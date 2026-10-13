import json, os, tempfile, urllib.request, urllib.error, uuid, errno
from urllib.parse import urlsplit
from pathlib import Path
from roggle_paths import project_root

def read_state():
    project=project_root();p=project/'run_state.json'
    if p.is_symlink():raise PermissionError('Refusing to edit a linked run_state.json.')
    raw=p.read_bytes() if p.exists() else b''
    state=json.loads(raw.decode('utf-8-sig')) if raw else {}
    if not isinstance(state,dict) or any(not isinstance(v,dict) for v in state.values()):raise ValueError('run_state.json must contain job records; no changes made.')
    revision=str(project)+'|'+(str(p.stat().st_mtime_ns)+':'+str(len(raw)) if p.exists() else 'missing')
    return project,p,raw,state,revision

def listing():
    project,p,raw,state,revision=read_state()
    rows=[{'key':key,'name':key,'state':'complete' if value.get('completed') else 'incomplete'} for key,value in state.items()]
    return {'jobs':rows,'revision':revision,'locked':(project/'.controller.lock').exists(),'complete':sum(r['state']=='complete' for r in rows),'incomplete':sum(r['state']=='incomplete' for r in rows),'state_path':str(p)}

def queue_idle(project):
    config=json.loads((project/'config.json').read_text(encoding='utf-8-sig'));url=config['server'].rstrip('/')+'/queue'
    parsed=urlsplit(url);local=parsed.scheme in ('http','https') and parsed.hostname in ('127.0.0.1','localhost','::1')
    try:
        with urllib.request.urlopen(url,timeout=5) as response:q=json.load(response)
    except Exception as e:
        reason=e.reason if isinstance(e,urllib.error.URLError) else e
        refused=isinstance(reason,ConnectionRefusedError) or isinstance(reason,OSError) and (reason.errno==errno.ECONNREFUSED or getattr(reason,'winerror',None)==10061)
        if local and refused:return 'offline'
        raise ValueError('Cannot verify backend queue status. Only an explicit local connection refusal permits offline clearing; timeouts, HTTP errors and other failures are blocked. No records changed.') from e
    if not isinstance(q,dict) or not isinstance(q.get('queue_running'),list) or not isinstance(q.get('queue_pending'),list):raise ValueError('Unexpected queue response; no records changed.')
    if q['queue_running'] or q['queue_pending']:raise ValueError('ComfyUI has running/pending jobs; clearing is blocked.')
    return 'idle'

def clear(mode,keys,expected):
    if mode not in ('selected','incomplete','all'):raise ValueError('Unknown clear action.')
    project,p,raw,state,revision=read_state();lock=project/'.controller.lock';token='roggle_jobs:'+uuid.uuid4().hex
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('Controller lock exists. Finish processing before clearing records.')
    with os.fdopen(fd,'w') as f:f.write(token)
    try:
        project,p,raw,state,revision=read_state()
        if revision!=expected:raise ValueError('Job state changed. Refresh Jobs and review before clearing.')
        backend_status=queue_idle(project)
        if mode=='selected':
            if not isinstance(keys,list) or not keys or any(not isinstance(k,str) or k not in state for k in keys):raise ValueError('Selected job no longer exists. Refresh Jobs.')
            remove=set(keys)
        elif mode=='incomplete':remove={k for k,v in state.items() if not v.get('completed')}
        else:remove=set(state)
        if not remove:return {'removed':0,'backend_status':backend_status}
        updated={k:v for k,v in state.items() if k not in remove}
        fd,temp=tempfile.mkstemp(prefix='.run_state_',suffix='.tmp',dir=str(project))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(updated,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
            if (p.read_bytes() if p.exists() else b'')!=raw:raise ValueError('Job state changed during clear; no records changed.')
            os.replace(temp,p)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        print('Roggle Jobs: cleared '+str(len(remove))+' job record(s); backend '+backend_status+'; media retained.',flush=True)
        return {'removed':len(remove),'backend_status':backend_status}
    finally:
        if lock.exists() and lock.read_text()==token:lock.unlink()
