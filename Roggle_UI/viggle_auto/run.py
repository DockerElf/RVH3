import math
import json, sys, time, shutil, hashlib, copy, os, subprocess, urllib.request, urllib.error, re
from pathlib import Path
from settings import R, C, INPUT, OUTPUT, STAGING, STAGING_SUBDIR, STEP34INPUT, STEP3_OUTPUT, STEP4_OUTPUT, STEP3_PREFIX, STEP4_PREFIX
I=INPUT; U=C['server'].rstrip('/')
S=R/'run_state.json'; L=R/'.controller.lock'
def api(path,data=None):
    req=urllib.request.Request(U+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as f:return json.load(f)
    except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode(errors='replace'))
def save(s):
    t=S.with_suffix('.tmp');t.write_text(json.dumps(s,indent=2));t.replace(S)
def source_id(p):
    p=p.resolve()
    if p.is_relative_to(R):return 'project/'+p.relative_to(R).as_posix()
    if p.is_relative_to(STEP3_OUTPUT):return 'step3output/'+p.relative_to(STEP3_OUTPUT).as_posix()
    raise PermissionError('Unsupported source outside project/Step 3 output: '+str(p))
def stage(p):
    p=p.resolve()
    if p.is_relative_to(R):rel=p.relative_to(R)
    elif p.is_relative_to(STEP3_OUTPUT):rel=Path('step3output')/p.relative_to(STEP3_OUTPUT)
    else:raise PermissionError('Cannot stage a file outside project or Step 3 outputs.')
    dest=(STAGING/rel).resolve()
    if not dest.is_relative_to(STAGING):raise PermissionError('Staging path escapes its root.')
    dest.parent.mkdir(parents=True,exist_ok=True);a=p.stat()
    if not dest.exists() or (dest.stat().st_size,dest.stat().st_mtime_ns)!=(a.st_size,a.st_mtime_ns):shutil.copy2(p,dest);print('Staged:',rel,flush=True)
    return STAGING_SUBDIR+'/'+rel.as_posix()
STEP3_PARAMETERS={
 'head_weight':('544','PrimitiveFloat'),'body_weight':('545','PrimitiveFloat'),
 'positive_text_head':('548','PrimitiveStringMultiline'),'negative_text':('549','PrimitiveStringMultiline'),
 'positive_text_body':('550','PrimitiveStringMultiline'),'positive_text_general':('552','PrimitiveStringMultiline'),
}
def apply_step3_parameters(workflow,config):
    parameters=config.get('step3_parameters',{})
    if not isinstance(parameters,dict):raise ValueError('step3_parameters must be an object.')
    if set(parameters)-set(STEP3_PARAMETERS):raise ValueError('Unknown step3_parameters keys.')
    updates=[]
    for key,value in parameters.items():
        node_id,kind=STEP3_PARAMETERS[key];node=workflow.get(node_id)
        if not isinstance(node,dict) or node.get('class_type')!=kind or not isinstance(node.get('inputs'),dict) or 'value' not in node['inputs']:raise ValueError(key+' requires '+kind+' node '+node_id+' with inputs.value.')
        if kind=='PrimitiveFloat':
            if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(key+' must be a JSON number.')
            try:value=float(value)
            except (ValueError,OverflowError):raise ValueError(key+' must be finite.')
            if not math.isfinite(value):raise ValueError(key+' must be finite.')
        elif not isinstance(value,str):raise ValueError(key+' must be text.')
        updates.append((node_id,value))
    for node_id,value in updates:workflow[node_id]['inputs']['value']=value

