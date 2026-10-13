(()=>{
 if(window.csvAutosaveInstalled)return;window.csvAutosaveInstalled=true;
 const $=s=>document.querySelector(s),scope=$('#shots-tab'),reload=$('#reloadshots'),save=$('#saveshots');
 const key='roggle.csv.autosave.v1';let enabled=true,pending=null,timer=null,focused=false,syncing=false,lastPointerInside=false,version=0,actionDepth=0;
 try{enabled=localStorage.getItem(key)!=='off'}catch{}
 const label=document.createElement('label');label.className='csv-autosave-control';const toggle=document.createElement('input');toggle.type='checkbox';toggle.id='csv-autosave';toggle.checked=enabled;toggle.setAttribute('role','switch');toggle.setAttribute('aria-label','Autosave shot CSV');const caption=document.createElement('span');caption.textContent='Autosave';label.append(toggle,caption);reload.before(label);
 const overlay=document.createElement('div');overlay.className='csv-sync-overlay';overlay.hidden=true;overlay.setAttribute('role','status');overlay.setAttribute('aria-live','polite');const box=document.createElement('div');box.className='csv-sync-box';box.textContent='Saving CSV…';overlay.append(box);scope.append(overlay);
 const style=document.createElement('style');style.textContent=`
 #shots-tab{position:relative}.shot-actions{flex-wrap:wrap}
 .csv-autosave-control{display:inline-flex;align-items:center;gap:7px;margin:0 6px 0 0;white-space:nowrap;font-size:12px;cursor:pointer}
 .csv-autosave-control input{width:16px;height:16px;min-width:16px;margin:0;padding:0;accent-color:var(--accent)}
 .csv-sync-overlay{position:absolute;inset:0;z-index:30;display:flex;align-items:flex-start;justify-content:center;padding-top:55px;background:rgba(10,15,23,.72);border-radius:8px;cursor:wait}
 .csv-sync-overlay[hidden]{display:none}.csv-sync-box{padding:14px 22px;background:#16202e;border:1px solid var(--accent);border-radius:8px;color:var(--text);box-shadow:0 8px 28px rgba(0,0,0,.35)}
 #step3-settings-tab .step3-weight input[type="number"]{box-sizing:content-box;width:calc(3ch + 20px);min-width:calc(3ch + 20px);max-width:calc(3ch + 20px);padding:8px 7px;appearance:auto;-moz-appearance:auto}
 #step3-settings-tab .step3-weight input[type="number"]::-webkit-inner-spin-button,#step3-settings-tab .step3-weight input[type="number"]::-webkit-outer-spin-button{-webkit-appearance:inner-spin-button;opacity:1;margin:0}
 `;document.head.append(style);
 for(const id of ['s3-head-weight','s3-body-weight']){const input=$('#'+id);if(input){input.type='number';input.step='0.1';input.removeAttribute('size')}}
 const baseDirty=markDirty;markDirty=function(...args){version++;return baseDirty(...args)};
 function cancel(){clearTimeout(timer);timer=null}
 function buttons(){reload.disabled=enabled||preparing||syncing;save.disabled=enabled||preparing||syncing;toggle.disabled=preparing||syncing;$('#timestamp').disabled=preparing||syncing;$('#add').disabled=preparing||syncing}
 function apply(data,id){shots=data.rows;csvRevision=data.revision;shotDirty=false;shotsLoaded=true;const index=shots.findIndex(r=>r.id===id);selected=index>=0?index:Math.max(0,Math.min(selected,shots.length-1));$('#shotsfile').value=data.csv_path;render()}
 const basePost=postAPI;
 async function snapshot(){const response=await fetch('/api/shots',{cache:'no-store'}),data=await response.json();if(!response.ok)throw new Error(data.error);return data}
 function flush(force=false){
  if(pending)return pending;if((!enabled&&!force)||preparing||!shotsLoaded||actionDepth)return Promise.resolve();
  cancel();const id=shots[selected]?.id,wasDirty=shotDirty,automatic=enabled,captured=version,expected=csvRevision,draft=shots.map(r=>({...r}));let written=false;
  syncing=true;overlay.hidden=false;box.textContent=wasDirty?'Saving CSV…':'Reloading CSV…';scope.inert=true;scope.setAttribute('aria-busy','true');buttons();
  pending=Promise.resolve().then(async()=>{
   try{
    if(wasDirty){const result=await basePost('/api/shots/save',{rows:draft,revision:expected,autosave:automatic});written=true;csvRevision=result.revision;if(version!==captured)return;apply(result,id);box.textContent='Reloading CSV…'}
    const data=await snapshot();if(version!==captured)return;apply(data,id);$('#csvstate').textContent=wasDirty?(automatic?'Autosaved':'Saved')+' and reloaded · '+shots.length+' rows':'CSV reloaded · '+shots.length+' rows';
   }catch(e){const text=written?'CSV saved, but reload failed: ':wasDirty?'Autosave failed; draft retained: ':'CSV reload failed: ';$('#csvstate').textContent=text+e.message;toast(text+e.message);throw e}
  }).finally(()=>{const newer=version!==captured;pending=null;syncing=false;overlay.hidden=true;scope.inert=false;scope.setAttribute('aria-busy','false');buttons();if(newer&&enabled&&shotDirty&&!preparing)queueMicrotask(()=>flush().catch(()=>{}))});return pending;
 }
 function schedule(){cancel();if(enabled&&!preparing&&!syncing&&!actionDepth)timer=setTimeout(()=>{timer=null;flush().catch(()=>{})},0)}
 function wrapMutation(button){
  if(!button||button.csvCompletionHook)return;const original=button.onclick;if(typeof original!=='function')return;button.csvCompletionHook=true;
  button.onclick=function(event){
   if(preparing||syncing)return;cancel();const before=version;actionDepth++;
   try{return original.call(this,event)}
   finally{actionDepth--;if(enabled&&version!==before&&shotDirty)flush().catch(()=>{})}
  };
 }
 const baseRender=render;render=function(...args){const result=baseRender(...args);document.querySelectorAll('#rows button').forEach(wrapMutation);return result};
 wrapMutation($('#add'));wrapMutation($('#timestamp'));render();
 scope.addEventListener('focusin',()=>{focused=true;cancel()});
 scope.addEventListener('focusout',event=>{if(syncing||actionDepth)return;if(!event.relatedTarget&&lastPointerInside&&document.hasFocus())return;if(event.relatedTarget&&scope.contains(event.relatedTarget))return;focused=false;schedule()});
 document.addEventListener('pointerdown',event=>{lastPointerInside=scope.contains(event.target);if(lastPointerInside){cancel();return}if(focused||scope.contains(document.activeElement)){focused=false;schedule()}},true);
 toggle.addEventListener('change',()=>{enabled=toggle.checked;cancel();try{localStorage.setItem(key,enabled?'on':'off')}catch{}buttons();flush(true).catch(()=>{})});
 const basePreparing=setPreparing;setPreparing=function(value){basePreparing(value);buttons()};
 postAPI=async function(path,extra){
  if(enabled&&path!=='/api/shots/save'&&(pending||shotDirty)){try{await flush()}catch(e){if(path==='/api/prepare/start'||path==='/api/pipeline/start')throw e}}
  if(path==='/api/prepare/start')extra={...extra,rows:shots,revision:csvRevision,autosave:enabled};else if(path==='/api/shots/save')extra={...extra,autosave:enabled};return basePost(path,extra);
 };
 const baseBrowse=browse;browse=async function(kind){if(enabled&&(pending||shotDirty)){try{await flush()}catch{return}}return baseBrowse(kind)};
 let backgroundVersion=-1;
 function background(){if(enabled&&shotDirty&&!preparing&&!actionDepth&&backgroundVersion!==version){backgroundVersion=version;cancel();flush().catch(()=>{})}}
 window.addEventListener('blur',background);document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')background()});
 let hadFocus=document.hasFocus();setInterval(()=>{const hasFocus=document.hasFocus();if(!hasFocus&&hadFocus)background();if(hasFocus&&!hadFocus)backgroundVersion=-1;hadFocus=hasFocus},500);
 window.csvAutosaveEnabled=()=>enabled;window.flushCsvAutosave=flush;buttons();
})();
