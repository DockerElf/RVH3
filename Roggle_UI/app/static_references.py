import json, os, hashlib, tempfile, shutil, mimetypes
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from roggle_paths import project_root
from explorer import open_folder as open_explorer_folder
IMAGE_EXTENSIONS={'.jpg','.jpeg','.png','.webp','.gif','.bmp'}
def info():
    project=project_root();config=project/'config.json';raw=config.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
    active=data.get('static_images',[])
    if not isinstance(active,list) or any(not isinstance(x,str) for x in active):raise ValueError('static_images must be a list of strings.')
    return project,config,raw,data,hashlib.sha256(raw).hexdigest()
def image(name):
    project=project_root();folder=(project/'static').resolve();p=(project/name).resolve()
    if not folder.is_relative_to(project) or not p.is_relative_to(folder) or p==folder or p.suffix.lower() not in IMAGE_EXTENSIONS:raise PermissionError('Only supported images within the linked static folder are allowed.')
    if not p.is_file():raise FileNotFoundError('Reference not found: '+name)
    return p
def listing():
    project,config,raw,data,revision=info();folder=(project/'static').resolve()
    if not folder.is_relative_to(project):raise PermissionError('Static folder is outside project.')
    active=data.get('static_images',[]);names=set(active)
    if folder.is_dir():
        for p in folder.rglob('*'):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and p.resolve().is_relative_to(folder):names.add(p.relative_to(project).as_posix())
    ordered=list(dict.fromkeys(active))+sorted(names-set(active),key=str.casefold);items=[]
    for name in ordered:
        try:image(name);available=True;error=None
        except (PermissionError,FileNotFoundError) as e:available=False;error=str(e)
        items.append({'path':name,'enabled':name in active,'available':available,'error':error,'preview_url':'/static-preview?path='+quote(name,safe='') if available else None})
    return {'folder':str(folder),'config_path':str(config),'revision':revision,'active':active,'items':items,'controller_running':(project/'.controller.lock').exists()}
def save(selected,revision):
    if not isinstance(selected,list) or any(not isinstance(x,str) for x in selected):raise ValueError('Selected references must be a list of strings.')
    if len(set(selected))!=len(selected):raise ValueError('Duplicate references.')
    if not selected:raise ValueError('Keep at least one enabled reference; Step 3 rejects an empty list.')
    project,config,raw,data,current=info()
    if current!=revision:raise ValueError('Pipeline config changed. Refresh references and review choices.')
    if (project/'.controller.lock').exists():raise ValueError('Controller lock exists. Stop/wait for viggle_auto before saving.')
    old=data.get('static_images',[])
    for name in selected:
        try:image(name)
        except (PermissionError,FileNotFoundError):
            if name not in old:raise
    if selected==old:return {'saved':False,'unchanged':True}
    data['static_images']=selected;backup=config.with_name('config.before_static_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json');backup.write_bytes(raw)
    fd,temp=tempfile.mkstemp(prefix='.config_static_',suffix='.tmp',dir=str(project))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        if config.read_bytes()!=raw:raise ValueError('Config changed during save. Refresh and retry.')
        if (project/'.controller.lock').exists():raise ValueError('Controller started during save; change cancelled.')
        os.replace(temp,config)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'saved':True,'backup':str(backup),'static_images':selected}
def preview(handler,name,head=False):
    p=image(name);handler.send_response(200);handler.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
    handler.send_header('Cache-Control','no-cache');handler.send_header('Content-Length',str(p.stat().st_size));handler.end_headers()
    if not head:
        with p.open('rb') as f:shutil.copyfileobj(f,handler.wfile,1024*1024)
def open_folder():
    project=project_root();folder=(project/'static').resolve()
    if not folder.is_relative_to(project) or not folder.is_dir():raise FileNotFoundError('Linked static folder is missing or outside the project.')
    return open_explorer_folder(folder)
