#!/usr/bin/env python3
"""Synchronize Code histories across registered Desktop clones, while closed."""
import types, re, datetime, fcntl, hashlib, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
import history_inventory as inventory
import profile_store as store

HISTORY_ROOTS = None
DESKTOP_ROOTS = None

ROOT = store.ROOT
NAMES = {'pro1': 'Claude Pro 1', 'pro2': 'Claude Pro 2', 'magpie': 'Claude Magpie GPT-6.1'}
BOUND = ('remoteMcpServersConfig', 'sessionPermissionUpdates', 'alwaysAllowedReasons',
         'promptAppendSnapshot', 'toolSurfaceSnapshot', 'spawnSeed', 'cliBinaryPin',
         'enabledMcpTools', 'chromePermissionMode', 'autoChosenInApp',
         'autoModeServerFallbackPrompt')

def gui(profile):
    return ROOT / 'profiles' / profile / ('gui-3p' if profile == 'magpie' else 'gui')

def code(profile):
    return inventory.EXTERNAL.get(profile, ROOT / 'profiles' / profile / 'code')

def read(path):
    return json.loads(path.read_text())

def processes():
    return subprocess.check_output(['/bin/ps', '-axo', 'command='], text=True).splitlines()

def running_profiles():
    lines = processes()
    return [p for p in NAMES if any(l.startswith(str(Path.home() / 'Applications' /
            (NAMES[p] + '.app') / 'Contents/MacOS/Claude.bin')) for l in lines)]

def validate_id(value):
    return str(uuid.UUID(value))

def account_dir(profile):
    return store.account(next(p for p in store.load() if p['id'] == profile))

def records():
    out = []
    for profile in NAMES:
        root = account_dir(profile)
        # Desktop may use several orgs for the same signed-in account.
        for path in root.parent.glob('*/local_*.json'):
            if (path.parent / ('deleted_' + path.stem.removeprefix('local_'))).exists():
                continue
            d = read(path)
            if d.get('cliSessionId'):
                out.append((profile, path, d))
    return out

def transcript(profile, sid):
    validate_id(sid)
    return inventory.locate(code(profile), sid)

