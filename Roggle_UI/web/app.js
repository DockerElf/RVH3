const $=s=>document.querySelector(s);let currentName="",objectURL=null,selected=0,currentPath="",libraryEntries=[],currentFolder="",pickerToken="",pickerBusy=false;
let shots=[],csvRevision="",shotDirty=false,preparing=false,prepareTimer=null,shotsLoaded=false;
function toast(text){$("#toast").textContent=text;$("#toast").style.display="block";$("#activity").textContent=text;clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$("#toast").style.display="none",4500)}
function clock(t,ms=false){t=Math.max(0,Number(t)||0);const whole=Math.floor(t);return [Math.floor(whole/3600),Math.floor(whole/60)%60,whole%60].map(n=>String(n).padStart(2,"0")).join(":")+(ms?"."+String(Math.floor((t-whole)*1000)).padStart(3,"0"):"")}
function markDirty(){shotDirty=true;$('#csvstate').textContent='Unsaved shot changes';$('#activity').textContent='Shot edited · Save CSV or Prepare to persist'}
function newShot(timestamp='00:00:00'){
 return {id:crypto.randomUUID(),target:$('#target').value||'NewShot',timestamp,duration:$('#duration').value,screenshot_delta:$('#delta').value||'00:00:00',width:$('#width').value,height:$('#height').value,status:'open',path:currentPath||'',error:''};
}
function render(){
 const body=$('#rows');body.replaceChildren();
 shots.forEach((shot,i)=>{const tr=document.createElement('tr');if(i===selected)tr.classList.add('chosen');if(shot.error)tr.classList.add('shot-error');tr.title=shot.error||'';
 ['target','timestamp','duration','screenshot_delta','width','height'].forEach(key=>{const td=document.createElement('td'),input=document.createElement('input');input.value=shot[key]??'';input.disabled=preparing;input.dataset.field=key;input.className=['timestamp','screenshot_delta'].includes(key)?'shot-time':['duration','width','height'].includes(key)?'shot-number':'shot-target';if(input.className==='shot-time')input.maxLength=8;
 input.oninput=()=>{shot[key]=input.value;shot.status='open';shot.error='';markDirty();tr.querySelector('[data-status]').textContent='open'};td.append(input);tr.append(td)});
 const status=document.createElement('td');status.dataset.status='';status.textContent=shot.status;tr.append(status);
 tr.onclick=()=>{selected=i;body.querySelectorAll('tr').forEach((r,j)=>r.classList.toggle('chosen',i===j));$('#original').value=shot.path;$('#shoterror').textContent=shot.error||''};
 const td=document.createElement('td'),del=document.createElement('button');del.textContent='×';del.disabled=preparing;del.onclick=e=>{e.stopPropagation();shots.splice(i,1);selected=Math.max(0,Math.min(selected,shots.length-1));markDirty();render()};td.append(del);tr.append(td);body.append(tr)
 });$('#rowcount').textContent=shots.length+' shots';$('#original').value=shots[selected]?.path||'';$('#original').disabled=preparing;$('#shoterror').textContent=shots[selected]?.error||'';
}
$('#original').oninput=()=>{if(shots[selected]){shots[selected].path=$('#original').value;shots[selected].status='open';shots[selected].error='';markDirty()}};
$('#add').onclick=()=>{if(preparing)return;shots.push(newShot());selected=shots.length-1;markDirty();render()};
async function postAPI(path,extra){
 const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:pickerToken,...extra})});const result=await response.json();if(!response.ok)throw new Error(result.error);return result;
}
async function loadShots(force=false){
 if(preparing&&!force)return;if(shotDirty&&!force&&!confirm('Discard unsaved shot edits and reload CSV?'))return;
 const response=await fetch('/api/shots',{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error);
 shots=data.rows;csvRevision=data.revision;shotDirty=false;shotsLoaded=true;$('#shotsfile').value=data.csv_path;$('#csvstate').textContent='Loaded '+shots.length+' rows';render();
}
$('#reloadshots').onclick=()=>loadShots().catch(e=>toast(e.message));
$('#saveshots').onclick=async()=>{try{const result=await postAPI('/api/shots/save',{rows:shots,revision:csvRevision});shots=result.rows;csvRevision=result.revision;shotDirty=false;$('#csvstate').textContent='Saved to CSV';render();toast('Shot list saved')}catch(e){toast('Save failed: '+e.message)}};
function setPreparing(value){
 preparing=value;document.body.classList.toggle('preparing',value);
 ['prepare','runstep3','runstep4','add','timestamp','saveshots','reloadshots','browseproject','browsesource','browseshots'].forEach(id=>$('#'+id).disabled=value);render();
}
async function pollPrepare(){
 try{const response=await fetch('/api/prepare/status',{cache:'no-store'});const job=await response.json();if(!response.ok)throw new Error(job.error);
 if(job.events)showProcessingLog(job.events);
 if(job.done!==window.lastReviewedPrepareCount){window.lastReviewedPrepareCount=job.done;if(window.refreshStep2Results)await window.refreshStep2Results(job.last_result||null);}
 $('#preparestatus').textContent=job.message+' · '+job.done+'/'+job.total+(job.errors.length?'\n'+job.errors.join('\n'):'');
 if(job.rows){shots=job.rows;csvRevision=job.revision;shotDirty=false;render()}
 if(job.running){setPreparing(true);prepareTimer=setTimeout(pollPrepare,1000)}else{setPreparing(false);if(job.rows)await loadShots(true);$('#csvstate').textContent=job.errors.length?'Prepare finished with errors; failed rows remain open':'CSV saved';}
 }catch(e){toast('Progress check failed: '+e.message);prepareTimer=setTimeout(pollPrepare,2000)}
}
$('#prepare').onclick=async()=>{
 const n=shots.filter(s=>s.status==='open').length;if(!n)return toast('No open rows to prepare.');
 if(!confirm('Save this CSV and prepare '+n+' open rows?\n\nOutputs go directly to the linked viggle_auto/step34input. Existing PNG/MP4 files will be kept and checked; only missing files will be created. Successful rows become complete.'))return;
 try{await postAPI('/api/prepare/start',{rows:shots,revision:csvRevision});shotDirty=false;setPreparing(true);window.lastReviewedPrepareCount=-1;if(window.beginStep2Review)await window.beginStep2Review();await pollPrepare()}catch(e){toast('Prepare could not start: '+e.message)}
};
function showProcessingLog(events){const log=$('#preparelog');const stick=log.scrollTop+log.clientHeight>=log.scrollHeight-30;log.textContent=events.join('\n');if(stick)log.scrollTop=log.scrollHeight;}
let pipelineTimer=null;
async function pollPipeline(){
 try{const response=await fetch('/api/pipeline/status',{cache:'no-store'});const job=await response.json();if(!response.ok)throw new Error(job.error);
 showProcessingLog(job.events||[]);$('#preparestatus').textContent=job.message;
 if(window.refreshStageResults&&job.stage)await window.refreshStageResults(job.stage);
 if(job.running){setPreparing(true);pipelineTimer=setTimeout(pollPipeline,3000)}else{setPreparing(false);toast(job.exit_code===0?'Pipeline '+job.stage+' completed':'Pipeline '+job.stage+' ended · check Processing activity');}
 }catch(e){toast('Pipeline progress check failed: '+e.message);pipelineTimer=setTimeout(pollPipeline,2000)}
}
async function runPipeline(stage){
 if(preparing)return;
 if(stage==='step3'&&window.staticReferencesDirty?.())return toast('Save or discard unsaved static-reference changes before Step 3.');
 const scope=stage==='step3'?'ALL eligible main PNGs in step34input, using the enabled references saved in viggle_auto/config.json':'ALL eligible Step 3 PNGs in step3output and its subfolders, paired with their MP4s in step34input';
 if(!confirm('Run '+stage.toUpperCase()+' through your existing viggle_auto controller?\n\nThis processes '+scope+'.\n\nThe controller may start ComfyUI if needed. CSV status is not changed.'+(shotDirty?'\n\nUnsaved shot edits do not affect these existing stage files.':'')))return;
 try{const job=await postAPI('/api/pipeline/start',{stage});setPreparing(true);if(window.beginStageReview)await window.beginStageReview(stage);await pollPipeline()}
 catch(e){toast('Stage could not start: '+e.message)}
}
$('#runstep3').onclick=()=>runPipeline('step3');$('#runstep4').onclick=()=>runPipeline('step4');
window.addEventListener('beforeunload',e=>{if(shotDirty||preparing){e.preventDefault();e.returnValue=''}});
document.querySelectorAll("[data-demo]").forEach(b=>b.onclick=()=>toast(b.dataset.demo));
function renderLibrary(){
 const list=$('#library');list.replaceChildren();const filter=$('#search').value.toLowerCase();
 libraryEntries.filter(e=>e.name.toLowerCase().includes(filter)).forEach(entry=>{
  const button=document.createElement('button');button.className='file';const icon=document.createElement('span');icon.textContent=entry.kind==='folder'?'📁':'▶';
  const label=document.createElement('div');label.textContent=entry.name;const detail=document.createElement('small');detail.textContent=entry.kind==='folder'?'Folder':(entry.size_bytes/1048576).toFixed(1)+' MB';label.append(detail);button.append(icon,label);
  button.onclick=()=>entry.kind==='folder'?loadLibrary(entry.relative_path):openLibraryVideo(entry,button);list.append(button);
 });$('#librarycount').textContent=libraryEntries.filter(e=>e.kind==='video').length+' FILES';
}
async function loadLibrary(folder=''){
 $('#librarystatus').textContent='Loading folder…';
 try{const response=await fetch('/api/videos?folder='+encodeURIComponent(folder),{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error);
 currentFolder=data.folder;libraryEntries=data.entries;$('#foldername').textContent=currentFolder||'Footage root';$('#folderup').disabled=!currentFolder;$('#sourcefolder').value=data.root;
 $('#librarystatus').textContent=libraryEntries.length?'Choose a folder or video.':'No supported videos or subfolders here.';renderLibrary();
 }catch(e){libraryEntries=[];renderLibrary();$('#librarystatus').textContent=e.message}
}
function openLibraryVideo(entry,button){
 if(window.showSourceReview)window.showSourceReview();
 video.pause();if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null}
 currentName=entry.name;currentPath=entry.full_path;video.src=entry.url;video.load();$('#empty').style.display='none';$('#clipname').textContent=entry.name;
 $('#target').value=entry.name.replace(/\.[^.]+$/,'').replace(/[_\s]/g,'');document.querySelectorAll('.file').forEach(b=>b.classList.toggle('active',b===button));toast('Video loaded locally · press Play');
}
$('#search').oninput=renderLibrary;$('#refreshvideos').onclick=()=>loadLibrary(currentFolder);$('#folderup').onclick=()=>loadLibrary(currentFolder.split('/').slice(0,-1).join('/'));
async function browse(kind){
 if(pickerBusy||preparing)return;
 if(kind==='shots'&&shotDirty&&!confirm('Changing CSV discards unsaved shot edits. Continue?'))return;
 if(kind==='project'&&window.staticReferencesDirty?.()&&!confirm('Changing project discards unsaved reference choices. Continue?'))return;
 pickerBusy=true;const buttons=[$('#browseproject'),$('#browsesource'),$('#browseshots')];buttons.forEach(b=>b.disabled=true);toast('Opening Windows selection dialog…');
 try{const response=await fetch('/api/browse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,token:pickerToken})});const result=await response.json();if(!response.ok)throw new Error(result.error);
 if(result.cancelled){toast('Selection cancelled · no changes saved');return}
 if(kind==='source'){video.pause();video.removeAttribute('src');video.load();currentPath='';currentName='';$('#empty').style.display='block';$('#clipname').textContent='Select a video to preview';$('#time').textContent='00:00:00.000';$('#length').textContent=' / —';if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null}}
 currentFolder='';await loadConfiguration(kind==='project');if(kind==='shots')await loadShots(true);toast('Selection saved · applied without restarting');
 }catch(e){toast('Browse error: '+e.message)}finally{pickerBusy=false;buttons.forEach(b=>b.disabled=false)}
}
$('#browseproject').onclick=()=>browse('project');$('#browsesource').onclick=()=>browse('source');$('#browseshots').onclick=()=>browse('shots');
$("#open").onclick=()=>$("#filepick").click();const video=$("#video");
$("#filepick").onchange=e=>{const file=e.target.files[0];if(!file)return;if(window.showSourceReview)window.showSourceReview();if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);currentName=file.name;currentPath="";video.src=objectURL;$("#empty").style.display="none";$("#clipname").textContent=file.name;$("#target").value=file.name.replace(/\.[^.]+$/,"").replace(/[_\s]/g,"");toast("Local preview loaded · file is not uploaded")};
video.ontimeupdate=()=>$("#time").textContent=clock(video.currentTime,true);video.onloadedmetadata=()=>$("#length").textContent=" / "+clock(video.duration,true);video.onerror=()=>toast("Browser cannot play this file. Transcode externally to compatible MP4 or WebM.");
$("#play").onclick=async()=>{if(!video.src)return toast("Open a preview video first.");if(video.paused){try{await video.play()}catch(e){toast(e.message)}}else video.pause()};
$("#back").onclick=()=>{if(video.src)video.currentTime=Math.max(0,video.currentTime-1)};$("#forward").onclick=()=>{if(video.src)video.currentTime=Math.min(video.duration||0,video.currentTime+1)};
$('#timestamp').onclick=()=>{if(preparing)return;if(!video.src)return toast('Open a video first.');if(!currentPath)return toast('Choose a video from the footage library so FFmpeg has its full source path.');video.pause();shots.push(newShot(clock(video.currentTime)));selected=shots.length-1;markDirty();render();toast('Shot added with timing, delta and resolution')};
document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-tab]").forEach(x=>x.classList.toggle("selected",x===b));$("#shots-tab").hidden=b.dataset.tab!=="shots";$("#config-tab").hidden=b.dataset.tab!=="config"});
async function loadConfiguration(forceReferences=false){
 try{const response=await fetch('/api/config',{cache:'no-store'});const r=await response.json();if(!response.ok)throw new Error(r.error);pickerToken=r.picker_token;
 $('#project').value=r.resolved_paths.viggle_auto;$('#shotsfile').value=r.resolved_paths.shots_csv;$('#sourcefolder').value=r.resolved_paths.source_video_directory||'';
 const d=r.config.shot_defaults||{};$('#duration').value=d.duration_seconds??10;$('#width').value=d.width??1344;$('#height').value=d.height??768;$('#delta').value=d.screenshot_delta??'00:00:00';
 $('#configeditor').value=JSON.stringify(r.config,null,2);$('#linkdetails').textContent=JSON.stringify({resolved_paths:r.resolved_paths,pipeline:r.pipeline},null,2);
 if(window.loadStaticReferences&&(forceReferences||!window.staticReferencesDirty?.()))await window.loadStaticReferences();
 await loadLibrary(currentFolder);if(!shotsLoaded)await loadShots(true);
 const progressResponse=await fetch('/api/prepare/status',{cache:'no-store'});const job=await progressResponse.json();
 const pipeResponse=await fetch('/api/pipeline/status',{cache:'no-store'});const pipe=await pipeResponse.json();
 if(job.running&&!preparing){setPreparing(true);if(window.beginStep2Review)await window.beginStep2Review();pollPrepare()}
 else if(pipe.running&&!preparing){setPreparing(true);if(window.beginStageReview)await window.beginStageReview(pipe.stage);pollPipeline()}
 else if(!preparing){const recent=(pipe.started_at||0)>(job.started_at||0)?pipe:job;if(recent.events?.length){showProcessingLog(recent.events);$('#preparestatus').textContent=recent.message}}
 if(forceReferences&&window.resetResultReview)await window.resetResultReview();
 }catch(e){toast('Configuration error: '+e.message)}
}
loadConfiguration();
$("#validate").onclick=()=>{try{JSON.parse($("#configeditor").value);toast("Valid JSON · not saved to disk")}catch(e){toast("Invalid JSON: "+e.message)}};render();
