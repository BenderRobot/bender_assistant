'use strict';
(() => {
 if(display)return;
 const clone=value=>JSON.parse(JSON.stringify(value));
 const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
 const make=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
 const button=(text,action)=>{const element=make('button',text);element.type='button';element.addEventListener('click',action);return element;};
 const unsaved=new Set(), editors={}, libraries={};
 let items=[];
 window.BenderCustomSelection={mouth:null,eyes:null};
 window.addEventListener('beforeunload',event=>{if(unsaved.size){event.preventDefault();event.returnValue='';}});
 async function request(path,options){const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Forme invalide. Vérifie les réglages et le nom.');return data;}
 async function reloadLibrary(){
  const data=await request('/api/poses',{cache:'no-store'});items=data.items;
  for(const kind of ['eyes','mouth']){
   const select=libraries[kind].select,previous=select.value;
   select.replaceChildren(make('option','Choisir une création…'));
   select.options[0].value='';
   items.filter(item=>item.kind===kind).forEach(item=>{const option=make('option',item.name);option.value=item.id;select.append(option);});
   select.value=items.some(item=>item.id===previous)?previous:'';
   libraries[kind].message.textContent=`${items.filter(item=>item.kind===kind).length} création(s) enregistrée(s) sur Bender.`;
  }
 }
 async function apply(kind,definition,name){
  await stop();window.BenderCustomSelection[kind]=clone(definition);
  sendFace({pose:0,eyes:$('emotion').value,mode:$('eyeMode').value,blink:$('eyeBlink').checked,active:false});
  $(kind==='mouth'?'poseState':'eyePreviewStatus').textContent=`Création : ${name||'aperçu non enregistré'}`;
 }
 function library(kind){
  const root=$(`library-${kind}`),label=make('label',kind==='mouth'?'Mes bouches':'Mes yeux');
  const select=make('select');select.setAttribute('aria-label',label.textContent);label.append(select);
  const message=make('p','Chargement des créations…','editor-message');
  const actions=make('div',undefined,'buttons');
  function selected(){return items.find(item=>item.id===select.value);}
  actions.append(button('Afficher ma création',async()=>{const item=selected();if(!item){message.textContent='Choisis une création.';return;}try{await apply(kind,item.definition,item.name);}catch(error){message.textContent=error.message;}}),button('Modifier cette création',()=>{const item=selected();if(!item){message.textContent='Choisis une création.';return;}editors[kind].load(item);}),button('Actualiser mes créations',()=>reloadLibrary().catch(error=>{message.textContent=error.message;})));
  root.className='creation-library';root.append(label,actions,message);libraries[kind]={select,message};
 }
 function editor(kind){
  const root=$(`editor-${kind}`),isMouth=kind==='mouth',width=isMouth?128:800,height=isMouth?64:480;
  let shape=isMouth?BenderFace.mouthPreset(0):BenderShapes.eyesPreset('normal');
  let identifier=null,revision=null,history=[],future=[],drag=null,selectedEye=0,saving=false;
  const bindings=[];
  const status=make('p','Prêt à créer. Les poses d’origine restent conservées.','editor-message');status.setAttribute('role','status');
  const instructions=make('p',isMouth?'Déplace les points orange et verts pour modeler les deux lèvres. Tu peux aussi dessiner directement une ligne. Le dessin conserve le format 128 × 64 de la matrice.':'Déplace les paupières et les pupilles sur le dessin. Le mode « Position et taille » permet de déplacer et redimensionner les yeux. Le cadre reste au format 800 × 480.','editor-help');
  const canvas=make('canvas');canvas.width=isMouth?768:800;canvas.height=isMouth?384:480;canvas.className='shape-canvas';canvas.setAttribute('aria-label',isMouth?'Éditeur graphique de bouche':'Éditeur graphique des yeux');
  const ctx=canvas.getContext('2d');
  const toolbar=make('div',undefined,'editor-toolbar');
  const toolLabel=make('label','Outil');const tool=make('select');tool.setAttribute('aria-label',`Outil ${isMouth?'bouche':'yeux'}`);
  (isMouth?[['handles','Déplacer les points'],['top','Dessiner la ligne du haut'],['bottom','Dessiner la ligne du bas']]:[['lids','Paupières et pupilles'],['geometry','Position et taille']]).forEach(([value,text])=>{const option=make('option',text);option.value=value;tool.append(option);});toolLabel.append(tool);
  const symmetryLabel=make('label',undefined,'editor-inline');const symmetry=make('input');symmetry.type='checkbox';symmetry.checked=true;symmetryLabel.append(symmetry,document.createTextNode(isMouth?'Symétrie gauche / droite':'Lier les deux yeux'));
  toolbar.append(toolLabel,symmetryLabel);
  if(!isMouth){const eyeLabel=make('label','Œil à régler');const eyeSelect=make('select');eyeSelect.setAttribute('aria-label','Œil à régler');['Gauche','Droit'].forEach((name,index)=>{const option=make('option',name);option.value=index;eyeSelect.append(option);});eyeSelect.onchange=()=>{selectedEye=Number(eyeSelect.value);refresh();};eyeLabel.append(eyeSelect);toolbar.append(eyeLabel);root.eyeSelect=eyeSelect;}
  const historyBar=make('div',undefined,'buttons');
  const undo=button('Annuler',()=>{if(!history.length)return;future.push(clone(shape));shape=history.pop();changed();});
  const redo=button('Rétablir',()=>{if(!future.length)return;history.push(clone(shape));shape=future.pop();changed();});
  const fromPreset=button('Copier la pose sélectionnée',()=>{
   if(!replaceAllowed())return;
   shape=isMouth?BenderFace.mouthPreset(Number($('mouthPose').value),$('teeth').value==='rounded'):BenderShapes.eyesPreset($('emotion').value);
   resetEdit();status.textContent=isMouth?'Copie de la pose : ajuste-la puis donne-lui un nom.':'Copie paramétrique de l’expression : ajuste les paupières pour l’affiner.';refresh();
  });
  const fresh=button('Nouvelle création',()=>{if(!replaceAllowed())return;shape=isMouth?BenderFace.mouthPreset(0):BenderShapes.eyesPreset('normal');resetEdit();refresh();});
  historyBar.append(fromPreset,fresh,undo,redo);
  const settings=make('details',undefined,'numeric-settings');settings.append(make('summary','Réglages précis · accessibles au clavier'));
  const grid=make('div',undefined,'editor-fields');settings.append(grid);
  function snapshot(){history.push(clone(shape));if(history.length>60)history.shift();future=[];}
  function changed(){unsaved.add(kind);status.textContent='Modifications non enregistrées.';refresh();}
  function replaceAllowed(){return !unsaved.has(kind)||window.confirm('Remplacer les modifications non enregistrées de cet éditeur ?');}
  function resetEdit(){identifier=revision=null;history=[];future=[];name.value='';unsaved.delete(kind);}
  function numeric(label,min,max,step,get,set){
   const row=make('label',label);const input=make('input');input.type='number';input.min=min;input.max=max;input.step=step;input.setAttribute('aria-label',`${isMouth?'Bouche':'Yeux'} · ${label}`);
   input.addEventListener('change',()=>{const value=Number(input.value);if(!Number.isFinite(value)||input.value===''){refresh();return;}snapshot();set(clamp(value,min,max));changed();});row.append(input);grid.append(row);bindings.push(()=>{input.value=Number(get().toFixed(3));});
  }
  function constrainMouth(line){for(let i=0;i<=120;i++){shape.top[i]=clamp(shape.top[i],0,80);shape.bottom[i]=clamp(shape.bottom[i],0,80);if(line==='top')shape.top[i]=Math.min(shape.top[i],shape.bottom[i]);else shape.bottom[i]=Math.max(shape.bottom[i],shape.top[i]);}}
  function shiftLip(line,index,value){
   const original=shape[line].slice(),delta=value-original[index];
   for(let i=Math.max(0,index-15);i<=Math.min(120,index+15);i++){
    const next=clamp(original[i]+delta*Math.max(0,1-Math.abs(i-index)/15),0,80);shape[line][i]=next;if(symmetry.checked)shape[line][120-i]=next;
   }constrainMouth(line);
  }
  function changeEye(key,value,point){
   const eye=shape.eyes[selectedEye],other=shape.eyes[1-selectedEye];
   if(point!==undefined){eye[key][point]=value;if(key==='top')eye.top[point]=Math.min(value,eye.bottom[point]);else eye.bottom[point]=Math.max(value,eye.top[point]);
    if(symmetry.checked){other[key][2-point]=eye[key][point];if(key==='top')other.top[2-point]=Math.min(other.top[2-point],other.bottom[2-point]);else other.bottom[2-point]=Math.max(other.bottom[2-point],other.top[2-point]);}
   }else{eye[key]=value;if(symmetry.checked)other[key]=key==='cx'?800-value:value;}
  }
  if(isMouth){
   numeric('Séparations des dents',0,10,1,()=>shape.teeth,value=>{shape.teeth=Math.round(value);});
   numeric('Épaisseur des lignes',1,3,1,()=>shape.thickness,value=>{shape.thickness=Math.round(value);});
   numeric('Masquer sous la ligne Y',0,80,1,()=>shape.cutoff,value=>{shape.cutoff=value;});
   const roundedLabel=make('label',undefined,'editor-inline');const rounded=make('input');rounded.type='checkbox';roundedLabel.append(rounded,document.createTextNode('Dents arrondies'));grid.append(roundedLabel);
   rounded.onchange=()=>{snapshot();shape.rounded=rounded.checked;changed();};bindings.push(()=>{rounded.checked=shape.rounded;});
   for(const line of ['top','bottom'])for(let n=0;n<9;n++){const index=n*15;numeric(`${line==='top'?'Haut':'Bas'} · point ${n+1} (x=${index+4})`,0,80,1,()=>shape[line][index],value=>shiftLip(line,index,value));}
  }else{
   for(const [key,label,min,max] of [['cx','Position horizontale',80,720],['cy','Position verticale',80,400],['rx','Largeur (rayon)',25,200],['ry','Hauteur (rayon)',25,170],['pupil_x','Pupille · décalage horizontal',-200,200],['pupil_y','Pupille · décalage vertical',-170,170],['pupil_size','Taille des pupilles',8,80]])numeric(label,min,max,1,()=>shape.eyes[selectedEye][key],value=>changeEye(key,value));
   for(const line of ['top','bottom'])for(let point=0;point<3;point++)numeric(`${line==='top'?'Paupière haute':'Paupière basse'} · ${['gauche','centre','droite'][point]} (%)`,0,100,1,()=>shape.eyes[selectedEye][line][point]*100,value=>changeEye(line,value/100,point));
   const colorLabel=make('label','Couleur des yeux');const color=make('input');color.type='color';color.setAttribute('aria-label','Couleur des yeux');color.onchange=()=>{snapshot();shape.color=color.value;changed();};bindings.push(()=>{color.value=shape.color;});colorLabel.append(color);grid.append(colorLabel);
  }
  function handles(){
   if(isMouth){if(tool.value!=='handles')return [];return ['top','bottom'].flatMap(line=>Array.from({length:9},(_,n)=>({x:4+n*15,y:shape[line][n*15],line,index:n*15,color:line==='top'?'#ffbf7a':'#97e6ba'})));}
   return shape.eyes.flatMap((eye,eyeIndex)=>tool.value==='geometry'?[
    {x:eye.cx,y:eye.cy,key:'position',eyeIndex,color:'#bbd7f3'},
    {x:eye.cx+eye.rx,y:eye.cy,key:'rx',eyeIndex,color:'#c7b0ee'},
    {x:eye.cx,y:eye.cy-eye.ry,key:'ry',eyeIndex,color:'#c7b0ee'}
   ]:[...['top','bottom'].flatMap(line=>[0,1,2].map(point=>({x:eye.cx+(point-1)*eye.rx,y:eye.cy-eye.ry+eye[line][point]*2*eye.ry,line,point,eyeIndex,color:line==='top'?'#ffbf7a':'#97e6ba'}))),{x:eye.cx+eye.pupil_x,y:eye.cy+eye.pupil_y,key:'pupil',eyeIndex,color:'#98cfff'}]);
  }
  function refresh(){
   bindings.forEach(update=>update());undo.disabled=!history.length||saving;redo.disabled=!future.length||saving;
   ctx.setTransform(canvas.width/width,0,0,canvas.height/height,0,0);
   if(isMouth)BenderShapes.mouth(ctx,shape);else BenderShapes.eyes(ctx,shape);
   const scale=(canvas.getBoundingClientRect().width||canvas.width)/width,radius=7/scale;
   for(const point of handles()){ctx.beginPath();ctx.arc(point.x,point.y,radius,0,Math.PI*2);ctx.fillStyle=point.color;ctx.fill();ctx.lineWidth=1.5/scale;ctx.strokeStyle='#152025';ctx.stroke();}
  }
  function coordinates(event){const rect=canvas.getBoundingClientRect();return {x:(event.clientX-rect.left)*width/rect.width,y:(event.clientY-rect.top)*height/rect.height};}
  function drawStroke(line,point,last){
   const index=clamp(Math.round(point.x-4),0,120),value=clamp(Math.round(point.y),0,80);
   const before=last||{index,value};
   const start=Math.min(index,before.index),end=Math.max(index,before.index);
   for(let i=start;i<=end;i++){const t=index===before.index?1:(i-before.index)/(index-before.index);const y=clamp(before.value+(value-before.value)*t,0,80);shape[line][i]=y;if(symmetry.checked)shape[line][120-i]=y;}
   constrainMouth(line);return {index,value};
  }
  canvas.addEventListener('pointerdown',event=>{
   if(saving||event.button!==0)return;const point=coordinates(event);
   if(isMouth&&tool.value!=='handles'){snapshot();drag={line:tool.value,stroke:true,last:drawStroke(tool.value,point)};changed();}
   else{
    const candidates=handles().sort((a,b)=>Math.hypot(a.x-point.x,a.y-point.y)-Math.hypot(b.x-point.x,b.y-point.y));
    const closest=candidates[0],radius=18*width/canvas.getBoundingClientRect().width;
    if(!closest||Math.hypot(closest.x-point.x,closest.y-point.y)>radius)return;
    snapshot();drag=closest;if(!isMouth){selectedEye=drag.eyeIndex;root.eyeSelect.value=String(selectedEye);refresh();}
   }canvas.setPointerCapture(event.pointerId);event.preventDefault();
  });
  canvas.addEventListener('pointermove',event=>{
   if(!drag)return;const point=coordinates(event);
   if(isMouth){if(drag.stroke)drag.last=drawStroke(drag.line,point,drag.last);else shiftLip(drag.line,drag.index,clamp(Math.round(point.y),0,80));}
   else{
    const eye=shape.eyes[selectedEye];
    if(drag.line)changeEye(drag.line,clamp((point.y-eye.cy+eye.ry)/(2*eye.ry),0,1),drag.point);
    else if(drag.key==='position'){changeEye('cx',clamp(point.x,80,720));changeEye('cy',clamp(point.y,80,400));}
    else if(drag.key==='pupil'){changeEye('pupil_x',clamp(point.x-eye.cx,-200,200));changeEye('pupil_y',clamp(point.y-eye.cy,-170,170));}
    else if(drag.key==='rx')changeEye('rx',clamp(Math.abs(point.x-eye.cx),25,200));
    else if(drag.key==='ry')changeEye('ry',clamp(Math.abs(point.y-eye.cy),25,170));
   }changed();
  });
  for(const event of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(event,()=>{drag=null;});
  tool.onchange=refresh;
  root.parentElement.addEventListener('toggle',refresh);
  window.addEventListener('resize',refresh);
  const nameLabel=make('label','Nom de la création');const name=make('input');name.type='text';name.maxLength=80;name.placeholder=isMouth?'Ex. : sourire discret':'Ex. : regard curieux';name.setAttribute('aria-label',`Nom ${isMouth?'de la bouche':'des yeux'}`);nameLabel.append(name);name.oninput=()=>{unsaved.add(kind);status.textContent='Modifications non enregistrées.';};
  const saveBar=make('div',undefined,'buttons');
  async function saveCreation(copy){
   if(saving)return;const title=name.value.trim();if(!title){status.textContent='Donne un nom à ta création.';name.focus();return;}
   saving=true;save.disabled=saveCopy.disabled=true;status.textContent='Enregistrement…';
   try{
    const updating=identifier&&!copy;
    const data=await request('/api/poses'+(updating?'/'+identifier:''),{method:updating?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:title,definition:shape,...(updating?{revision}:{})})});
    identifier=data.id;revision=data.revision;unsaved.delete(kind);
    await reloadLibrary();libraries[kind].select.value=identifier;status.textContent='✓ Création enregistrée sur Bender. Elle est disponible dans Mes créations.';
   }catch(error){status.textContent=error.message;}
   finally{saving=false;save.disabled=saveCopy.disabled=false;refresh();}
  }
  const save=button('Enregistrer',()=>saveCreation(false));
  const saveCopy=button('Enregistrer une copie',()=>saveCreation(true));
  const test=button('Tester dans l’atelier',async()=>{try{await apply(kind,shape,name.value);}catch(error){status.textContent=error.message;}});
  const exportButton=button('Exporter JSON',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({version:1,name:name.value||'Création',definition:shape},null,2)],{type:'application/json'}));const anchor=make('a');anchor.href=url;anchor.download=`bender-${kind}-creation.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  saveBar.append(save,saveCopy,test,exportButton);
  const legend=make('p','Orange : ligne haute · Vert : ligne basse · Bleu : pupille / position. Les réglages précis permettent aussi de travailler sans glisser-déposer.','editor-help');
  root.append(instructions,toolbar,canvas,legend,historyBar,settings,nameLabel,saveBar,status);
  refresh();
  return {load(item){if(!replaceAllowed())return;shape=clone(item.definition);identifier=item.id;revision=item.revision;name.value=item.name;history=[];future=[];unsaved.delete(kind);root.parentElement.open=true;status.textContent='Création chargée. Enregistrer met à jour celle-ci ; une copie nécessite un autre nom.';refresh();root.parentElement.scrollIntoView({block:'start',behavior:'smooth'});}};
 }
 for(const kind of ['eyes','mouth']){library(kind);editors[kind]=editor(kind);}
 reloadLibrary().catch(error=>{for(const entry of Object.values(libraries))entry.message.textContent=error.message;});
})();
