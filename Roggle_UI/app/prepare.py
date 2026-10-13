import csv, io, json, os, re, shutil, subprocess, tempfile, threading, hashlib, uuid, copy, time, queue
from pathlib import Path
from datetime import datetime
from roggle_paths import ROOT, read_config, resolve, project_root
FIELDS=['id','target','timestamp','duration','screenshot_delta','width','height','status','path','error']
LOCK=threading.RLock()
JOB={'running':False,'message':'Ready','done':0,'total':0,'errors':[]}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def time_seconds(value):
    s=str(value).strip()
    parts=s.split(':')
    if len(parts) not in (2,3) or any(not re.fullmatch(r'\d+',p) for p in parts):raise ValueError('Use MM:SS or HH:MM:SS, with whole seconds.')
    nums=list(map(int,parts));h,m,sec=nums if len(nums)==3 else [0,*nums]
    if m>=60 or sec>=60 or h>99:raise ValueError('Time must have hours 0–99 and minutes/seconds 0–59.')
    return h*3600+m*60+sec
def clock(seconds):
    n=int(seconds);return f'{n//3600:02}:{n//60%60:02}:{n%60:02}'
def defaults():
    c=read_config();d=c.get('shot_defaults',{})
    return {'duration':str(d.get('duration_seconds',10)),'screenshot_delta':d.get('screenshot_delta','00:00:00'),'width':str(d.get('width',1344)),'height':str(d.get('height',768))}
def csv_path():
    c=read_config();return resolve(c['paths'].get('shots_csv') or str(Path(c['paths'].get('data_directory','data'))/'shots.csv'))
def snapshot():
    p=csv_path();raw=p.read_bytes() if p.exists() else b'';rows=[];d=defaults()
    if raw:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if not reader.fieldnames:raise ValueError('CSV header is missing.')
        for index,r in enumerate(reader):
            if not any(v for v in r.values() if isinstance(v,str)):continue
            path=r.get('path') or r.get('file') or ''
            target=r.get('target') or re.sub(r'[_\s]+','',Path(path).stem)
            rows.append({'id':r.get('id') or str(uuid.uuid5(uuid.NAMESPACE_URL,str(p)+':'+str(index))),
              'target':target,'timestamp':r.get('timestamp') or r.get('time') or '00:00:00',
              'duration':r.get('duration') or d['duration'],'screenshot_delta':r.get('screenshot_delta') or d['screenshot_delta'],
              'width':r.get('width') or d['width'],'height':r.get('height') or d['height'],
              'status':r.get('status') or 'open','path':path,'error':r.get('error') or ''})
    c=read_config();return {'rows':rows,'revision':digest(raw),'csv_path':str(p),'defaults':d,
      'ffmpeg_executable':'ffmpeg','running':JOB['running']}
def normalize(rows):
    if not isinstance(rows,list) or len(rows)>10000:raise ValueError('Shot list must be an array with at most 10000 rows.')
    result=[];ids=set();names=set();d=defaults()
    for index,r in enumerate(rows):
        if not isinstance(r,dict):raise ValueError('Invalid shot row.')
        row={k:str(r.get(k,'')) for k in FIELDS};row['id']=row['id'] or str(uuid.uuid4())
        if row['id'] in ids:raise ValueError('Duplicate shot ID.')
        ids.add(row['id']);target=row['target'].strip()
        if not re.fullmatch(r'[^_\s\\/:*?"<>|]+',target) or len(target)>80 or target.endswith('.') or target in ('.','..'):raise ValueError(f'Row {index+1}: target cannot contain spaces, underscores, or Windows filename characters.')
        row['target']=target
        row['timestamp']=clock(time_seconds(row['timestamp']))
        row['screenshot_delta']=clock(time_seconds(row['screenshot_delta'] or '00:00:00'))
        try:duration=float(row['duration'] or d['duration'])
        except ValueError:raise ValueError(f'Row {index+1}: invalid duration.')
        if not 0<duration<=86400:raise ValueError(f'Row {index+1}: duration must be positive and at most 86400 seconds.')
        if time_seconds(row['screenshot_delta'])>=duration:raise ValueError(f'Row {index+1}: Screenshot Delta must be smaller than duration.')
        row['duration']=format(duration,'.9g')
        for k in ('width','height'):
            value=row[k] or d[k]
            if not value.isdigit() or not 2<=int(value)<=16384 or int(value)%2:raise ValueError(f'Row {index+1}: {k} must be a positive even pixel size (2–16384).')
            row[k]=str(int(value))
        row['status']=row['status'].lower()
        if row['status'] not in ('open','complete'):raise ValueError(f'Row {index+1}: status must be open or complete.')
        name=(target+'_'+row['timestamp'].replace(':','-')).casefold()
        if name in names:raise ValueError(f'Row {index+1}: duplicate output filename. Change the target or timestamp.')
        names.add(name);result.append(row)
    return result

