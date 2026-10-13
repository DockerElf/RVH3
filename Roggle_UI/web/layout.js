(()=>{
 const main=document.querySelector('main'),left=main?.querySelector(':scope > .left'),right=main?.querySelector(':scope > .right');if(!main||!left||!right)return;
 const key='roggle.sidebarWidths.v1';const limits={left:[220,560],right:[440,1100]};let desired={left:340,right:820},custom=false,active=null,frame=null,measuredDefaultRight=820;
 const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
 try{const stored=JSON.parse(localStorage.getItem(key)||'null');if(stored&&Number.isFinite(stored.left)&&Number.isFinite(stored.right)){desired={left:clamp(stored.left,...limits.left),right:clamp(stored.right,...limits.right)};custom=true}}catch{}
 left.id=left.id||'layout-left-sidebar';right.id=right.id||'layout-right-sidebar';
 function make(side,panel){const handle=document.createElement('div');handle.className='sidebar-splitter sidebar-splitter-'+side;handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');handle.setAttribute('aria-label','Resize '+side+' sidebar');handle.setAttribute('aria-controls',panel.id);handle.textContent='⋮';handle.title='Drag to resize. Arrow keys adjust. Double-click to reset.';return handle}
 const handles={left:make('left',left),right:make('right',right)};left.after(handles.left);right.before(handles.right);
 function budget(){const c=getComputedStyle(main);return main.clientWidth-parseFloat(c.paddingLeft)-parseFloat(c.paddingRight)}
 function wide(){return window.innerWidth>=1200}
 function fit(){
  const available=budget();let l=clamp(desired.left,...limits.left),r=clamp(desired.right,...limits.right);
  if(wide()){const sides=available-64-360;if(l+r>sides)l=Math.max(limits.left[0],sides-r);if(l+r>sides)r=Math.max(limits.right[0],sides-l)}
  else if(window.innerWidth>=900)l=Math.min(l,Math.max(limits.left[0],available-32-360));
  main.style.setProperty('--roggle-left-width',Math.round(l)+'px');main.style.setProperty('--roggle-right-width',Math.round(r)+'px');
  handles.left.setAttribute('aria-valuenow',Math.round(l));handles.right.setAttribute('aria-valuenow',Math.round(r));
  for(const side of ['left','right']){handles[side].setAttribute('aria-valuemin',limits[side][0]);handles[side].setAttribute('aria-valuemax',limits[side][1])}
  return {left:l,right:r};
 }
 function persist(){custom=true;try{localStorage.setItem(key,JSON.stringify(desired))}catch{}}
 function change(side,value){const current=fit();let max=limits[side][1];if(wide())max=Math.min(max,budget()-64-360-current[side==='left'?'right':'left']);else if(side==='left')max=Math.min(max,budget()-32-360);desired[side]=clamp(value,limits[side][0],Math.max(limits[side][0],max));fit()}
 for(const side of ['left','right']){
  const handle=handles[side];
  handle.addEventListener('pointerdown',e=>{if(e.button!==0||window.innerWidth<900||(!wide()&&side==='right'))return;e.preventDefault();const current=fit();active={side,id:e.pointerId,x:e.clientX,width:current[side]};handle.classList.add('dragging');document.body.classList.add('sidebar-resizing');try{handle.setPointerCapture(e.pointerId)}catch{}});
  handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home'].includes(e.key))return;e.preventDefault();if(e.key==='Home')desired[side]=side==='left'?340:820;else{const amount=(e.shiftKey?32:16)*(e.key==='ArrowRight'?1:-1)*(side==='left'?1:-1);change(side,fit()[side]+amount)}fit();persist()});
  handle.addEventListener('dblclick',()=>{desired[side]=side==='left'?340:defaultRight();fit();persist()});
 }
 window.addEventListener('pointermove',e=>{if(!active||e.pointerId!==active.id)return;change(active.side,active.width+(e.clientX-active.x)*(active.side==='left'?1:-1))});
 function finish(e){if(!active||e.pointerId!==active.id)return;handles[active.side].classList.remove('dragging');active=null;document.body.classList.remove('sidebar-resizing');persist()}
 window.addEventListener('pointerup',finish);window.addEventListener('pointercancel',finish);window.addEventListener('blur',()=>{if(active){finish({pointerId:active.id})}});
 function defaultRight(){const table=document.querySelector('#shots-tab table');const c=getComputedStyle(right);const need=table?table.scrollWidth+parseFloat(c.paddingLeft)+parseFloat(c.paddingRight)+18:820;measuredDefaultRight=clamp(Math.max(measuredDefaultRight,820,need),...limits.right);return measuredDefaultRight}
 function resize(){if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=null;if(!custom)desired.right=defaultRight();fit()})}
 window.addEventListener('resize',resize);
 if(window.ResizeObserver)new ResizeObserver(resize).observe(main);
 const rows=document.querySelector('#rows');if(rows)new MutationObserver(()=>{if(!custom)resize()}).observe(rows,{childList:true,subtree:true});
 fit();resize();
})();
