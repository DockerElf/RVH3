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

 const $=s=>document.querySelector(s),fields=[...document.querySelectorAll('[data-step3-field]')],refs=referencePanel();
 let model=null,dirtyStep=false,loading=false,saving=false,lastStage=null,project='';
 const norm=s=>(s||'').replaceAll('\\','/').toLowerCase();
 function note(text,state=''){const el=$('#step3-settings-status');if(el){el.textContent=text;el.dataset.state=state}}
 function dirty(){return dirtyStep||refs.dirty()}
 function state(){const locked=loading||saving||preparing||!!model?.controller_active,canSave=!!model&&dirty()&&refs.selected().length>0&&!locked;
  fields.forEach(f=>f.disabled=loading||saving||!model);
  for(const id of ['save-step3-settings','savestatic']){const el=$('#'+id);if(el)el.disabled=!canSave}
  for(const id of ['reload-step3-settings','refreshstatic']){const el=$('#'+id);if(el)el.disabled=loading||saving}
  const grid=$('#staticgrid');if(grid)grid.inert=loading||saving;
 }
 function display(data){
  if(!data.values||!data.references)throw new Error('Shared settings API returned an incomplete response. Check that the joint-save backend files are installed.');
  if(fields.length!==6)throw new Error('Expected six data-step3-field inputs in index.html; found '+fields.length+'.');
  model=data;project=data.project;fields.forEach(f=>{const value=data.values[f.dataset.step3Field];if(value===undefined)throw new Error('Missing setting '+f.dataset.step3Field);f.value=typeof value==='number'&&Number.isInteger(value)?value.toFixed(1):String(value);f.title=typeof value==='number'?String(value):''});dirtyStep=false;
  const path=$('#step3-settings-path');if(path)path.textContent=data.config_path;refs.accept(data.references);note('Loaded references and Step 3 settings. Either Save button saves both.');state();
 }
 async function load(force=false,discardApproved=false){
  if(loading||saving)return;if(dirty()&&!force)return;if(force&&dirty()&&!discardApproved&&!confirm('Reload BOTH static references and Step 3 settings?\n\nUnsaved changes in both panels will be discarded.'))return;
  loading=true;state();note('Loading shared settings…');
  try{const response=await fetch('/api/step3/settings',{cache:'no-store'}),data=await response.json();if(!response.ok)throw new Error(data.error);display(data)}catch(e){note('Settings could not load: '+e.message,'error');refs.note('Settings could not load: '+e.message)}finally{loading=false;state()}
 }
 function values(){const result={};for(const field of fields){let value=field.value;if(field.dataset.step3Field.endsWith('_weight')){const text=value.trim();if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)||!Number.isFinite(Number(text)))throw new Error('Weights must be finite numbers, for example 0.5.');value=Number(text)}result[field.dataset.step3Field]=value}return result}
 async function save(){
  if(!model||loading||saving||preparing||model.controller_active)return;
  try{const selected=refs.selected(),draft=values();if(!selected.length)throw new Error('Keep at least one enabled reference.');if(!pickerToken)throw new Error('Wait for GUI configuration to finish loading.');
   if(!confirm('Save BOTH enabled references and Step 3 settings to '+model.config_path+'?\n\nEnabled references:\n'+selected.join('\n')+'\n\nOne config backup will be created if anything changes. Applies to the next controller run.'))return;
   saving=true;state();note('Saving both panels…');refs.note('Saving both panels…');const data=await postAPI('/api/step3/settings/save',{values:draft,selected,revision:model.revision});display(data);note('Saved references and Step 3 settings together.');refs.note('Saved references and Step 3 settings together.');toast('References and Step 3 settings saved together')
  }catch(e){note('Save failed: '+e.message,'error');refs.note('Save failed: '+e.message);toast('Shared settings save failed: '+e.message)}finally{saving=false;state()}
 }
 fields.forEach(f=>f.addEventListener('input',()=>{dirtyStep=true;note('Unsaved settings · either Save button saves both panels.','dirty');state()}));
 for(const id of ['save-step3-settings','savestatic']){const el=$('#'+id);if(el)el.onclick=save}
 for(const id of ['reload-step3-settings','refreshstatic']){const el=$('#'+id);if(el)el.onclick=()=>load(true)}
 window.updateSharedSettings=state;window.loadSharedSettings=load;window.saveSharedSettings=save;window.step3SettingsDirty=()=>dirtyStep;
 function sidebar(name){document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.tab===name));for(const id of ['shots','step3-settings','config','jobs']){const el=$('#'+id+'-tab');if(el)el.hidden=id!==name}if(name==='step3-settings')load()}
 document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>sidebar(b.dataset.tab)));
 function open(name){document.querySelector('[data-tab="'+name+'"]')?.click()}
 function follow(stage){open(stage==='source'?'shots':stage==='step2'?'step3-settings':'jobs')}
 function sync(){const stage=window.reviewNavigationState?.().stage;if(stage&&stage!==lastStage){lastStage=stage;follow(stage)}}
 document.addEventListener('roggle-media-change',sync);
 document.querySelectorAll('[data-review]').forEach(b=>b.addEventListener('click',()=>{lastStage=b.dataset.review;follow(lastStage)}));
 document.querySelectorAll('[data-results]').forEach(b=>b.addEventListener('click',()=>{lastStage=b.dataset.results;follow(lastStage)}));
 const source=$('#source-browse-tab');if(source)source.addEventListener('click',()=>{lastStage='source';follow('source')});
 const baseRun=runPipeline;runPipeline=async function(stage){if(stage==='step3'&&(dirty()||saving)){open('step3-settings');return toast('Save both reference/settings drafts or reload them before Step 3.')}return baseRun(stage)};
 const basePreparing=setPreparing;setPreparing=function(value){basePreparing(value);if(!value&&model)model.controller_active=false;state()};
 const baseBrowse=browse;browse=async function(kind){if(kind==='project'&&dirty()&&!confirm('Changing project discards unsaved references and Step 3 settings. Continue?'))return;return baseBrowse(kind)};
 const baseConfig=loadConfiguration;loadConfiguration=async function(...args){await baseConfig(...args);if(project&&norm($('#project').value)!==norm(project)){model=null;dirtyStep=false;project='';await load(true,true)}};
 window.addEventListener('beforeunload',e=>{if(dirty()||saving){e.preventDefault();e.returnValue=''}});state();sync();load();
})();
(()=>{const script=document.createElement('script');script.src='csv-autosave.js';document.body.append(script)})();