def load(step):
    w=json.loads((R/C[step+'_workflow']).read_text(encoding='utf-8-sig'))
    if 'nodes' in w:raise RuntimeError('Use API-format workflow exports, not canvas JSON.')
    for n in (['534','521'] if step=='step3' else ['3','73']):
        if n not in w or 'inputs' not in w[n]:raise RuntimeError('Missing API node '+n)
    if step=='step3':apply_step3_parameters(w,C)
    node_id,prefix=('541',STEP3_PREFIX) if step=='step3' else ('82',STEP4_PREFIX)
    node=w.get(node_id)
    if not isinstance(node,dict) or node.get('class_type')!='PrimitiveString' or not isinstance(node.get('inputs'),dict) or 'value' not in node['inputs']:raise ValueError('Output prefix requires PrimitiveString node '+node_id+' with inputs.value.')
    node['inputs']['value']=prefix
    return w
def ready():
    try:api('/system_stats');return
    except Exception:pass
    subprocess.Popen(['cmd.exe','/c',str(R/'_1_start_backend.bat')],creationflags=subprocess.CREATE_NEW_CONSOLE)
    print('Waiting for backend...',flush=True);end=time.monotonic()+C['startup_timeout_seconds']
    while time.monotonic()<end:
        try:api('/system_stats');return
        except Exception:time.sleep(3)
    raise RuntimeError('Backend startup timeout; inspect backend console.')
def snap(folder,ext):
    return {str(p.resolve()):[p.stat().st_size,p.stat().st_mtime_ns] for p in folder.rglob('*') if p.is_file() and p.suffix.lower()==ext}
def job(key,w,sources,folder,ext,state):
    h=hashlib.sha256(json.dumps(w,sort_keys=True).encode())
    for p in sources:
        a=p.stat();h.update(f'{source_id(p)}|{a.st_size}|{a.st_mtime_ns}'.encode())
    sig=h.hexdigest();old=state.get(key,{})
    if old.get('signature')==sig and old.get('completed') and old.get('outputs') and all(Path(p).exists() for p in old['outputs']):print('Skip:',key,flush=True);return
    if old.get('prompt_id') and not old.get('completed'):
        if old.get('signature')!=sig:raise RuntimeError('Unfinished job inputs changed: '+key)
        pid=old['prompt_id'];before=old['before'];print('Resume wait:',key,flush=True)
    else:
        q=api('/queue')
        if q.get('queue_running') or q.get('queue_pending'):raise RuntimeError('Backend queue is busy. Wait before running automation.')
        before=snap(folder,ext);print('Submit:',key,flush=True)
        result=api('/prompt',{
            'prompt':w,
            'client_id':'viggle_auto_controller',
            'extra_data': {
                'extra_pnginfo':{
                    'workflow':{
                        'extra':{
                            'VHS_MetadataImage': False,
                            'VHS_KeepIntermediate' :False
                        }
                    }
                }
            }
        })
        if 'prompt_id' not in result:raise RuntimeError(json.dumps(result))
        pid=result['prompt_id'];state[key]={'signature':sig,'prompt_id':pid,'before':before,'completed':False};save(state)
    end=time.monotonic()+C['job_timeout_seconds']
    while time.monotonic()<end:
        rec=api('/history/'+pid).get(pid)
        if rec:
            status=rec.get('status',{})
            if status.get('status_str')=='error' or any(m[0] in ('execution_error','execution_interrupted') for m in status.get('messages',[])):raise RuntimeError(json.dumps(status))
            if status.get('completed'):break
        time.sleep(C['poll_seconds'])
    else:raise RuntimeError('Job timeout. Backend may still be running; do not clean inputs or blindly resubmit.')
    outputs=[]
    for _ in range(5):
        after=snap(folder,ext);outputs=sorted(p for p,v in after.items() if before.get(p)!=v)
        if outputs:break
        time.sleep(1)
    if not outputs:raise RuntimeError('No new/changed '+ext+' under '+str(folder)+'. Inspect save graph; pending state retained.')
    state[key]={'signature':sig,'prompt_id':pid,'completed':True,'outputs':outputs};save(state)
    print('Finished:',key,'->',len(outputs),'file(s)',flush=True)
