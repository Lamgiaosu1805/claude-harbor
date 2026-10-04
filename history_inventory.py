"""Discover local Claude Code histories, including those with no Desktop record."""
import datetime, hashlib, json, uuid, re
from pathlib import Path

EXTERNAL = {}
TRANSCRIPTS = {}
SUMMARIES = {}
PATH_CACHE = {}
WARNINGS = []
SOURCE_STATS = {}
HISTORY_META = {}
PROJECT_PATHS = {}
BASE_ROOT = None

def initialize(module):
    global BASE_ROOT, PATH_CACHE
    EXTERNAL.clear(); TRANSCRIPTS.clear(); SUMMARIES.clear(); WARNINGS.clear(); SOURCE_STATS.clear(); HISTORY_META.clear()
    BASE_ROOT = module.ROOT
    PROJECT_PATHS.clear()
    configs=[Path.home()/'.claude.json',*[module.code(p)/'.claude.json' for p in module.NAMES]]
    for config in configs:
        try:
            for cwd in json.loads(config.read_text()).get('projects',{}):
                slug=re.sub(r'[^a-zA-Z0-9]','-',cwd)
                PROJECT_PATHS.setdefault(slug,set()).add(cwd)
        except (OSError,ValueError):pass
    cache = module.ROOT / 'history-index.json'
    try: PATH_CACHE = json.loads(cache.read_text()).get('paths', {})
    except (OSError, ValueError): PATH_CACHE = {}
    candidates = module.HISTORY_ROOTS
    if candidates is None:
        candidates = [Path.home()/'.claude', Path.home()/'.local/share/claude-three-profiles/shared']
        candidates += [p for p in (Path.home()/'.config/magpie/claude-accounts').glob('*') if p.is_dir()]
    for i, root in enumerate(candidates):
        if (root/'projects').is_dir(): EXTERNAL['history-'+str(i)] = root
    for root in [*EXTERNAL.values(), *(module.code(p) for p in module.NAMES)]:
        index(root)
    # Desktop gives better titles, workspace and archive information than bare CLI files.
    desktop_roots = module.DESKTOP_ROOTS if module.DESKTOP_ROOTS is not None else [Path.home()/'Library/Application Support/Claude', Path.home()/'Library/Application Support/Claude-3p']
    for gui in desktop_roots:
        record_count = 0; missing = 0
        for path in gui.glob('claude-code-sessions/*/*/local_*.json'):
            try:
                record = json.loads(path.read_text()); sid = record.get('cliSessionId')
                if not sid:continue
                record_count += 1
                HISTORY_META[sid] = record
                if not any(sid in files for files in TRANSCRIPTS.values()):
                    missing += 1
                    WARNINGS.append({'record':str(path),'session':sid,'reason':'desktop_record_without_transcript'})
            except (OSError, ValueError) as e:
                WARNINGS.append({'record':str(path),'reason':'invalid_desktop_record','detail':str(e)})
        SOURCE_STATS[str(gui)] = {'desktopRecords':record_count,'missingTranscripts':missing}


def index(root):
    key = str(root)
    if key not in TRANSCRIPTS:
        files = {}
        for path in (root/'projects').glob('*/*.jsonl'):
            try: sid = str(uuid.UUID(path.stem))
            except ValueError:continue
            files.setdefault(sid, []).append(path)
        TRANSCRIPTS[key] = files
        SOURCE_STATS[key] = {'transcripts':sum(len(p) for p in files.values()),'uniqueSessionIds':len(files)}
    return TRANSCRIPTS[key]


def locate(root, sid):
    candidates = index(root).get(sid, [])
    if not candidates:
        candidates = list((root/'projects').glob('*/'+sid+'.jsonl'))
        if candidates:index(root)[sid] = candidates
    if not candidates:raise ValueError('Missing transcript '+sid)
    return max(candidates, key=lambda p:p.stat().st_size)


def timestamp(value, fallback):
    try:return int(datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1000)
    except (ValueError, AttributeError):return fallback


