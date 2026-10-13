(()=>{
 const $=s=>document.querySelector(s);let activeStage='step2',reviewStage='source',entries=[],selectedFile=null,requestId=0;
 const folders={step2:'',step3:'',step4:''};const saved={};const labels={step2:'STEP 2',step3:'STEP 3',step4:'STEP 4'};
 const video=$('#reviewvideo'),image=$('#reviewimage');
 function changed(){document.dispatchEvent(new Event('roggle-media-change'))}
 function format(t){t=Math.max(0,Number(t)||0);const n=Math.floor(t);return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].map(x=>String(x).padStart(2,'0')).join(':')+'.'+String(Math.floor((t-n)*1000)).padStart(3,'0')}
 function stopResult(){video.pause();video.removeAttribute('src');video.load();image.removeAttribute('src');image.hidden=true;video.hidden=true;$('#reviewtransport').hidden=true;$('#reviewtimebar').hidden=true;$('#reviewempty').hidden=false;$('#reviewempty').textContent='Select an image or video in the result browser.'}
 function showSource(){reviewStage='source';video.pause();$('#source-review').hidden=false;$('#result-review').hidden=true;document.querySelectorAll('[data-review]').forEach(b=>b.classList.toggle('selected',b.dataset.review==='source'));changed()}
 function showStage(stage){reviewStage=stage;$('#video').pause();$('#source-review').hidden=true;$('#result-review').hidden=false;$('#reviewstage').textContent=labels[stage]+' / REVIEW';document.querySelectorAll('[data-review]').forEach(b=>b.classList.toggle('selected',b.dataset.review===stage));changed()}
 function select(entry,stage=activeStage){
  selectedFile=entry.relative_path;saved[stage]=entry;showStage(stage);stopResult();$('#reviewempty').hidden=true;$('#reviewfilename').textContent=entry.name;$('#reviewpath').textContent=entry.relative_path;$('#reviewkind').textContent=entry.kind==='image'?'Image':'Video';$('#reviewtransport').hidden=false;
  const isVideo=entry.kind==='video';for(const id of ['reviewback','reviewplay','reviewforward'])$('#'+id).hidden=!isVideo;
  if(!isVideo){image.hidden=false;image.src=entry.url}else{video.hidden=false;video.src=entry.url;video.load();$('#reviewtimebar').hidden=false;$('#reviewtime').textContent='00:00:00.000';$('#reviewlength').textContent=' / —'}render();
 }
 function visibleFiles(){return entries.filter(e=>e.kind!=='folder'&&e.name.toLowerCase().includes($('#resultfilter').value.toLowerCase()))}
 function render(){
  const grid=$('#resultentries');grid.replaceChildren();const filter=$('#resultfilter').value.toLowerCase();
  entries.filter(e=>e.name.toLowerCase().includes(filter)).forEach(entry=>{
   const button=document.createElement('button');button.className='result-item'+(entry.relative_path===selectedFile?' chosen':'');
   if(entry.kind==='image'){const thumb=document.createElement('img');thumb.src=entry.url;thumb.loading='lazy';thumb.alt=entry.name;button.append(thumb)}else{const icon=document.createElement('span');icon.className='result-icon';icon.textContent=entry.kind==='folder'?'📁':'▶';button.append(icon)}
   const name=document.createElement('span');name.className='result-name';name.textContent=entry.name;const info=document.createElement('small');info.textContent=entry.kind==='folder'?'Folder':entry.kind+' · '+(entry.size_bytes/1048576).toFixed(1)+' MB';button.append(name,info);
   button.onclick=()=>entry.kind==='folder'?load(entry.relative_path):select(entry);grid.append(button)
  });changed();
 }
 async function load(folder=folders[activeStage],preferred=null,autoSelect=true){
  const stage=activeStage,id=++requestId;$('#resultstatus').textContent='Loading '+labels[stage]+' results…';
  try{const response=await fetch('/api/review?stage='+stage+'&folder='+encodeURIComponent(folder),{cache:'no-store'});const data=await response.json();if(!response.ok)throw new Error(data.error);
   if(id!==requestId||stage!==activeStage)return;folders[stage]=data.folder;entries=data.entries;$('#resultfolder').textContent=data.root+(data.folder?' / '+data.folder:'');$('#resultup').disabled=!data.folder;
   $('#resultstatus').textContent=data.missing?'This stage folder has not been created yet.':entries.length?entries.filter(e=>e.kind!=='folder').length+' media files · click a file to review':'No result files or subfolders here yet.';
   const remembered=saved[stage]?.relative_path;selectedFile=remembered||null;render();
   if(autoSelect&&reviewStage!=='source'){
    const match=entries.find(e=>e.kind!=='folder'&&e.relative_path===preferred)||entries.find(e=>e.kind!=='folder'&&e.relative_path===remembered)||entries.find(e=>e.kind!=='folder');
    if(match&&(!saved[stage]||saved[stage].relative_path!==match.relative_path||reviewStage!==stage))select(match,stage);
    else if(!match){stopResult();$('#reviewfilename').textContent='Select a result below';$('#reviewpath').textContent=''}
   }
  }catch(e){if(id!==requestId)return;entries=[];render();$('#resultstatus').textContent=e.message}
 }
 async function activate(stage){
  if(stage!==activeStage){stopResult();selectedFile=null;entries=[]}
  activeStage=stage;showStage(stage);document.querySelectorAll('[data-results]').forEach(b=>b.classList.toggle('selected',b.dataset.results===stage));
  await load();if(saved[stage]&&entries.some(e=>e.relative_path===saved[stage].relative_path)&&video.hidden&&image.hidden)select(saved[stage],stage);
 }
 document.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>b.dataset.review==='source'?showSource():activate(b.dataset.review));
 document.querySelectorAll('[data-results]').forEach(b=>b.onclick=()=>activate(b.dataset.results));
 $('#resultfilter').oninput=render;$('#resultrefresh').onclick=()=>load();$('#resultup').onclick=()=>load(folders[activeStage].split('/').slice(0,-1).join('/'));
 $('#resultopen').onclick=async()=>{try{await postAPI('/api/review/open',{stage:activeStage,folder:folders[activeStage]})}catch(e){$('#resultstatus').textContent=e.message}};
 video.ontimeupdate=()=>$('#reviewtime').textContent=format(video.currentTime);video.onloadedmetadata=()=>$('#reviewlength').textContent=' / '+format(video.duration);
 video.onerror=()=>{$('#reviewempty').hidden=false;$('#reviewempty').textContent='Browser cannot play this video/codec.'};image.onerror=()=>{$('#reviewempty').hidden=false;$('#reviewempty').textContent='Image preview could not be loaded.'};
 $('#reviewplay').onclick=async()=>{if(!video.src)return;try{if(video.paused)await video.play();else video.pause()}catch(e){$('#resultstatus').textContent=e.message}};
 $('#reviewback').onclick=()=>{if(video.src)video.currentTime=Math.max(0,video.currentTime-1)};$('#reviewforward').onclick=()=>{if(video.src)video.currentTime=Math.min(video.duration||0,video.currentTime+1)};
 window.showSourceReview=showSource;
 window.beginStageReview=async stage=>{if(!labels[stage])return;folders[stage]='';await activate(stage)};
 window.beginStep2Review=()=>window.beginStageReview('step2');
 window.refreshStageResults=async(stage,preferred=null)=>{if(activeStage===stage)await load(folders[stage],preferred,reviewStage===stage)};
 window.refreshStep2Results=preferred=>window.refreshStageResults('step2',preferred);
 window.resetResultReview=async()=>{Object.keys(folders).forEach(k=>{folders[k]='';delete saved[k]});stopResult();selectedFile=null;entries=[];await load('',null,false)};
 window.reviewNavigationState=()=>({stage:reviewStage,files:visibleFiles(),selected:selectedFile});
 window.navigateResult=delta=>{if(reviewStage==='source')return;const files=visibleFiles();const index=files.findIndex(e=>e.relative_path===selectedFile);const next=index<0?(delta>0?0:-1):index+delta;if(next>=0&&next<files.length)select(files[next],activeStage)};
 load('',null,false);
})();