def run(step,state):
    w=load(step);src=STEP34INPUT
    if step=='step3':
        static=[(R/n).resolve() for n in C['static_images']]
        if not static:raise RuntimeError('Static list empty.')
        for p in static:
            p.relative_to(R)
            if not p.is_file():raise RuntimeError('Missing static: '+str(p))
        images=sorted(p for p in src.glob('*') if p.suffix.lower()=='.png')
        if not images:raise RuntimeError('No main PNGs in step34input.')
        paths=[stage(p) for p in static]
        for p in images:
            if not re.fullmatch(r'[^_\s]+_\d{2}-\d{2}-\d{2}',p.stem):raise RuntimeError('Unexpected main filename: '+p.name)
            a=copy.deepcopy(w);a['534']['inputs']['image']=stage(p);a['521']['inputs']['selected_paths']=json.dumps(paths)
            job('step3:'+p.name,a,[p]+static,STEP3_OUTPUT,'.png',state)
    else:
        images=sorted((STEP3_OUTPUT).rglob('*.png'))
        if not images:raise RuntimeError('No Step 3 PNGs.')
        pairs=[]
        for p in images:
            stem=p.parent.name
            if not re.fullmatch(r'[^_\s]+_\d{2}-\d{2}-\d{2}',stem):raise RuntimeError('Unexpected Step 3 folder: '+str(p.parent))
            v=src/(stem+'.mp4')
            if not v.is_file():raise RuntimeError('Missing video: '+str(v))
            pairs.append((p,v))
        for p,v in pairs:
            a=copy.deepcopy(w);a['3']['inputs']['video']=stage(v);a['75']['inputs']['value']=v.name;a['73']['inputs']['image']=stage(p)
            job('step4:step3output/'+p.relative_to(STEP3_OUTPUT).as_posix(),a,[p,v],STEP4_OUTPUT,'.mp4',state)
def main():
    mode=sys.argv[1]
    if mode in ('validate-step3','validate-paths'):
        if mode=='validate-step3':
            workflow=load('step3')
            effective={key:workflow[node]['inputs']['value'] for key,(node,kind) in STEP3_PARAMETERS.items() if node in workflow}
            effective['output_prefix_541']=workflow['541']['inputs']['value']
        else:
            load('step3');load('step4')
            effective={'project':str(R),'comfy_input':str(INPUT),'comfy_output':str(OUTPUT),'staging':str(STAGING),'step34input':str(STEP34INPUT),'step3output':str(STEP3_OUTPUT),'step4output':str(STEP4_OUTPUT),'step3_prefix':STEP3_PREFIX,'step4_prefix':STEP4_PREFIX}
        print('Validation passed. No backend started; no jobs submitted.')
        print(json.dumps(effective,ensure_ascii=False,indent=2));return
    try:fd=os.open(L,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise RuntimeError('Controller lock exists. If a prior run crashed, verify no controller is active and backend queue is idle before removing .controller.lock.')
    os.close(fd)
    try:
        state=json.loads(S.read_text()) if S.exists() else {}
        if mode in ('cleanup','reset'):
            if input('Type YES to '+mode+' (originals and outputs retained): ').strip()!='YES':return
            try:
                q=api('/queue')
                if q.get('queue_running') or q.get('queue_pending'):raise RuntimeError('Queue busy; refusing cleanup/reset.')
            except (urllib.error.URLError,TimeoutError):pass
            if mode=='cleanup':
                p=STAGING
                if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise RuntimeError('Staging root is a junction/link; refusing deletion.')
                if p.exists():shutil.rmtree(p)
                print('Staging deleted; completed-job records retained.')
            else:
                if any(not v.get('completed') for v in state.values()):raise RuntimeError('Unfinished jobs exist; inspect state before resetting manually.')
                if S.exists():S.unlink()
                print('Job records reset. Next run will process again; existing outputs retained.')
            return
        steps=['step3','step4'] if mode=='both' else [mode]
        for step in steps:load(step)
        ready()
        for step in steps:run(step,state)
        print('All requested jobs finished.')
    finally:L.unlink(missing_ok=True)
if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt) as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