def summarize(path):
    stat = path.stat(); stamp = [stat.st_size, stat.st_mtime_ns]
    old = PATH_CACHE.get(str(path))
    if old and old['stamp'] == stamp:return old['summary']
    # APFS seed copies retain session ID, byte length and mtime. Parse one copy once.
    fingerprint = (path.stem, *stamp)
    if fingerprint in SUMMARIES:
        summary = SUMMARIES[fingerprint]
    else:
        first_time = int(stat.st_mtime*1000); last_time = first_time
        cwd = ''; title = ''; prompt = ''; signature = []; last_assistant = None
        seen = set(); turns = 0; plan_names = set()
        with path.open() as f:
            for line in f:
                if not line.strip():continue
                try:r = json.loads(line)
                except ValueError:
                    raise ValueError('Invalid JSONL in '+str(path))
                cwd = r.get('cwd') or cwd
                if r.get('timestamp'):
                    t = timestamp(r['timestamp'],first_time)
                    if not signature:first_time=t
                    last_time=t
                if r.get('type') in ('custom-title','ai-title'):
                    title = r.get('customTitle') or r.get('aiTitle') or r.get('title') or title
                if r.get('slug'):plan_names.add(r['slug']+'.md')
                if r.get('type') not in ('user','assistant') or r.get('isSidechain'):continue
                msg = r.get('message',{}); mid = r.get('uuid')
                if mid and mid in seen:continue
                seen.add(mid)
                stable={'type':r['type'],'uuid':mid,'role':msg.get('role'),'content':msg.get('content'),'stop_reason':msg.get('stop_reason')}
                signature.append(hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
                if r['type']=='user':
                    turns += 1
                    if not prompt:
                        content=msg.get('content','')
                        if isinstance(content,str):prompt=content
                        elif isinstance(content,list):prompt=' '.join(b.get('text','') for b in content if isinstance(b,dict) and b.get('type')=='text')
                else:last_assistant=mid
        if path.stat().st_mtime_ns != stamp[1] or path.stat().st_size != stamp[0]:
            raise ValueError('Source is being written: '+str(path))
        cwd = cwd or HISTORY_META.get(path.stem,{}).get('cwd','')
        known=PROJECT_PATHS.get(path.parent.name,set())
        if not cwd and len(known)==1:cwd=next(iter(known))
        if not cwd:
            # Keep unresolved histories in the report, never guess a filesystem path.
            raise ValueError('Transcript has no working directory: '+str(path))
        title=title or prompt.strip().split('\n')[0][:120] or path.stem
        summary={'cwd':cwd,'title':title,'createdAt':first_time,'lastActivityAt':last_time,'signature':signature,
                 'lastAssistantUuid':last_assistant,'completedTurns':turns,'planNames':sorted(plan_names)}
        SUMMARIES[fingerprint]=summary
    PATH_CACHE[str(path)]={'stamp':stamp,'summary':summary}
    return summary


def candidates(module, managed, state):
    linked = {}
    for p,path,d in managed:
        gid=state['members'].get(str(path)) or d.get('threeAppSync',{}).get('group')
        if gid:
            for sid in [d['cliSessionId'],*d.get('priorCliSessionIds',[])]:linked[sid]=gid
    out=[]; scanned = set()
    for profile in [*module.NAMES,*EXTERNAL]:
        root=module.code(profile)
        owned={d['cliSessionId'] for p,_,d in managed if p==profile}
        for sid, files in index(root).items():
            if sid in owned:continue
            path=max(files,key=lambda p:p.stat().st_size)
            try:
                summary=summarize(path)
                if not summary['signature']:
                    WARNINGS.append({'transcript':str(path),'reason':'no_conversation_messages'});continue
            except (OSError,ValueError) as e:
                WARNINGS.append({'transcript':str(path),'reason':'unreadable_or_unstable','detail':str(e)});continue
            gid=linked.get(sid) or str(uuid.uuid5(uuid.NAMESPACE_URL,'claude-local-history:'+sid))
            local='local_'+str(uuid.uuid5(uuid.NAMESPACE_URL,'claude-history:'+profile+':'+sid))
            record={k:v for k,v in summary.items() if k not in ('signature','planNames')}
            source_meta=HISTORY_META.get(sid,{})
            for key in ('title','titleSource','createdAt','lastActivityAt','isArchived','cwd','originCwd'):
                if key in source_meta:record[key]=source_meta[key]
            record.update(sessionId=local,cliSessionId=sid,priorCliSessionIds=[],permissionMode='default',
                          model=getattr(module,'PROFILE_MODELS',{}).get(profile,'mythos-magpie-1026517788' if profile=='magpie' else 'sonnet'),
                          originCwd=record.get('originCwd',record['cwd']),isArchived=record.get('isArchived',False),
                          threeAppSync={'group':gid,'historyImport':True})
            if profile in module.NAMES:
                record_path=module.account_dir(profile)/(local+'.json')
            else:record_path=path
            out.append((profile,record_path,record,summary['signature'],gid))
            scanned.add(sid)
    return out,scanned


def persist(module, tx):
    tx.write(module.ROOT/'history-index.json',module.json_bytes({'version':1,'paths':PATH_CACHE}))
    audit={'sources':SOURCE_STATS,'warnings':WARNINGS}
    tx.write(module.ROOT/'history-audit.json',module.json_bytes(audit))
