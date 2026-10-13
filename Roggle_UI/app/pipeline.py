import json, os, copy, time, queue, threading, subprocess
from pathlib import Path
from datetime import datetime
from roggle_paths import resolve, project_root, project_paths
LOCK=threading.RLock()
STATE={'running':False,'stage':None,'message':'Ready','events':[],'exit_code':None,'started_at':0,'id':0}
def status():
    with LOCK:return copy.deepcopy(STATE)
def event(message):
    print(message,flush=True)
    with LOCK:
        STATE['message']=message;STATE['events'].append(datetime.now().strftime('%H:%M:%S')+' '+message);STATE['events']=STATE['events'][-200:]
def start(stage):
    if stage not in ('step3','step4'):raise ValueError('Only Step 3 and Step 4 may be launched.')
    with LOCK:
        if STATE['running']:raise ValueError('A pipeline stage is already running.')
        project=project_root();controller=project/'run.py';config=project/'config.json'
        if not controller.is_file() or not config.is_file():raise FileNotFoundError('Linked viggle_auto must contain run.py and config.json.')
        c=json.loads(config.read_text(encoding='utf-8-sig'));python=resolve(c['paths']['python_executable'],project)
        if not python.is_file():raise FileNotFoundError('Pipeline Python not found: '+str(python))
        if (project/'.controller.lock').exists():raise ValueError('Controller lock exists. Finish/stop current processing before starting another stage.')
        workflow=c.get(stage+'_workflow')
        if not workflow or not (project/workflow).is_file():raise FileNotFoundError('Workflow not found for '+stage)
        if stage=='step3':
            images=list((project/'step34input').glob('*.png'))
            if not images:raise ValueError('No PNGs in step34input to process.')
            active=c.get('static_images',[])
            if not active:raise ValueError('Enable at least one static reference before Step 3.')
            for name in active:
                if not (project/name).is_file():raise FileNotFoundError('Enabled static reference missing: '+name)
        else:
            images=list(project_paths()['step3output'].rglob('*.png'))
            if not images:raise ValueError('No Step 3 PNGs to process.')
            for image in images:
                video=project/'step34input'/(image.parent.name+'.mp4')
                if not video.is_file():raise FileNotFoundError('Step 4 matching MP4 missing: '+str(video))
        command=[str(python),'-u',str(controller),stage];env=os.environ.copy();env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8'
        process=subprocess.Popen(command,cwd=str(project),env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ident=STATE.get('id',0)+1;STATE.clear();STATE.update({'running':True,'stage':stage,'message':'Starting '+stage,'events':[],'exit_code':None,'started_at':time.time(),'id':ident})
        event('[Pipeline] '+stage+' started using existing viggle_auto/run.py')
        worker=threading.Thread(target=monitor,args=(process,stage),daemon=False)
        try:worker.start()
        except Exception:
            process.terminate();process.wait();STATE['running']=False;raise
        return status()
def monitor(process,stage):
    lines=queue.Queue()
    def reader():
        try:
            for line in process.stdout:lines.put(line.rstrip())
        finally:lines.put(None)
    reader_thread=threading.Thread(target=reader,daemon=True);reader_thread.start();begin=time.monotonic();last=time.monotonic()
    try:
        while True:
            try:line=lines.get(timeout=1)
            except queue.Empty:
                if time.monotonic()-last>=15:event(f'[Pipeline] {stage} still running — elapsed {time.monotonic()-begin:.0f}s');last=time.monotonic()
                continue
            if line is None:break
            if line:event(line);last=time.monotonic()
        code=process.wait()
        with LOCK:STATE['exit_code']=code
        event('[Pipeline] '+stage+(' completed successfully' if code==0 else ' failed')+f' · exit code {code}')
    except Exception as exc:
        event('[Pipeline] Monitoring error: '+str(exc))
        # Never leave a live controller untracked just because GUI monitoring failed.
        if process.poll() is None:process.wait()
        with LOCK:STATE['exit_code']=process.returncode
    finally:
        reader_thread.join(timeout=2);process.stdout.close()
        with LOCK:STATE['running']=False


# Explicit backend start is independent of Step 3/4 processing status.
import urllib.request
from urllib.parse import urlsplit
BACKEND_LOCK=threading.RLock()
BACKEND={'starting':False,'project':None,'message':'Backend status not checked.'}
def backend_alive(project):
    config=json.loads((project/'config.json').read_text(encoding='utf-8-sig'))
    url=config['server'].rstrip('/')+'/system_stats'
    try:
        with urllib.request.urlopen(url,timeout=2) as response:data=json.load(response)
        return isinstance(data,dict) and ('system' in data or 'devices' in data)
    except Exception:return False

def backend_status():
    project=project_root();ready=backend_alive(project)
    with BACKEND_LOCK:
        current=BACKEND.get('project')==str(project)
        starting=bool(current and BACKEND['starting'] and not ready)
        message='ComfyUI is running.' if ready else BACKEND['message'] if current else 'ComfyUI is not responding.'
    return {'ready':ready,'starting':starting,'message':message}

def start_backend():
    project=project_root();config=json.loads((project/'config.json').read_text(encoding='utf-8-sig'))
    parsed=urlsplit(config['server'])
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Start Comfy supports the local loopback backend only.')
    with BACKEND_LOCK:
        if backend_alive(project):return {'ready':True,'starting':False,'message':'ComfyUI is already running.'}
        if BACKEND['starting'] and BACKEND.get('project')==str(project):return {'ready':False,'starting':True,'message':'ComfyUI startup is already in progress.'}
        if STATE['running'] or (project/'.controller.lock').exists():raise ValueError('Processing/controller is active; wait before manually starting the backend.')
        if os.name!='nt':raise RuntimeError('The backend BAT launcher requires Windows.')
        bat=project/'_1_start_backend.bat'
        if not bat.is_file():raise FileNotFoundError('Backend launcher not found: '+str(bat))
        process=subprocess.Popen(['cmd.exe','/c','call',str(bat)],cwd=str(project),creationflags=subprocess.CREATE_NEW_CONSOLE)
        BACKEND.update({'starting':True,'project':str(project),'message':'Starting ComfyUI; see the backend console.'})
        timeout=float(config.get('startup_timeout_seconds',600))
        monitor_thread=threading.Thread(target=watch_backend,args=(project,process,timeout),daemon=True)
        monitor_thread.start();print('[Backend] Started existing _1_start_backend.bat',flush=True)
        return {'ready':False,'starting':True,'message':BACKEND['message']}

def watch_backend(project,process,timeout):
    deadline=time.monotonic()+timeout;ready=False;message='Backend startup timed out. Check its console.'
    while time.monotonic()<deadline:
        if backend_alive(project):ready=True;message='ComfyUI is running.';break
        code=process.poll()
        if code is not None:message='Backend launcher exited before the API became ready (exit '+str(code)+'). Check its console.';break
        time.sleep(2)
    with BACKEND_LOCK:
        if BACKEND.get('project')==str(project):BACKEND.update({'starting':False,'message':message})
    print('[Backend] '+message,flush=True)
