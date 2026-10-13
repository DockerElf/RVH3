(()=>{
 const $=s=>document.querySelector(s);const tab=$('#source-browse-tab'),sourcePanel=$('#source-library-panel'),stagePanel=$('#stage-library-panel');let observer=null;
 const baseShowSource=window.showSourceReview;const baseBeginStage=window.beginStageReview;
 function release(){if(observer){observer.disconnect();observer=null}sourcePanel.querySelectorAll('.source-thumb').forEach(v=>{v.pause();v.removeAttribute('src');v.load()})}
 function showSourceBrowser(){
  const refresh=sourcePanel.hidden||!$('#library').childElementCount;sourcePanel.hidden=false;stagePanel.hidden=true;tab.classList.add('selected');document.querySelectorAll('[data-results]').forEach(b=>b.classList.remove('selected'));if(refresh)renderLibrary();
 }
 function showStageBrowser(){sourcePanel.hidden=true;stagePanel.hidden=false;tab.classList.remove('selected');release()}
 // Existing loadLibrary() resolves this global function when the folder changes.
 renderLibrary=function(){
  release();const grid=$('#library');grid.replaceChildren();const filter=$('#search').value.toLowerCase();
  $('#sourcebrowsepath').textContent=($('#sourcefolder').value||'No footage folder selected')+(currentFolder?' / '+currentFolder:'');
  const pending=[];
  libraryEntries.filter(e=>e.name.toLowerCase().includes(filter)).forEach(entry=>{
   const button=document.createElement('button');button.className='file source-entry';button.title=entry.relative_path;
   const box=document.createElement('div');box.className='source-thumbnail-box';const fallback=document.createElement('span');fallback.className='source-thumbnail-fallback';fallback.textContent=entry.kind==='folder'?'📁':'▶';box.append(fallback);
   if(entry.kind==='video'){
    const thumb=document.createElement('video');thumb.className='source-thumb';thumb.muted=true;thumb.playsInline=true;thumb.preload='metadata';thumb.hidden=true;thumb.setAttribute('aria-hidden','true');box.append(thumb);
    thumb.onloadedmetadata=()=>{if(Number.isFinite(thumb.duration)&&thumb.duration>0)thumb.currentTime=Math.min(.1,thumb.duration/2)};
    thumb.onloadeddata=()=>{thumb.hidden=false;fallback.hidden=true};thumb.onseeked=()=>{thumb.pause();thumb.hidden=false;fallback.hidden=true};
    thumb.onerror=()=>{thumb.hidden=true;fallback.hidden=false;fallback.title='Thumbnail unavailable; try opening the video.'};pending.push({thumb,target:box,url:entry.url});
   }
   const name=document.createElement('span');name.className='source-entry-name';name.textContent=entry.name;const info=document.createElement('small');info.textContent=entry.kind==='folder'?'Folder':(entry.size_bytes/1048576).toFixed(1)+' MB';button.append(box,name,info);
   button.onclick=()=>entry.kind==='folder'?loadLibrary(entry.relative_path):openLibraryVideo(entry,button);grid.append(button)
  });
  $('#librarycount').textContent=libraryEntries.filter(e=>e.kind==='video').length+' FILES';
  if(window.IntersectionObserver){
   observer=new IntersectionObserver(items=>{for(const item of items)if(item.isIntersecting){const thumb=item.target.querySelector('.source-thumb');if(thumb){thumb.src=thumb.dataset.previewUrl+'#t=0.1';thumb.load()}observer.unobserve(item.target)}},{root:grid,rootMargin:'60px'});
   for(const item of pending){item.thumb.dataset.previewUrl=item.url;observer.observe(item.target)}
  }else if(!sourcePanel.hidden){for(const item of pending){item.thumb.src=item.url+'#t=0.1';item.thumb.load()}}
 };
 $('#search').oninput=()=>renderLibrary();
 tab.onclick=()=>{if(baseShowSource)baseShowSource();showSourceBrowser();};
 document.querySelectorAll('[data-review]').forEach(b=>b.addEventListener('click',()=>b.dataset.review==='source'?showSourceBrowser():showStageBrowser()));
 document.querySelectorAll('[data-results]').forEach(b=>b.addEventListener('click',showStageBrowser));
 window.showSourceReview=()=>{if(baseShowSource)baseShowSource();showSourceBrowser()};
 if(baseBeginStage)window.beginStageReview=async stage=>{showStageBrowser();await baseBeginStage(stage)};
 showSourceBrowser();
})();
