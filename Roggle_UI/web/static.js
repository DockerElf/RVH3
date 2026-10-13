(()=>{
function referencePanel(){
 if(window.referencePanel&&typeof window.referencePanel.dirty==='function'&&typeof window.referencePanel.accept==='function')return window.referencePanel;
 let data=null;const $=s=>document.querySelector(s);
 const selected=()=>[...document.querySelectorAll('#staticgrid input[type=checkbox]:checked')].map(c=>c.value);
 const dirty=()=>!!data&&JSON.stringify(selected())!==JSON.stringify(data.active);
 const note=text=>{const el=$('#staticstatus');if(el)el.textContent=text};
 function update(){const count=$('#staticcount');if(count)count.textContent=selected().length+' ENABLED';note(dirty()?'Unsaved reference changes':'Loaded from viggle_auto/config.json');window.updateSharedSettings?.()}
 function accept(snapshot){
  const grid=$('#staticgrid');if(!grid)throw new Error('Missing HTML element #staticgrid.');data=snapshot;const path=$('#staticfolderpath');if(path)path.textContent=snapshot.folder;grid.replaceChildren();
  snapshot.items.forEach(item=>{const card=document.createElement('label');card.className='reference-card'+(item.available?'':' unavailable');const preview=document.createElement('div');preview.className='reference-preview';
   if(item.preview_url){const img=document.createElement('img');img.src=item.preview_url;img.loading='lazy';img.alt=item.path;img.onerror=()=>{preview.replaceChildren();preview.textContent='Preview unavailable'};preview.append(img)}else preview.textContent='Missing/unsupported image';
   const line=document.createElement('div');line.className='reference-choice';const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.value=item.path;checkbox.checked=item.enabled;
   checkbox.onchange=()=>{if(!item.available&&checkbox.checked){checkbox.checked=false;update();note('Missing/unsupported images cannot be newly enabled.');return}update()};
   const name=document.createElement('span');name.textContent=item.path;line.append(checkbox,name);card.append(preview,line);if(item.error)card.title=item.error;grid.append(card)
  });update();if(!snapshot.items.length)note('No reference images found. Open static folder, add images, then Refresh.');
 }
 window.referencePanel={accept,selected,dirty,note};window.staticReferencesDirty=dirty;window.loadStaticReferences=()=>window.loadSharedSettings?.(false)||Promise.resolve();return window.referencePanel;
}

 const refs=referencePanel(),$=s=>document.querySelector(s);
 async function post(path){const response=await fetch('/api/config',{cache:'no-store'}),data=await response.json();if(!response.ok)throw new Error(data.error);const result=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:data.picker_token})});const body=await result.json();if(!result.ok)throw new Error(body.error);return body}
 const open=$('#openstatic'),refresh=$('#refreshstatic'),save=$('#savestatic');
 if(open)open.onclick=async()=>{try{await post('/api/static/open');refs.note('Static folder opened in Explorer')}catch(e){refs.note(e.message)}};
 if(refresh)refresh.onclick=()=>window.loadSharedSettings?.(true);
 if(save)save.onclick=()=>window.saveSharedSettings?.();
 window.addEventListener('beforeunload',e=>{if(refs.dirty()){e.preventDefault();e.returnValue=''}});
})();