def write_csv(rows,expected,backup=True,path=None):
    p=path or csv_path();raw=p.read_bytes() if p.exists() else b''
    if digest(raw)!=expected:raise ValueError('CSV changed on disk. Reload it before saving; no changes written.')
    p.parent.mkdir(parents=True,exist_ok=True)
    if backup and raw:p.with_name(p.stem+'.before_save_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+p.suffix).write_bytes(raw)
    buffer=io.StringIO(newline='');w=csv.DictWriter(buffer,fieldnames=FIELDS);w.writeheader();w.writerows(rows);data=buffer.getvalue().encode('utf-8-sig')
    fd,temp=tempfile.mkstemp(prefix='.shots_',suffix='.tmp',dir=str(p.parent))
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        if (p.read_bytes() if p.exists() else b'')!=raw:raise ValueError('CSV changed during save.')
        os.replace(temp,p)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return digest(data)
def safe_status(rows):
    old={r['id']:r for r in snapshot()['rows']}
    for row in rows:
        previous=old.get(row['id'])
        if row['status']=='complete' and (not previous or previous['status']!='complete' or any(row[k]!=str(previous[k]) for k in ('target','timestamp','duration','screenshot_delta','width','height','path'))):row['status']='open'
    return rows
def save_draft(rows,revision,backup=True):
    with LOCK:
        if JOB['running']:raise ValueError('Prepare is running; shot edits are locked.')
        rows=safe_status(normalize(rows));write_csv(rows,revision,backup=backup);return snapshot()
def tools():
    for name in ('ffmpeg','ffprobe'):
        if not shutil.which(name):raise FileNotFoundError(name+' is not on PATH. Add it to PATH and restart the GUI launcher.')
    return 'ffmpeg','ffprobe'
def event(message,update_message=True):
    print(message,flush=True)
    with LOCK:
        JOB.setdefault('events',[]).append(datetime.now().strftime('%H:%M:%S')+' '+message)
        JOB['events']=JOB['events'][-200:]
        if update_message:JOB['message']=message
def run_command(command,timeout,stage=None,expected=None):
    if stage is None:
        r=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode:raise RuntimeError(r.stderr.strip()[-6000:] or 'FFmpeg command failed.')
        return r.stdout
    event('[FFmpeg] '+stage+' started');command=[command[0],'-progress','pipe:1','-stats_period','2','-nostats']+command[1:]
    with tempfile.TemporaryFile() as stderr:
        p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        lines=queue.Queue()
        def reader():
            for line in p.stdout:lines.put(line.strip())
            lines.put(None)
        thread=threading.Thread(target=reader,daemon=True);thread.start();begin=time.monotonic();last=begin;values={}
        try:
            while True:
                if time.monotonic()-begin>timeout:raise RuntimeError(stage+' exceeded configured timeout.')
                try:line=lines.get(timeout=.25)
                except queue.Empty:
                    if time.monotonic()-last>=5:event(f'[FFmpeg] {stage} working — elapsed {time.monotonic()-begin:.0f}s');last=time.monotonic()
                    continue
                if line is None:break
                key,sep,value=line.partition('=')
                if sep:values[key]=value
                if key=='progress' and time.monotonic()-last>=2:
                    pos=values.get('out_time','?');percent=''
                    if expected and pos!='?':
                        try:
                            h,m,s=map(float,pos.split(':'));percent=f' · {min(100,(h*3600+m*60+s)/expected*100):.0f}%'
                        except ValueError:pass
                    event(f'[FFmpeg] {stage}: encoded {pos}{percent} · elapsed {time.monotonic()-begin:.0f}s');last=time.monotonic()
            p.wait(timeout=max(1,timeout-(time.monotonic()-begin)))
            if p.returncode:stderr.seek(0);raise RuntimeError(stderr.read().decode('utf-8',errors='replace').strip()[-6000:] or stage+' failed.')
        except Exception:
            if p.poll() is None:p.kill()
            p.wait();raise
        finally:thread.join(timeout=2);p.stdout.close()
    event('[FFmpeg] '+stage+f' finished ({time.monotonic()-begin:.1f}s)');return ''
def has_audio(probe,path):
    data=json.loads(run_command([probe,'-v','error','-select_streams','a','-show_entries','stream=index','-of','json',str(path)],60))
    return bool(data.get('streams',[]))

def probe_file(probe,p):
    data=json.loads(run_command([probe,'-v','error','-show_streams','-show_format','-of','json',str(p)],60));videos=[s for s in data.get('streams',[]) if s.get('codec_type')=='video']
    if not videos:raise ValueError('No video/image stream found: '+str(p))
    stream=videos[0];duration=data.get('format',{}).get('duration') or stream.get('duration')
    return stream,float(duration) if duration else None

def source_for(row,root):
    p=Path(os.path.expandvars(row['path']));p=p.resolve() if p.is_absolute() else (root/p).resolve()
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('Source must be an existing file inside the configured footage root: '+row['path'])
    return p

def options():
    p=read_config().get('prepare',{});settings={'video_codec':p.get('video_codec','libx264'),'crf':p.get('crf',18),'preset':p.get('preset','medium'),
      'audio_codec':p.get('audio_codec','copy'),'audio_bitrate':p.get('audio_bitrate','192k'),'timeout_seconds':p.get('timeout_seconds',7200),
      'filename_template':p.get('filename_template','{target}_{timestamp}')}
    if settings['video_codec']!='libx264':raise ValueError('This version supports video_codec libx264.')
    if settings['audio_codec'] not in ('copy','aac','none'):raise ValueError('audio_codec must be copy, aac, or none.')
    if settings['preset'] not in ('ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'):raise ValueError('Invalid libx264 preset.')
    if not 0<=float(settings['crf'])<=51 or not 1<=float(settings['timeout_seconds'])<=86400:raise ValueError('Invalid CRF/timeout.')
    return settings

def base_name(row,settings):
    stamp=row['timestamp'].replace(':','-');name=settings['filename_template'].format(target=row['target'],timestamp=stamp)
    if not re.fullmatch(r'[^_\s\\/:*?"<>|]+_\d{2}-\d{2}-\d{2}',name):raise ValueError('filename_template must retain target_HH-MM-SS for Step 3/4 compatibility.')
    return name

def validate_clip(probe,p,row):
    if not p.is_file() or not p.stat().st_size:raise ValueError('Clip output missing or empty.')
    stream,duration=probe_file(probe,p)
    if (stream.get('width'),stream.get('height'))!=(int(row['width']),int(row['height'])):raise ValueError('Output clip dimensions do not match the row.')
    if duration is None or abs(duration-float(row['duration']))>max(.5,float(row['duration'])*.01):raise ValueError('Output clip duration differs from requested duration.')
def validate_png(probe,p):
    if not p.is_file() or p.stat().st_size<8:raise ValueError('PNG output invalid or empty.')
    with p.open('rb') as f:
        if f.read(8)!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG header invalid.')
    stream,_=probe_file(probe,p)
    if stream.get('width',0)<=0 or stream.get('height',0)<=0:raise ValueError('PNG resolution invalid.')

def repair_audio(row,mp4,settings,ffmpeg,probe):
    if has_audio(probe,mp4):return
    validate_clip(probe,mp4,row);_,duration=probe_file(probe,mp4)
    event('[Prepare] Adding silent AAC to existing clip: '+mp4.name)
    with tempfile.TemporaryDirectory(prefix='.roggle_audio_',dir=str(mp4.parent)) as td:
        repaired=Path(td)/'clip.mp4'
        command=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n','-i',str(mp4),'-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(duration),'-shortest','-movflags','+faststart',str(repaired)]
        run_command(command,float(settings['timeout_seconds']),stage='Silent audio repair',expected=duration)
        validate_clip(probe,repaired,row)
        if not has_audio(probe,repaired):raise ValueError('Silent audio repair did not create an audio stream.')
        os.replace(repaired,mp4)
    event('[Prepare] Silent audio added; video stream was copied, not re-encoded')
