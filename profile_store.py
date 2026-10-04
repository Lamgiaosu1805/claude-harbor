"""Profile registry: login data never travels between profiles."""
import json, os, uuid
from pathlib import Path
SUPPORT = Path.home() / 'Library/Application Support'
LEGACY = SUPPORT / 'ClaudeThreeDesktop'
ROOT = LEGACY if (LEGACY / 'profiles.json').exists() else SUPPORT / 'ClaudeHarbor'
REGISTRY = ROOT / 'profiles.json'

def defaults():
    return []

def load():
    if REGISTRY.exists():
        profiles=json.loads(REGISTRY.read_text())['profiles']
    else: profiles=defaults()
    for p in profiles:
        if not p['id'].replace('-','').isalnum(): raise ValueError('Profile ID không hợp lệ')
    return profiles

def save(profiles):
    ROOT.mkdir(parents=True,exist_ok=True)
    temp=REGISTRY.with_suffix('.tmp-'+uuid.uuid4().hex)
    temp.write_text(json.dumps({'version':1,'profiles':profiles},ensure_ascii=False,indent=2)+'\n')
    temp.chmod(0o600); os.replace(temp,REGISTRY)

def gui(p): return ROOT/'profiles'/p['id']/('gui-3p' if p['kind']=='magpie' else 'gui')

def account(p):
    g=gui(p); config=g/'config.json'
    data=json.loads(config.read_text()) if config.exists() else {}
    current=data.get('lastKnownAccountUuid')
    legacy=p.get('legacyAccount')
    if legacy:
        f=Path.home()/'.config/magpie/claude-accounts'/legacy/'.claude.json'
        if f.exists():
            a=json.loads(f.read_text()).get('oauthAccount',{})
            if current and current!=a.get('accountUuid'): legacy=None
            else:
                return g/'claude-code-sessions'/str(uuid.UUID(a['accountUuid']))/str(uuid.UUID(a['organizationUuid']))
    base=g/'claude-code-sessions'
    if current:
        base=base/str(uuid.UUID(current))
        orgs=[d for d in base.iterdir() if d.is_dir()] if base.exists() else []
    else:
        # The 3P deployment has its own synthetic account, supplied by Desktop.
        if p['kind']!='magpie': raise ValueError('Đăng nhập và mở tab Code một lần để bật đồng bộ.')
        origins=list(base.glob('*/*.profile-origin.json'))
        if len(origins)!=1: raise ValueError('Mở tab Code một lần để bật đồng bộ.')
        return origins[0].parent/origins[0].name.removesuffix('.profile-origin.json')
    if not orgs: raise ValueError('Mở tab Code và tạo một phiên local để bật đồng bộ.')
    return max(orgs,key=lambda d:max((f.stat().st_mtime for f in d.glob('local_*.json')),default=d.stat().st_mtime))
