from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote
import json, os, re, mimetypes, webbrowser, subprocess, base64, secrets, threading, sys
from roggle_paths import ROOT, read_config, resolve, runtime
import static_references
import prepare as prepare_jobs
import review
import pipeline
import jobs
from explorer import open_folder as open_explorer_folder
import step3_settings
TOKEN=secrets.token_urlsafe(32)
UPDATE_LOCK=threading.Lock()
VIDEO_EXTENSIONS={'.mp4','.mov','.webm','.mkv','.avi','.m4v','.mpeg','.mpg'}
def disconnected(exc):
    return isinstance(exc,ConnectionError) or (isinstance(exc,OSError) and (getattr(exc,'winerror',None) in (10053,10054,10058) or exc.errno in (32,54,104)))
def source_path(relative=''):
    value=read_config()['paths'].get('source_video_directory')
    if not value:raise ValueError('Click Browse beside Source video folder to choose footage.')
    root=resolve(value)
    if not root.is_dir():raise FileNotFoundError('Footage folder does not exist: '+str(root))
    rel=Path(relative)
    if rel.is_absolute():raise PermissionError('Only relative footage paths are allowed.')
    p=(root/rel).resolve()
    if not p.is_relative_to(root):raise PermissionError('Path is outside configured footage folder.')
    return root,p
def native_picker(kind,initial):
    if os.name!='nt':raise RuntimeError('Native dialogs require Windows.')
    script=r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner=New-Object System.Windows.Forms.Form
