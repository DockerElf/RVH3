import json, math, hashlib, os, tempfile, uuid
from datetime import datetime
from pathlib import Path
from roggle_paths import project_root, resolve
import static_references
FIELDS={
 'head_weight':('544','PrimitiveFloat'),'body_weight':('545','PrimitiveFloat'),
 'positive_text_head':('548','PrimitiveStringMultiline'),'negative_text':('549','PrimitiveStringMultiline'),
 'positive_text_body':('550','PrimitiveStringMultiline'),'positive_text_general':('552','PrimitiveStringMultiline'),
}
def validate(values,complete=False):
    if not isinstance(values,dict):raise ValueError('Step 3 settings must be an object.')
    if set(values)-set(FIELDS):raise ValueError('Unknown Step 3 settings keys.')
    if complete and set(values)!=set(FIELDS):raise ValueError('All six Step 3 settings are required.')
    result={}
    for key,value in values.items():
        if FIELDS[key][1]=='PrimitiveFloat':
            if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(key+' must be a number.')
            try:value=float(value)
            except (ValueError,OverflowError):raise ValueError(key+' must be finite.')
            if not math.isfinite(value):raise ValueError(key+' must be finite.')
        elif not isinstance(value,str):raise ValueError(key+' must be text.')
        result[key]=value
    return result

def read():
    project=project_root();path=project/'config.json';raw=path.read_bytes();config=json.loads(raw.decode('utf-8-sig'))
    active=config.get('static_images',[])
    if not isinstance(active,list) or any(not isinstance(x,str) for x in active):raise ValueError('static_images must be a list of strings.')
    workflow_path=resolve(config.get('step3_workflow','step3_api.json'),project);workflow_raw=workflow_path.read_bytes();workflow=json.loads(workflow_raw.decode('utf-8-sig'))
    if not isinstance(workflow,dict) or 'nodes' in workflow:raise ValueError('Step 3 requires an API workflow.')
    defaults={}
    for key,(node_id,kind) in FIELDS.items():
        node=workflow.get(node_id)
        if not isinstance(node,dict) or node.get('class_type')!=kind or not isinstance(node.get('inputs'),dict) or 'value' not in node['inputs']:raise ValueError(key+' requires '+kind+' node '+node_id+' with inputs.value.')
        defaults[key]=node['inputs']['value']
    values=validate({**defaults,**validate(config.get('step3_parameters',{}))},True)
    relevant=json.dumps({'static_images':active,'step3_parameters':config.get('step3_parameters',{}),'step3_workflow':config.get('step3_workflow','step3_api.json')},sort_keys=True,allow_nan=False).encode()
    h=hashlib.sha256()
    for part in (str(project).encode(),relevant,str(workflow_path).encode(),workflow_raw):h.update(len(part).to_bytes(8,'big'));h.update(part)
    return project,path,raw,config,values,h.hexdigest()

def snapshot():
    project,path,raw,config,values,revision=read()
    return {'project':str(project),'config_path':str(path),'values':values,'revision':revision,'controller_active':(project/'.controller.lock').exists(),'references':static_references.listing()}

def save(values,revision,selected=None):
    values=validate(values,True)
    if not isinstance(selected,list) or any(not isinstance(x,str) for x in selected):raise ValueError('Both panels must be submitted together. Reload the GUI.')
    if not selected:raise ValueError('Keep at least one enabled reference.')
    if len(set(selected))!=len(selected):raise ValueError('Duplicate enabled references.')
    project,path,raw,config,current,expected=read();lock=project/'.controller.lock';owner='roggle_settings:'+uuid.uuid4().hex
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('Controller lock exists. Wait for processing before saving settings.')
    with os.fdopen(fd,'w') as f:f.write(owner)
    temporary=None
    try:
        project,path,raw,config,current,expected=read()
        if revision!=expected:raise ValueError('Shared settings/workflow changed externally. Reload both panels and review before saving. Neither draft was written.')
        old=config.get('static_images',[])
        for name in selected:
            try:static_references.image(name)
            except (PermissionError,FileNotFoundError):
                if name not in old:raise
        changed=selected!=old or values!=config.get('step3_parameters',{})
        backup=None
        if changed:
            config['static_images']=selected;config['step3_parameters']=values
            backup=path.with_name('config.before_static_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json');backup.write_bytes(raw)
            encoded=(json.dumps(config,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
            with tempfile.NamedTemporaryFile(dir=str(project),prefix='.config_settings_',suffix='.tmp',delete=False) as f:
                temporary=Path(f.name);f.write(encoded);f.flush();os.fsync(f.fileno())
            if path.read_bytes()!=raw:raise ValueError('Config changed during save; neither panel was written.')
            os.replace(temporary,path);temporary=None
        result=snapshot();result['saved']=changed;result['backup']=str(backup) if backup else None;result['controller_active']=False;result['references']['controller_running']=False
        return result
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
        if lock.exists() and lock.read_text()==owner:lock.unlink()
