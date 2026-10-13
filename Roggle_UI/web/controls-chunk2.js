(()=>{
 const $=s=>document.querySelector(s);
 const paths={play:'<path d="M8 5l12 7-12 7z" fill="currentColor" stroke="none"/>',pause:'<path d="M7 5v14M17 5v14" stroke-width="4"/>',prev:'<path d="M5 5v14M19 5l-10 7 10 7z"/>',next:'<path d="M19 5v14M5 5l10 7-10 7z"/>',back:'<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/><text x="12" y="16" text-anchor="middle" fill="currentColor" stroke="none" font-size="10">1</text>',forward:'<path d="M20 10a8 8 0 1 0-1 8M20 4v6h-6"/><text x="12" y="16" text-anchor="middle" fill="currentColor" stroke="none" font-size="10">1</text>'};
 function icon(id,kind,label){const b=$('#'+id);b.innerHTML='<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+paths[kind]+'</svg>';b.classList.add('icon-control');b.title=label;b.setAttribute('aria-label',label)}
 for(const prefix of ['', 'review']){icon(prefix?'reviewback':'back','back','Seek back 1 second');icon(prefix?'reviewforward':'forward','forward','Seek forward 1 second');icon(prefix?'reviewprev':'sourceprev','prev','Previous file');icon(prefix?'reviewnext':'sourcenext','next','Next file')}
 for(const [videoId,buttonId] of [['video','play'],['reviewvideo','reviewplay']]){const video=$('#'+videoId);const update=()=>icon(buttonId,video.paused?'play':'pause',video.paused?'Play':'Pause');for(const name of ['play','pause','ended','emptied'])video.addEventListener(name,update);update()}
 function sourceFiles(){return libraryEntries.filter(e=>e.kind==='video'&&e.name.toLowerCase().includes($('#search').value.toLowerCase()))}
 function updateNavigation(){
  const files=sourceFiles(),index=files.findIndex(e=>e.full_path===currentPath);$('#sourceprev').disabled=index<=0;$('#sourcenext').disabled=!files.length||index===files.length-1;
  const state=window.reviewNavigationState?.();if(state){const i=state.files.findIndex(e=>e.relative_path===state.selected);$('#reviewprev').disabled=i<=0;$('#reviewnext').disabled=!state.files.length||i===state.files.length-1;}
 }
 function navigateSource(delta){const files=sourceFiles(),i=files.findIndex(e=>e.full_path===currentPath),next=i<0?(delta>0?0:-1):i+delta;if(next<0||next>=files.length)return;const entry=files[next];const card=[...$('#library').querySelectorAll('.source-entry')].find(b=>b.title===entry.relative_path)||null;openLibraryVideo(entry,card);updateNavigation()}
 $('#sourceprev').onclick=()=>navigateSource(-1);$('#sourcenext').onclick=()=>navigateSource(1);$('#reviewprev').onclick=()=>window.navigateResult?.(-1);$('#reviewnext').onclick=()=>window.navigateResult?.(1);
 const baseOpen=openLibraryVideo;openLibraryVideo=function(...args){baseOpen(...args);updateNavigation()};const baseLoad=loadLibrary;loadLibrary=async function(...args){await baseLoad(...args);updateNavigation()};
 $('#search').addEventListener('input',updateNavigation);$('#filepick').addEventListener('change',updateNavigation);document.addEventListener('roggle-media-change',updateNavigation);updateNavigation();
 async function action(path,payload={}){try{return await postAPI(path,payload)}catch(e){toast(e.message);return null}}
 $('#openproject').onclick=()=>action('/api/project/open');$('#opencsvfolder').onclick=()=>action('/api/csv/open');
 let backendTimer=null;
 async function checkBackend(){
  try{const response=await fetch('/api/backend/status',{cache:'no-store'});const state=await response.json();if(!response.ok)throw new Error(state.error);$('#backend-status').textContent=state.message;$('#startcomfy').disabled=state.starting;if(state.starting)backendTimer=setTimeout(checkBackend,2000)}
  catch(e){$('#backend-status').textContent=e.message;$('#startcomfy').disabled=false}
 }
 $('#startcomfy').onclick=async()=>{if(backendTimer)clearTimeout(backendTimer);$('#startcomfy').disabled=true;const result=await action('/api/backend/start');if(result){$('#backend-status').textContent=result.message;if(result.starting)checkBackend();else $('#startcomfy').disabled=false}else $('#startcomfy').disabled=false};
 document.querySelector('[data-tab="jobs"]').addEventListener('click',checkBackend);
 // Horizontal divider adjusts heights without changing sidebar width behavior.
 const middle=document.querySelector('main > .middle'),divider=$('#vertical-splitter'),browse=$('#browse-collapse');const key='roggle.verticalPanes.v1';const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const defaults=()=>({screen:clamp(window.innerHeight*.32,220,500),browser:clamp(window.innerHeight*.25,160,360)});let size=defaults(),drag=null;
 try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved&&Number.isFinite(saved.screen)&&Number.isFinite(saved.browser))size={screen:clamp(saved.screen,160,900),browser:clamp(saved.browser,100,800)}}catch{}
 function apply(){middle.style.setProperty('--review-screen-height',Math.round(size.screen)+'px');middle.style.setProperty('--browse-grid-height',Math.round(size.browser)+'px');divider.setAttribute('aria-valuenow',Math.round(size.screen));divider.setAttribute('aria-valuemin','160');divider.setAttribute('aria-valuemax','900');divider.hidden=!browse.open}
 function store(){try{localStorage.setItem(key,JSON.stringify(size))}catch{}}
 function shift(delta,start=size){const min=Math.max(160-start.screen,start.browser-800),max=Math.min(900-start.screen,start.browser-100),d=clamp(delta,min,max);size={screen:start.screen+d,browser:start.browser-d};apply()}
 divider.addEventListener('pointerdown',e=>{if(e.button!==0||!browse.open)return;e.preventDefault();drag={id:e.pointerId,y:e.clientY,start:{...size}};document.body.classList.add('pane-resizing');try{divider.setPointerCapture(e.pointerId)}catch{}});
 window.addEventListener('pointermove',e=>{if(drag&&e.pointerId===drag.id)shift(e.clientY-drag.y,drag.start)});
 function finish(e){if(!drag||e.pointerId!==drag.id)return;drag=null;document.body.classList.remove('pane-resizing');store()}
 window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);window.addEventListener('blur',()=>{if(drag)finish({pointerId:drag.id})});
 divider.addEventListener('keydown',e=>{if(!['ArrowUp','ArrowDown','Home'].includes(e.key))return;e.preventDefault();if(e.key==='Home')size=defaults();else shift((e.key==='ArrowDown'?1:-1)*(e.shiftKey?32:16));apply();store()});divider.addEventListener('dblclick',()=>{size=defaults();apply();store()});browse.addEventListener('toggle',apply);apply();
})();
