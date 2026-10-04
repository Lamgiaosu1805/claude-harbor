#!/usr/bin/env python3
"""Native manager backend. stdout carries small JSON results only."""
import fcntl, json, os, plistlib, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path
import profile_store as store
import desktop_sync as sync

ROOT=store.ROOT

def configure():
    sync.ROOT=ROOT
    profiles=store.load(); ready={}; pending=[]
    for p in profiles:
        try: ready[p['id']]=store.account(p)
        except (OSError,ValueError,KeyError) as e: pending.append(p['name']+': '+str(e))
    selected={p['id']:p for p in profiles if p['id'] in ready}
    sync.NAMES={i:p['name'] for i,p in selected.items()}
    sync.gui=lambda i:store.gui(selected[i])
    sync.account_dir=lambda i:ready[i]
    sync.PROFILE_MODELS={i:p['model'] for i,p in selected.items()}
    sync.running_profiles=lambda:[i for i,p in selected.items() if any(l.startswith(p['bundle']+'/Contents/MacOS/Claude.bin') for l in sync.processes())]
    return profiles,pending

def status():
    profiles,pending=configure(); running=sync.running_profiles(); result=[]
    for p in profiles:
        ready=p['id'] in sync.NAMES; count=0; archived=0
        if ready:
            for f in store.account(p).parent.glob('*/local_*.json'):
                if (f.parent/('deleted_'+f.stem.removeprefix('local_'))).exists():continue
                count+=1
                try: archived+=bool(json.loads(f.read_text()).get('archived'))
                except ValueError:pass
        result.append({**{k:v for k,v in p.items() if k!='legacyAccount'},'ready':ready,'running':p['id'] in running,'sessions':count,'archived':archived})
    last=json.loads((ROOT/'last-sync.json').read_text()) if (ROOT/'last-sync.json').exists() else None
    return {'profiles':result,'pending':pending,'lastSync':last}

def create(name,kind):
    name=name.strip()
    if not name or len(name)>60 or any(c in name for c in '/\\:\0\n'):raise ValueError('Tên cần 1–60 ký tự, không chứa /, \\, : hoặc xuống dòng.')
    if kind not in ('claude','magpie'):raise ValueError('Loại profile không hợp lệ')
    source=Path('/Applications/Claude.app')
    if not source.exists():raise ValueError('Cần cài Claude chính thức tại /Applications/Claude.app.')
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        profiles=store.load(); apps=Path.home()/'Applications'; apps.mkdir(exist_ok=True)
        display=name if name.lower().startswith('claude') else 'Claude '+name
        target=apps/(display+'.app')
        if target.exists() or any(p['name']==display for p in profiles):raise ValueError('Tên này đã được sử dụng. Chọn tên khác.')
        pid='p'+uuid.uuid4().hex[:12]; bid='local.anle.claude.desktop.'+pid
        base=ROOT/'profiles'/pid; stage=Path(tempfile.mkdtemp(prefix='clone-',dir=ROOT)); clone=stage/'Claude.app'
        try:
            subprocess.run(['/bin/cp','-cR',str(source),str(clone)],check=True,capture_output=True)
            info=clone/'Contents/Info.plist'; data=plistlib.loads(info.read_bytes())
            executable=data.get('CFBundleExecutable','Claude')
            binary=clone/'Contents/MacOS'/executable; binary.rename(binary.with_name('Claude.bin'))
            data.update(CFBundleExecutable='Claude',CFBundleName='Claude',CFBundleDisplayName=display,CFBundleIdentifier=bid)
            for key in ('CFBundleURLTypes','CFBundleDocumentTypes','UTImportedTypeDeclarations','UTExportedTypeDeclarations'):data.pop(key,None)
            info.write_bytes(plistlib.dumps(data))
            args=['/usr/bin/python3',str(ROOT/'desktop_launcher.py'),pid,str(target)]
            c='#include <unistd.h>\n#include <stdlib.h>\nint main(int argc,char **argv){char **a=calloc(argc+5,sizeof(char*));\n'
            c+=''.join('a[%d]=%s;\n'%(i,json.dumps(s,ensure_ascii=True)) for i,s in enumerate(args))
            c+='for(int i=1;i<argc;i++)a[i+3]=argv[i];execv(a[0],a);return 127;}\n'
            src=stage/'shim.c';src.write_text(c)
            subprocess.run(['/usr/bin/clang',str(src),'-o',str(clone/'Contents/MacOS/Claude')],check=True,capture_output=True)
            entitlements=ROOT/'clone-entitlements.plist'
            if not entitlements.exists():raise ValueError('Thiếu entitlements của bộ nhân bản.')
            # Keep the original signed Electron frameworks, required for helper startup.
            for signed in (clone/'Contents/MacOS/Claude.bin',clone):
                subprocess.run(['/usr/bin/codesign','--force','--sign','-','--options','runtime','--entitlements',str(entitlements),str(signed)],check=True,capture_output=True)
            subprocess.run(['/usr/bin/codesign','--verify',str(clone)],check=True,capture_output=True)
            (base/'code').mkdir(parents=True); (base/'gui').mkdir()
            config={'deploymentMode':'3p' if kind=='magpie' else '1p','preferences':{'sidebarMode':'epitaxy'}}
            (base/'gui'/'claude_desktop_config.json').write_text(json.dumps(config))
            if kind=='magpie':
                g=base/'gui-3p';g.mkdir();(g/'claude_desktop_config.json').write_text(json.dumps(config))
                library=g/'configLibrary';library.mkdir();cid=str(uuid.uuid4())
                settings={'inferenceProvider':'gateway','inferenceGatewayBaseUrl':'http://127.0.0.1:3425','inferenceGatewayApiKey':'magpie-claude-desktop','inferenceGatewayAuthScheme':'bearer','disableDeploymentModeChooser':True,'deploymentDisplayName':display,'inferenceModels':['mythos-magpie-1026517788']}
                (library/(cid+'.json')).write_text(json.dumps(settings));(library/(cid+'.json')).chmod(0o600)
                (library/'_meta.json').write_text(json.dumps({'appliedId':cid,'entries':[{'id':cid,'name':display}]}))
            os.rename(clone,target)
            p=dict(id=pid,name=display,kind=kind,bundle=str(target),bundleID=bid,model='mythos-magpie-1026517788' if kind=='magpie' else 'sonnet',sourceVersion=data.get('CFBundleShortVersionString',''))
            try:store.save(profiles+[p])
            except Exception:
                os.rename(target,clone);raise
            return p
        except subprocess.CalledProcessError as e:
            if base.exists():shutil.rmtree(base)
            raise ValueError('Không tạo được app: '+e.stderr.decode(errors='replace')[-1200:])
        except Exception:
            if base.exists():shutil.rmtree(base)
            raise
        finally:shutil.rmtree(stage)

if __name__=='__main__':
    try:
        command=sys.argv[1] if len(sys.argv)>1 else 'status'
        if command=='status':result=status()
        elif command=='create': result=create(sys.argv[2],sys.argv[3])
        elif command in ('check','sync'):
            profiles,pending=configure()
            if len(sync.NAMES)<2:raise ValueError('Cần ít nhất hai profile đã đăng nhập và mở tab Code.')
            if command=='check':result={**sync.preflight(),'pending':pending,'eligible':list(sync.NAMES)}
            else:result={**sync.sync_all(),'pending':pending}
        else:raise ValueError('Lệnh không hợp lệ')
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
