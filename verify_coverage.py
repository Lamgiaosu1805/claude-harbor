"""Read-only content/coverage verification, using parsed-history cache."""
import json, types
from collections import defaultdict
import manager
from manager import sync, store
manager.configure()
context=types.SimpleNamespace(ROOT=sync.ROOT,NAMES=sync.NAMES,code=sync.code,account_dir=sync.account_dir,json_bytes=sync.json_bytes,HISTORY_ROOTS=sync.HISTORY_ROOTS,DESKTOP_ROOTS=sync.DESKTOP_ROOTS)
sync.inventory.initialize(context)
state=json.loads((sync.ROOT/'sync-state.json').read_text())['members']
groups=defaultdict(dict);missing=[]
for p,path,d in sync.records():
    gid=state.get(str(path)) or d.get('threeAppSync',{}).get('group')
    if not gid:missing.append(str(path));continue
    try:
        if d.get('priorCliSessionIds'):signature=sync.snapshot(p,path,d)['signature']
        else:signature=sync.inventory.summarize(sync.transcript(p,d['cliSessionId']))['signature']
        groups[gid][p]=signature
    except (OSError,ValueError) as e:missing.append(str(path)+': '+str(e))
incomplete=[gid for gid,m in groups.items() if set(m)!=set(sync.NAMES)]
mismatches=[gid for gid,m in groups.items() if any(s!=next(iter(m.values())) for s in m.values())]
result={'profiles':len(sync.NAMES),'sessionGroups':len(groups),'incompleteGroups':len(incomplete),'missingTranscripts':missing,'conversationMismatches':mismatches}
print(json.dumps(result,ensure_ascii=False,indent=2))
if incomplete or missing or mismatches:raise SystemExit(1)
