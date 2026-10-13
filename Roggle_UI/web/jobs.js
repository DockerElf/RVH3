(()=>{
 const $=s=>document.querySelector(s);let state=null,busy=false;
 function message(text){$('#jobs-message').textContent=text}
 function disabled(){return busy||preparing||!!state?.locked}
 function draw(){
  const rows=$('#jobs-rows');rows.replaceChildren();
  for(const job of state.jobs){const tr=document.createElement('tr'),name=document.createElement('td'),status=document.createElement('td'),action=document.createElement('td'),button=document.createElement('button');
   name.textContent=job.name;status.textContent=job.state==='complete'?'Complete':'Incomplete';status.className='job-'+job.state;button.textContent='×';button.title='Remove this job record only';button.disabled=disabled();button.onclick=()=>clear('selected',[job.key]);action.append(button);tr.append(name,status,action);rows.append(tr)
  }
  $('#jobs-summary').textContent=state.jobs.length+' jobs · '+state.complete+' complete · '+state.incomplete+' incomplete'+(state.locked?' · controller locked':'');
  $('#jobs-clear-incomplete').disabled=disabled()||!state.incomplete;$('#jobs-clear-all').disabled=disabled()||!state.jobs.length;
 }
 async function load(){
  try{const response=await fetch('/api/jobs',{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error);state=data;draw()}
  catch(e){message('Jobs: '+e.message)}
 }
 async function clear(mode,keys=[]){
  if(!state||disabled())return;
  const scope=mode==='selected'?keys.join('\n'):mode==='incomplete'?'ALL incomplete job records':'ALL job records, including completed jobs';
  if(!confirm('Remove '+scope+' from viggle_auto/run_state.json?\n\nThis resets tracking for reruns. It does NOT delete media or cancel backend jobs. This cannot be undone in the GUI.\n\nAllowed with an idle backend, or when the local backend explicitly refuses the connection. Active controllers and ambiguous connection failures remain blocked.'))return;
  busy=true;draw();
  try{const result=await postAPI('/api/jobs/clear',{mode,keys,revision:state.revision});message('Removed '+result.removed+' record(s)'+(result.backend_status==='offline'?' while the local backend was offline':'')+'. Media retained. You may rerun the stage once its underlying error is fixed.');busy=false;await load()}
  catch(e){message('Clear blocked: '+e.message)}finally{busy=false;if(state)draw()}
 }
 $('#jobs-refresh').onclick=load;$('#jobs-clear-incomplete').onclick=()=>clear('incomplete');$('#jobs-clear-all').onclick=()=>clear('all');
 document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{const visible=button.dataset.tab==='jobs';$('#jobs-tab').hidden=!visible;if(visible)load()}));
 setInterval(()=>{if(!$('#jobs-tab').hidden&&!busy)load()},3000);
 // Extend Prepare to allow audio repair when CSV rows are already complete.
 $('#prepare').onclick=async()=>{
  if(preparing)return;if(!shots.length)return toast('No shot rows loaded.');
  const open=shots.filter(s=>s.status==='open').length;
  if(!confirm('Prepare '+open+' open rows and check completed CSV clips for missing audio?\n\nExisting no-audio MP4s will be replaced with the same video plus silent AAC. Existing audio is kept. Original footage and PNGs are not changed by audio repair.'))return;
  toast('Checking open rows and existing clips for missing audio…');
  try{await postAPI('/api/prepare/start',{rows:shots,revision:csvRevision});shotDirty=false;setPreparing(true);window.lastReviewedPrepareCount=-1;if(window.beginStep2Review)await window.beginStep2Review();await pollPrepare()}
  catch(e){toast('Prepare could not start: '+e.message)}
 };
})();
