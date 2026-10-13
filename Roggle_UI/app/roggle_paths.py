import json, os, re
from pathlib import Path, PurePosixPath
ROOT=Path(__file__).resolve().parent.parent
_fallback_noted=False

def read_config():return json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
def resolve(value,base=ROOT):
    value=os.path.expandvars(os.path.expanduser(str(value)))
    if re.search(r'%[^%]+%',value):raise ValueError('Unresolved environment variable: '+value)
    p=Path(value);return p.resolve() if p.is_absolute() else (base/p).resolve()
def project_root():
    global _fallback_noted
    c=read_config();project=resolve(c['paths'].get('viggle_auto','viggle_auto'))
    nested=ROOT/'viggle_auto'
    if not (project/'config.json').is_file() and (nested/'config.json').is_file() and (nested/'run.py').is_file():
        if not _fallback_noted:print('Configured project path is unavailable; using nested viggle_auto. Use Workspace Browse to save this project selection.',flush=True);_fallback_noted=True
        return nested.resolve()
    return project

def project_paths():
    project=project_root();linked=json.loads((project/'config.json').read_text(encoding='utf-8-sig'));lp=linked['paths'];base=resolve(lp['comfy_base'],project)
    def directory(name,default):return resolve(lp.get(name,default),project)
    def sub(name,default):
        value=str(lp.get(name,default)).replace('\\','/');p=PurePosixPath(value)
        if not value or p.is_absolute() or re.match(r'^[A-Za-z]:',value) or '..' in p.parts or not p.parts:raise ValueError('paths.'+name+' must be a relative subdirectory without ..')
        return p.as_posix()
    input_root=directory('comfy_input_directory',base/'input');output_root=directory('comfy_output_directory',base/'output');user=directory('comfy_user_directory',base/'user')
    staging_prefix=sub('comfy_staging_subdir','viggle_auto');s3=sub('step3_output_subdir','viggle_auto/step3output');s4=sub('step4_output_subdir','viggle_auto/step4output')
    def inside(root,relative):
        p=(root/relative).resolve()
        if p==root or not p.is_relative_to(root):raise PermissionError('Configured directory escapes its root: '+relative)
        return p
    prepared=(project/'step34input').resolve()
    if not prepared.is_relative_to(project):raise PermissionError('step34input resolves outside the project.')
    return {'project':project,'config':linked,'comfy_base':base,'comfy_backend':directory('comfy_backend',None),'comfy_input':input_root,'comfy_output':output_root,'comfy_user':user,
      'comfy_staging':inside(input_root,staging_prefix),'step34input':prepared,'step3output':inside(output_root,s3),'step4output':inside(output_root,s4),'step3_prefix':s3,'step4_prefix':s4}

def runtime():
    c=read_config();p=c['paths'];v=project_paths();project=v['project'];linked=v['config'];lp=linked['paths'];base=v['comfy_base'];backend=v['comfy_backend']
    resolved={'roggle_root':str(ROOT),'viggle_auto':str(project),'viggle_config':str(project/'config.json'),
      'viggle_controller':str(project/'run.py'),'viggle_launcher':str(project/'launcher.py'),
      'python_executable':str(resolve(p['python_executable'])) if p.get('python_executable') else str(resolve(lp['python_executable'],project)),
      'comfy_base':str(base),'comfy_backend':str(backend),'comfy_main':str(backend/'main.py'),
      'comfy_input':str(v['comfy_input']),'comfy_output':str(v['comfy_output']),'comfy_user':str(v['comfy_user']),'comfy_staging':str(v['comfy_staging']),
      'model_paths_config':str(resolve(lp['model_paths_config'],project)),
      'step34input':str(v['step34input']),'step3output':str(v['step3output']),'step4output':str(v['step4output']),
      'static_directory':str(project/'static'),'web_directory':str(resolve(p.get('web_directory','web'))),
      'data_directory':str(resolve(p.get('data_directory','data'))),'shots_csv':str(resolve(p.get('shots_csv','data/shots.csv'))),
      'source_video_directory':str(resolve(p['source_video_directory'])) if p.get('source_video_directory') else None}
    g=c.get('gui',{});host=g.get('host','127.0.0.1');port=g.get('port',8765)
    if host!='127.0.0.1':raise ValueError('GUI host must remain 127.0.0.1.')
    if isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535:raise ValueError('Invalid GUI port.')
    return {'config':c,'gui':{'host':host,'port':port,'open_browser':g.get('open_browser',True)},'resolved_paths':resolved,
      'pipeline':{'server':linked['server'],'startup_args':linked.get('startup_args',[]),'static_images':linked.get('static_images',[]),'step3_output_prefix':v['step3_prefix'],'step4_output_prefix':v['step4_prefix']},
      'missing_files':[k for k in ('python_executable','viggle_controller','viggle_launcher','comfy_main','model_paths_config') if not Path(resolved[k]).is_file()],
      'prototype_only':True,'production_actions_enabled':False}