def prepare_row(row,source,out,settings,ffmpeg,probe):
    stem=base_name(row,settings);mp4=out/(stem+'.mp4');png=out/(stem+'.png')
    have_clip=mp4.exists();have_png=png.exists()
    if have_clip:validate_clip(probe,mp4,row)
    if have_png:validate_png(probe,png)
    if have_clip and have_png:
        repair_audio(row,mp4,settings,ffmpeg,probe);event('[Prepare] Existing PNG and MP4 ready: '+stem);return
    if source is None:raise FileNotFoundError('Original source required to create missing files.')
    start=time_seconds(row['timestamp']);delta=time_seconds(row['screenshot_delta']);duration=float(row['duration'])
    _,source_duration=probe_file(probe,source)
    if source_duration is None:raise ValueError('Cannot determine source video duration.')
    if not have_clip and start+duration>source_duration+.05:raise ValueError('Clip extends past source end.')
    if not have_png and start+delta>=source_duration:raise ValueError('Screenshot time is outside source video.')
    w,h=row['width'],row['height'];vf=f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1'
    timeout=float(settings['timeout_seconds']);created=[]
    with tempfile.TemporaryDirectory(prefix='.roggle_prepare_',dir=str(out)) as td:
        td=Path(td);p=td/'frame.png';v=td/'clip.mp4';publish=[]
        if not have_png:
            event('[Prepare] Screenshot at '+clock(start+delta)+' · source resolution')
            run_command([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n','-ss',str(start+delta),'-i',str(source),'-frames:v','1','-update','1',str(p)],timeout,stage='Screenshot');validate_png(probe,p);publish.append((p,png))
        if not have_clip:
            real_audio=has_audio(probe,source) and settings['audio_codec']!='none'
            command=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-n','-ss',str(start),'-i',str(source)]
            if not real_audio:command+=['-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000'];event('[Prepare] Source has no usable audio; generating silent AAC')
            command+=['-t',row['duration'],'-map','0:v:0','-map','0:a:0' if real_audio else '1:a:0','-vf',vf,'-c:v',settings['video_codec'],'-crf',str(settings['crf']),'-preset',settings['preset'],'-pix_fmt','yuv420p']
            codec=settings['audio_codec'] if real_audio else 'aac';command+=['-c:a',codec]
            if codec=='aac':command+=['-b:a',str(settings['audio_bitrate'])]
            if not real_audio:command+=['-shortest']
            command+=['-movflags','+faststart',str(v)]
            event('[Prepare] Clip '+row['timestamp']+' for '+row['duration']+'s · '+w+'×'+h)
            run_command(command,timeout,stage='Clip encoding',expected=duration);validate_clip(probe,v,row)
            if not has_audio(probe,v):raise ValueError('Prepared clip has no audio stream.')
            publish.append((v,mp4))
        try:
            for temp,dest in publish:
                with dest.open('xb') as f:
                    created.append(dest)
                    with temp.open('rb') as src:shutil.copyfileobj(src,f,1024*1024)
            if have_clip:repair_audio(row,mp4,settings,ffmpeg,probe)
            validate_png(probe,png);validate_clip(probe,mp4,row);event('[Prepare] PNG and MP4 ready: '+stem)
        except Exception:
            for dest in created:dest.unlink(missing_ok=True)
            raise

def progress():
    with LOCK:return copy.deepcopy(JOB)
def start(rows,revision,backup=True):
    with LOCK:
        if JOB['running']:raise ValueError('Prepare is already running.')
        rows=safe_status(normalize(rows));ffmpeg,probe=tools();settings=options();project=project_root();out=project/'step34input';work_rows=[]
        for r in rows:
            stem=base_name(r,settings);mp4=out/(stem+'.mp4');png=out/(stem+'.png')
            if r['status']=='open' or (r['status']=='complete' and mp4.is_file() and png.is_file() and not has_audio(probe,mp4)):work_rows.append(r)
        if not work_rows:raise ValueError('No open rows or existing no-audio clips need work.')
        csvfile=csv_path();root_value=read_config()['paths'].get('source_video_directory');source_root=resolve(root_value) if root_value else None;sources={}
        for r in work_rows:
            stem=base_name(r,settings)
            if (out/(stem+'.png')).is_file() and (out/(stem+'.mp4')).is_file():sources[r['id']]=None
            else:
                if source_root is None:raise ValueError('Choose a footage folder to create missing files.')
                sources[r['id']]=source_for(r,source_root)
        token=uuid.uuid4().hex;controller_lock=project/'.controller.lock'
        try:fd=os.open(controller_lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise ValueError('viggle_auto controller lock exists. Finish/stop that run before Prepare.')
        with os.fdopen(fd,'w') as f:f.write('roggle_prepare:'+token)
        try:
            revision=write_csv(rows,revision,backup=backup,path=csvfile);out.mkdir(parents=True,exist_ok=True)
            JOB.clear();JOB.update({'running':True,'message':'Starting Prepare','done':0,'total':len(work_rows),'errors':[],'rows':copy.deepcopy(rows),'revision':revision,'csv_path':str(csvfile),'events':[],'started_at':time.time()})
            worker=threading.Thread(target=work,args=(rows,sources,csvfile,revision,out,settings,ffmpeg,probe,controller_lock,token),daemon=False);worker.start()
        except Exception:
            controller_lock.unlink(missing_ok=True);JOB['running']=False;raise
        return progress()
def work(rows,sources,csvfile,revision,out,settings,ffmpeg,probe,controller_lock,token):
    try:
        event('[Prepare] Starting '+str(JOB['total'])+' rows/audio repairs → '+str(out))
        for row in rows:
            if row['id'] not in sources:continue
            event('[Prepare '+str(JOB['done']+1)+'/'+str(JOB['total'])+'] '+row['target']+' at '+row['timestamp'])
            try:
                prepare_row(row,sources[row['id']],out,settings,ffmpeg,probe);row['status']='complete';row['error']=''
                with LOCK:JOB['last_result']=base_name(row,settings)+'.mp4'
            except Exception as e:
                row['status']='open';row['error']=str(e)[-6000:];event('[Prepare] FAILED '+row['target']+': '+row['error'])
            try:revision=write_csv(rows,revision,backup=False,path=csvfile)
            except Exception as e:
                with LOCK:JOB['errors'].append('CSV update failed: '+str(e));JOB['message']='Stopped: CSV changed or could not be saved.'
                break
            event('[Prepare] CSV status: '+row['status']+' · '+row['target'],False)
            with LOCK:
                JOB['done']+=1;JOB['rows']=copy.deepcopy(rows);JOB['revision']=revision
                if row['error']:JOB['errors'].append(row['target']+': '+row['error'])
        with LOCK:
            if JOB['done']==JOB['total']:JOB['message']='Prepare finished'+(' with errors' if JOB['errors'] else ' successfully')
        event('[Prepare] '+JOB['message'],False)
    except Exception as e:
        with LOCK:JOB['errors'].append(str(e));JOB['message']='Prepare failed'
    finally:
        try:
            if controller_lock.exists() and controller_lock.read_text()=='roggle_prepare:'+token:controller_lock.unlink()
        except OSError as e:
            with LOCK:JOB['errors'].append('Could not remove controller lock: '+str(e))
        finally:
            with LOCK:JOB['running']=False
