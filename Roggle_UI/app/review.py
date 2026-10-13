from pathlib import Path
from urllib.parse import quote
import os, mimetypes, shutil
from roggle_paths import project_paths
from explorer import open_folder as open_explorer_folder
STAGES={'step2':'step34input','step3':'step3output','step4':'step4output'}
VIDEOS={'.mp4','.mov','.webm','.mkv','.avi','.m4v','.mpeg','.mpg'}
IMAGES={'.png','.jpg','.jpeg','.webp','.gif','.bmp'}
def location(stage,relative=''):
    if stage not in STAGES:raise ValueError('Unknown review stage.')
    root=project_paths()[STAGES[stage]].resolve();rel=Path(relative)
    if rel.is_absolute():raise PermissionError('Only relative review paths allowed.')
    target=(root/rel).resolve()
    if not target.is_relative_to(root):raise PermissionError('Review path is outside stage folder.')
    return root,target

def listing(stage,relative=''):
    root,folder=location(stage,relative)
    if not root.exists():return {'stage':stage,'root':str(root),'folder':'','missing':True,'entries':[]}
    if not folder.is_dir():raise FileNotFoundError('Review subfolder not found.')
    entries=[]
    for p in sorted(folder.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold())):
        try:
            if p.name.startswith('.') or not p.resolve().is_relative_to(root):continue
            rel=p.relative_to(root).as_posix()
            if p.is_dir():entries.append({'kind':'folder','name':p.name,'relative_path':rel});continue
            ext=p.suffix.lower()
            if not p.is_file() or ext not in VIDEOS|IMAGES:continue
            entries.append({'kind':'video' if ext in VIDEOS else 'image','name':p.name,'relative_path':rel,'size_bytes':p.stat().st_size,
                'url':'/review-media?stage='+stage+'&path='+quote(rel,safe='')})
        except OSError:continue
    rel=folder.relative_to(root).as_posix()
    return {'stage':stage,'root':str(root),'folder':'' if rel=='.' else rel,'missing':False,'entries':entries}
def file(stage,relative,video_only=False):
    root,p=location(stage,relative)
    if not p.is_file() or p.suffix.lower() not in (VIDEOS if video_only else VIDEOS|IMAGES):raise FileNotFoundError('Supported review file not found.')
    return root,p

def image_response(handler,stage,relative,head=False):
    root,p=file(stage,relative)
    if p.suffix.lower() not in IMAGES:raise ValueError('Expected review image.')
    with p.open('rb') as f:
        size=os.fstat(f.fileno()).st_size;handler.send_response(200)
        handler.send_header('Content-Type',mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
        handler.send_header('Content-Length',str(size));handler.send_header('Cache-Control','no-cache');handler.end_headers()
        if not head:shutil.copyfileobj(f,handler.wfile,1024*1024)
def open_folder(stage,relative=''):
    root,p=location(stage,relative)
    if not p.is_dir():raise FileNotFoundError('Result folder does not exist yet.')
    return open_explorer_folder(p)