def snapshot(profile, path, record):
    main_id = record['cliSessionId']
    ids = list(dict.fromkeys([*record.get('priorCliSessionIds', []), main_id]))
    files, rows, signature, seen = {}, [], [], set()
    for sid in ids:
        t = transcript(profile, sid)
        # JSONL rows end at '\n' only; splitlines() also breaks on U+2028/U+2029/U+0085 inside strings.
        body = [json.loads(l) for l in t.read_text().split('\n') if l.strip()]
        files[sid] = (t, body)
        if sid == main_id:
            rows = body
        for row in body:
            if row.get('type') not in ('user', 'assistant') or row.get('isSidechain'):
                continue
            key = row.get('uuid')
            if key and key in seen:
                continue
            seen.add(key)
            msg = row.get('message', {})
            stable = {'type': row['type'], 'uuid': key,
                      'role': msg.get('role'), 'content': msg.get('content'),
                      'stop_reason': msg.get('stop_reason')}
            signature.append(hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
    # An idle child process is normal. Use the saved completed-turn marker instead.
    frames = [r for r in rows if r.get('type') in ('user', 'assistant') and not r.get('isSidechain')]
    busy = False
    if frames:
        last_user = max((i for i, r in enumerate(frames) if r['type'] == 'user' and
                         r.get('message', {}).get('role') == 'user'), default=-1)
        marker = record.get('lastAssistantUuid')
        final = max((i for i, r in enumerate(frames) if r['type'] == 'assistant' and
                     r.get('uuid') == marker), default=-1)
        busy = last_user >= 0 and (final <= last_user or
               not any(r.get('subtype') == 'stop_hook_summary' and
                       r.get('timestamp', '') >= frames[final].get('timestamp', '')
                       for r in rows))
    return {'profile': profile, 'path': path, 'record': record, 'files': files,
            'signature': signature, 'busy': busy}

def live_cli_ids():
    result = {}
    for line in processes():
        for profile in NAMES:
            if str(gui(profile)/'claude-code') in line and '/Contents/MacOS/claude' in line:
                result.setdefault(profile,set()).update(re.findall(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',line))
    return result

def preflight():
    busy, errors = [], []
    active = running_profiles(); live = live_cli_ids()
    for p,path,d in records():
        # Historical interrupted sessions are not running turns. Only inspect live SDKs.
        if p not in live:continue
        if d['cliSessionId'] not in live[p] and d.get('latestUserFrameAt',0) < (time.time()-300)*1000:continue
        try:
            s = snapshot(p,path,d)
            if s['busy'] and p in active:busy.append(NAMES[p]+': '+d.get('title',path.stem))
        except (OSError,ValueError):
            busy.append(NAMES[p]+': đang ghi phiên, chờ lưu xong')
    return {'busy':busy,'errors':errors,'running':active}

def prefix(left, right):
    return len(left) <= len(right) and left == right[:len(left)]

class Transaction:
    def __init__(self):
        self.root = ROOT / 'sync-backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(uuid.uuid4())[:8])
        self.root.mkdir(parents=True)
        self.changes = []

    def write(self, path, data):
        if path.exists() and path.read_bytes() == data:
            return
        index = len(self.changes)
        backup = self.root / str(index)
        if path.exists():
            shutil.copy2(path, backup)
        self.changes.append((path, backup if backup.exists() else None))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.sync-' + str(uuid.uuid4()) + '.tmp')
        with temp.open('wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)

    def rollback(self):
        for i, (path, backup) in enumerate(reversed(self.changes)):
            if backup:
                shutil.copy2(backup, path)
            elif path.exists():
                # Keep any newly created file for recovery instead of deleting it.
                shutil.move(str(path), str(self.root / ('rolled-back-' + str(i))))

    def report(self):
        (self.root / 'paths.json').write_text(json.dumps([
            {'path': str(p), 'backup': str(b) if b else None}
            for p, b in self.changes], indent=2))

def json_bytes(d):
    return (json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()

def copy_session(source, profile, existing, group_id, tx):
    record = source['record']
    old = record['cliSessionId']
    if existing:
        dest_record = dict(existing['record'])
        new = dest_record['cliSessionId']
        local = dest_record['sessionId']
        record_path = existing['path']
        dest_file = existing['files'][new][0]
    else:
        new = str(uuid.uuid4()); local = 'local_' + str(uuid.uuid4())
        record_path = account_dir(profile) / (local + '.json')
        rel = source['files'][old][0].parent.relative_to(code(source['profile']))
        dest_file = code(profile) / rel / (new + '.jsonl')
        dest_record = {k: v for k, v in record.items() if k not in BOUND}
        dest_record.update(model=globals().get('PROFILE_MODELS', {}).get(profile, 'mythos-magpie-1026517788' if profile == 'magpie' else 'sonnet'),
                           permissionMode='default')
    id_map = {old: new}
    prior_ids = []
    for sid in record.get('priorCliSessionIds', []):
        if sid == old:
            continue
        mapped = dest_record.get('threeAppSync', {}).get('priorMap', {}).get(sid, str(uuid.uuid4()))
        id_map[sid] = mapped; prior_ids.append(mapped)
    for sid, (src, rows) in source['files'].items():
        mapped = id_map[sid]
        target = dest_file if sid == old else code(profile) / src.parent.relative_to(code(source['profile'])) / (mapped + '.jsonl')
        if existing and source['signature'] == existing['signature']:
            continue
        converted = []
        for row in rows:
            row = dict(row)
            if row.get('sessionId') in id_map:
                row['sessionId'] = id_map[row['sessionId']]
            converted.append(json.dumps(row, ensure_ascii=False))
        tx.write(target, ('\n'.join(converted) + '\n').encode())
        # Preserve per-session tool history, attachments and subagent transcripts.
        for folder in [code(source['profile']) / 'file-history' / sid,
                       code(source['profile']) / 'tasks' / sid, src.with_suffix('')]:
            if not folder.is_dir():
                continue
            target_folder = (target.with_suffix('') if folder == src.with_suffix('')
                             else code(profile) / folder.parent.name / mapped)
            for f in folder.rglob('*'):
                if f.is_file():
                    tx.write(target_folder / f.relative_to(folder), f.read_bytes())
    # Referenced plan/paste files only; no unrelated credentials, settings or memory.
    text = source.get('referenceText')
    if text is None:
        text = '\n'.join(json.dumps(r, ensure_ascii=False) for _, rows in source['files'].values() for r in rows)
        source['referenceText'] = text
    for category in ('plans', 'paste-cache'):
        if not text:continue
        for f in (code(source['profile']) / category).glob('*'):
            if f.is_file() and (f.name in text or str(f) in text):
                target = code(profile) / category / f.name
                if target.exists() and target.read_bytes() != f.read_bytes():
                    continue
                tx.write(target, f.read_bytes())
    # Keep target account permissions/model, update session history and visible status.
    for key in ('title', 'titleSource', 'lastActivityAt', 'completedTurns', 'latestUserFrameAt',
                'lastAssistantUuid', 'postTurnSummary', 'postTurnSummaryFor'):
        if key in record:
            dest_record[key] = record[key]
    dest_record.update(sessionId=local, cliSessionId=new, priorCliSessionIds=prior_ids,
                       threeAppSync={'group': group_id, 'priorMap': {k: v for k, v in id_map.items() if k != old}})
    tx.write(record_path, json_bytes(dest_record))
    return str(record_path)

def sync_all():
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'sync.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Một lượt đồng bộ khác đang chạy.')
        if running_profiles():
            raise ValueError('App vẫn đang mở. Dùng nút Đồng bộ tất cả để tự đóng và mở lại app.')
        check = preflight()
        if check['busy'] or check['errors']:
            raise ValueError('Chưa đồng bộ: ' + '; '.join(check['busy'] + check['errors']))
        manifest_path = ROOT / 'sync-state.json'
        state = read(manifest_path) if manifest_path.exists() else {'version': 1, 'members': {}}
        context = types.SimpleNamespace(ROOT=ROOT,NAMES=NAMES,PROFILE_MODELS=globals().get("PROFILE_MODELS",{}),code=code,account_dir=account_dir,json_bytes=json_bytes,HISTORY_ROOTS=HISTORY_ROOTS,DESKTOP_ROOTS=DESKTOP_ROOTS)
        inventory.initialize(context)
        managed = records()
        groups = {}
        for p, path, record in managed:
            gid = state['members'].get(str(path)) or record.get('threeAppSync', {}).get('group') or str(uuid.uuid4())
            groups.setdefault(gid, []).append({'profile':p,'path':path,'record':record})
        discovered, source_ids = inventory.candidates(context, managed, state)
        for p,path,record,signature,gid in discovered:
            groups.setdefault(gid, []).append({'profile':p,'path':path,'record':record,'signature':signature})
        tx = Transaction(); next_members = {path:gid for path,gid in state['members'].items() if not any(Path(path).is_relative_to(gui(p)) for p in NAMES)}; branches = 0; count = 0
        try:
            imported = 0
            for gid, descriptors in groups.items():
                members = []
                for descriptor in descriptors:
                    try:
                        p=descriptor['profile']; d=descriptor['record']; sid=d['cliSessionId']
                        if d.get('priorCliSessionIds'):
                            member=snapshot(p,descriptor['path'],d)
                        else:
                            file=transcript(p,sid)
                            sig=descriptor.get('signature') or inventory.summarize(file)['signature']
                            member={**descriptor,'files':{sid:(file,[])},'signature':sig,'busy':False}
                        members.append(member)
                    except (OSError,ValueError) as e:
                        inventory.WARNINGS.append({'record':str(descriptor['path']),'reason':'cannot_load_history','detail':str(e)})
                if not members:continue
                maxima = []
                for member in sorted(members, key=lambda x: len(x['signature']), reverse=True):
                    if not any(prefix(member['signature'], x['signature']) for x in maxima):
                        maxima.append(member)
                claimed = set()
                for index, canonical in enumerate(maxima):
                    branch_id = gid if index == 0 else str(uuid.uuid4())
                    if index:
                        branches += 1
                    selected={}
                    for profile in NAMES:
                        choices=[m for m in members if m['profile']==profile and str(m['path']) not in claimed and prefix(m['signature'],canonical['signature'])]
                        selected[profile]=max(choices,key=lambda x:len(x['signature']),default=None)
                    if any(not m or m['signature']!=canonical['signature'] for m in selected.values()):
                        canonical=snapshot(canonical['profile'],canonical['path'],canonical['record'])
                    for profile,existing in selected.items():
                        if existing:claimed.add(str(existing['path']))
                        path=copy_session(canonical,profile,existing,branch_id,tx)
                        next_members[path]=branch_id
                    count += 1
            inventory.persist(context, tx)
            tx.write(manifest_path, json_bytes({'version': 1, 'members': next_members}))
            tx.report()
            report = {'profiles': len(NAMES), 'sessions': count, 'newBranches': branches,
                      'filesChanged':sum(p.name not in ('history-index.json','history-audit.json','sync-state.json') for p,_ in tx.changes), 'backup': str(tx.root),
                      'sourceHistories':len(source_ids), 'warnings':len(inventory.WARNINGS),
                      'audit':str(ROOT/'history-audit.json')}
            (ROOT / 'last-sync.json').write_bytes(json_bytes(report))
            return report
        except Exception:
            tx.rollback(); tx.report(); raise

if __name__ == '__main__':
    os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('manager.py')),*sys.argv[1:]])