$owner.TopMost=$true; $owner.ShowInTaskbar=$false; $owner.Opacity=0; $owner.Width=1; $owner.Height=1
$owner.Show(); $owner.Activate()
try {
 if ($env:ROGGLE_PICK_KIND -eq 'shots') {
  $dialog=New-Object System.Windows.Forms.OpenFileDialog
  $dialog.Title='Choose Roggle shot list CSV'; $dialog.Filter='CSV files (*.csv)|*.csv'; $dialog.CheckFileExists=$true
  if (Test-Path -LiteralPath $env:ROGGLE_PICK_INITIAL) {$dialog.InitialDirectory=Split-Path -Parent $env:ROGGLE_PICK_INITIAL}
  if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {$value=$dialog.FileName} else {$value=$null}
 } else {
  $dialog=New-Object System.Windows.Forms.FolderBrowserDialog
  $dialog.Description=if ($env:ROGGLE_PICK_KIND -eq 'project') {'Choose existing viggle_auto project'} else {'Choose source footage folder'}
  $dialog.ShowNewFolderButton=$false
  if (Test-Path -LiteralPath $env:ROGGLE_PICK_INITIAL -PathType Container) {$dialog.SelectedPath=$env:ROGGLE_PICK_INITIAL}
  if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {$value=$dialog.SelectedPath} else {$value=$null}
 }
 @{path=$value} | ConvertTo-Json -Compress
} finally {if ($dialog) {$dialog.Dispose()};$owner.Close();$owner.Dispose()}
'''
    env=os.environ.copy();env['ROGGLE_PICK_KIND']=kind;env['ROGGLE_PICK_INITIAL']=initial or ''
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-EncodedCommand',encoded],env=env,capture_output=True,encoding='utf-8-sig',errors='replace',timeout=180)
    if result.returncode:raise RuntimeError('Picker failed: '+(result.stderr.strip() or 'PowerShell error'))
    return json.loads(result.stdout.strip())['path']
def save_selection(kind,value):
    p=Path(value).resolve();c=read_config()
    if kind=='project':
        if not p.is_dir() or not (p/'run.py').is_file() or not (p/'config.json').is_file():raise ValueError('Choose viggle_auto containing run.py and config.json.')
        linked=json.loads((p/'config.json').read_text(encoding='utf-8-sig'))
        for key in ('comfy_base','comfy_backend','python_executable','model_paths_config'):
            if not linked.get('paths',{}).get(key):raise ValueError('Project lacks paths.'+key)
        if not linked.get('server'):raise ValueError('Project lacks server setting.')
        field='viggle_auto'
    elif kind=='source':
        if not p.is_dir():raise ValueError('Select a footage directory.')
        field='source_video_directory'
    elif kind=='shots':
        if not p.is_file() or p.suffix.lower()!='.csv':raise ValueError('Select an existing CSV.')
        field='shots_csv'
    else:raise ValueError('Unknown picker type.')
    config=ROOT/'config.json';backup=ROOT/'config.before_browse.json'
    if not backup.exists():backup.write_bytes(config.read_bytes())
    c.setdefault('paths',{})[field]=p.as_posix();temp=ROOT/'config.json.tmp';temp.write_text(json.dumps(c,indent=2)+'\n',encoding='utf-8');temp.replace(config)
    return str(p)
class Server(ThreadingHTTPServer):
    def handle_error(self,request,client_address):
        exc=sys.exc_info()[1]
        if disconnected(exc):return
        print('Roggle request error: '+str(exc),file=sys.stderr,flush=True)
        if read_config().get('logging',{}).get('debug',False):super().handle_error(request,client_address)
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        self.response_started=False;super().__init__(*args,directory=args[2].web_directory,**kwargs)
    def send_response(self,*args,**kwargs):self.response_started=True;super().send_response(*args,**kwargs)
    def log_message(self,format,*args):
        if read_config().get('logging',{}).get('verbose_requests',False):super().log_message(format,*args)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');super().end_headers()
    def json_response(self,data,status=200):
        raw=json.dumps(data).encode('utf-8');self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def handle(self):
        try:super().handle()
        except OSError as e:
            if not disconnected(e):raise
    def report(self,e):
        if disconnected(e):return
        if self.response_started:print('Roggle streaming error: '+str(e),file=sys.stderr,flush=True);return
        status=403 if isinstance(e,PermissionError) else 404 if isinstance(e,FileNotFoundError) else 400
        try:self.json_response({'error':str(e)},status)
        except OSError as exc:
            if not disconnected(exc):raise
    def do_POST(self):
        self.response_started=False
        try:
            expected=f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Origin')!=expected or self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':raise PermissionError('Only same-origin local requests accepted.')
            path=urlsplit(self.path).path
            if path not in ('/api/browse','/api/static/save','/api/static/open','/api/shots/save','/api/prepare/start','/api/review/open','/api/pipeline/start','/api/jobs/clear','/api/backend/start','/api/project/open','/api/csv/open','/api/step3/settings/save'):self.json_response({'error':'Unknown endpoint'},404);return
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise PermissionError('JSON required.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024*1024:raise ValueError('Invalid request size.')
            data=json.loads(self.rfile.read(length))
            if data.get('token')!=TOKEN:raise PermissionError('Reload GUI before making changes.')
            if not UPDATE_LOCK.acquire(blocking=False):self.json_response({'error':'Another selection/update is active.'},409);return
            try:
                if path=='/api/project/open':self.json_response(open_explorer_folder(resolve(read_config()['paths']['viggle_auto'])));return
                if path=='/api/csv/open':self.json_response(open_explorer_folder(prepare_jobs.csv_path().parent));return
                if path=='/api/backend/start':self.json_response(pipeline.start_backend());return
                if path=='/api/review/open':self.json_response(review.open_folder(data.get('stage'),data.get('folder','')));return
                if prepare_jobs.progress()['running'] or pipeline.status()['running']:raise ValueError('Processing is running; config/shot/state edits and other stages are locked.')
                if path=='/api/step3/settings/save':self.json_response(step3_settings.save(data.get('values'),data.get('revision'),data.get('selected')));return
                if path=='/api/jobs/clear':self.json_response(jobs.clear(data.get('mode'),data.get('keys'),data.get('revision')));return
                if path=='/api/pipeline/start':self.json_response(pipeline.start(data.get('stage')));return
                if path=='/api/shots/save':self.json_response(prepare_jobs.save_draft(data.get('rows'),data.get('revision'),backup=data.get('autosave') is not True));return
                if path=='/api/prepare/start':self.json_response(prepare_jobs.start(data.get('rows'),data.get('revision'),backup=data.get('autosave') is not True));return
                if path=='/api/static/save':
                    result=static_references.save(data.get('selected'),data.get('revision'));self.json_response(result)
                    if result.get('saved'):print('Roggle: static references saved to viggle_auto config.',flush=True)
                    return
                if path=='/api/static/open':self.json_response(static_references.open_folder());return
                kind=data.get('kind')
                if kind not in ('project','source','shots'):raise ValueError('Unknown picker type.')
                field={'project':'viggle_auto','source':'source_video_directory','shots':'shots_csv'}[kind];initial=read_config()['paths'].get(field)
                selected=native_picker(kind,str(resolve(initial)) if initial else '')
                if not selected:self.json_response({'cancelled':True});return
                saved=save_selection(kind,selected);self.json_response({'cancelled':False,'path':saved,'config_saved':True});print('Roggle '+kind+' selection updated: '+saved,flush=True)
            finally:UPDATE_LOCK.release()
        except Exception as e:self.report(e)
    def do_GET(self):self.route(False)
    def do_HEAD(self):self.route(True)
    def route(self,head):
        self.response_started=False;u=urlsplit(self.path);q=parse_qs(u.query)
        try:
            if u.path=='/favicon.ico':self.send_response(204);self.send_header('Content-Length','0');self.end_headers();return
            if u.path=='/api/config':r=runtime();r['picker_token']=TOKEN;self.json_response(r);return
            if u.path=='/api/step3/settings':self.json_response(step3_settings.snapshot());return
            if u.path=='/api/jobs':self.json_response(jobs.listing());return
            if u.path=='/api/backend/status':self.json_response(pipeline.backend_status());return
            if u.path=='/api/pipeline/status':self.json_response(pipeline.status());return
            if u.path=='/api/review':self.json_response(review.listing(q.get('stage',['step2'])[0],q.get('folder',[''])[0]));return
            if u.path=='/review-media':
                stage=q.get('stage',['step2'])[0];relative=q.get('path',[''])[0];root,p=review.file(stage,relative)
                if p.suffix.lower() in review.VIDEOS:self.media(relative,head,stage)
                else:review.image_response(self,stage,relative,head)
                return
            if u.path=='/api/shots':self.json_response(prepare_jobs.snapshot());return
            if u.path=='/api/prepare/status':self.json_response(prepare_jobs.progress());return
            if u.path=='/api/health':self.json_response({'ok':True});return
            if u.path=='/api/static':self.json_response(static_references.listing());return
            if u.path=='/static-preview':static_references.preview(self,q.get('path',[''])[0],head);return
            if u.path=='/api/videos':
                root,folder=source_path(q.get('folder',[''])[0])
                if not folder.is_dir():raise FileNotFoundError('Subfolder not found.')
                entries=[]
                for p in sorted(folder.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold())):
                    try:
                        if not p.resolve().is_relative_to(root):continue
                        rel=p.relative_to(root).as_posix()
                        if p.is_dir():entries.append({'name':p.name,'relative_path':rel,'kind':'folder'})
                        elif p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS:entries.append({'name':p.name,'relative_path':rel,'kind':'video','size_bytes':p.stat().st_size,'full_path':str(p),'url':'/media?path='+quote(rel,safe='')})
                    except OSError:continue
                rel=folder.relative_to(root).as_posix();self.json_response({'root':str(root),'folder':'' if rel=='.' else rel,'entries':entries});return
            if u.path=='/media':self.media(q.get('path',[''])[0],head);return
            if u.path.startswith('/api/'):self.json_response({'error':'Unknown endpoint'},404);return
            if head:super().do_HEAD()
            else:super().do_GET()
        except Exception as e:self.report(e)
    def range_error(self,size):
        self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers()
    def media(self,relative,head,stage=None):
        root,p=review.file(stage,relative,video_only=True) if stage else source_path(relative)
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXTENSIONS:raise FileNotFoundError('Video not found.')
        with p.open('rb') as f:
            size=os.fstat(f.fileno()).st_size;start=0;end=size-1;status=200;value=self.headers.get('Range')
            if value:
                m=re.fullmatch(r'bytes=(\d*)-(\d*)',value.strip())
                if not m or not any(m.groups()) or size==0:self.range_error(size);return
                a,b=m.groups()
                if a:start=int(a);end=min(int(b) if b else size-1,size-1)
                else:start=max(0,size-int(b))
                if start>=size or start>end:self.range_error(size);return
                status=206
            self.send_response(status);mime={'.mp4':'video/mp4','.m4v':'video/mp4','.mov':'video/quicktime','.webm':'video/webm'}.get(p.suffix.lower(),mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
            self.send_header('Content-Type',mime);self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(max(0,end-start+1)))
            if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            if head:return
            f.seek(start);remaining=end-start+1
            while remaining>0:
                chunk=f.read(min(1024*1024,remaining))
                if not chunk:break
                self.wfile.write(chunk);remaining-=len(chunk)
if __name__=='__main__':
    try:
        r=runtime();g=r['gui'];web=Path(r['resolved_paths']['web_directory'])
        if not (web/'index.html').is_file():raise FileNotFoundError('Web index not found.')
        server=Server((g['host'],g['port']),Handler);server.web_directory=str(web)
    except Exception as e:raise SystemExit('Roggle UI startup error: '+str(e))
    url=f"http://{g['host']}:{g['port']}";print('Roggle UI: '+url,flush=True);print('Local-only. Routine request logs hidden. Ctrl+C stops server.',flush=True)
    if g['open_browser']:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
