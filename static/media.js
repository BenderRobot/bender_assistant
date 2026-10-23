'use strict';
(() => {
 const stateNames={pending:'En attente',processing:'Analyse en cours',review:'À vérifier',approved:'Sélections validées',error:'À reprendre'};
 let items=[],selected=null,loaded=false,dirty=false,version=null,urls=[],loading=false;
 const el=id=>document.getElementById(id),make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
 function revoke(){urls.forEach(url=>URL.revokeObjectURL(url));urls=[];}
 async function execute(button,action){button.disabled=true;el('mediaError').textContent='';try{await action();}catch(error){el('mediaError').textContent=error.message;}finally{button.disabled=false;}}
 function drawList(){
  const query=el('mediaSearch').value.toLocaleLowerCase('fr'),filter=el('mediaFilter').value;
  const filtered=items.filter(item=>(!filter||item.state===filter)&&JSON.stringify([item.original_name,item.analysis,item.media.transcript]).toLocaleLowerCase('fr').includes(query));
  el('mediaList').replaceChildren(...filtered.map(item=>{
   const button=make('button');button.className='media-tile';button.setAttribute('aria-pressed',String(selected===item.id));
   button.append(make('strong',item.analysis.title||item.original_name),make('span',`${stateNames[item.state]} · ${item.media.duration?item.media.duration.toFixed(1)+' s':'à préparer'}`));
   button.onclick=()=>{selected=item.id;dirty=false;version=null;drawList();drawDetail(item);};return button;
  }));
  if(!filtered.length)el('mediaList').append(make('p',loaded?'Aucun sample correspondant.':'Charge la bibliothèque pour commencer.'));
 }
 async function refresh(){
  if(loading)return;loading=true;
  try{
   const data=await(await ioFetch('/api/media',null,'GET')).json();items=data.items;loaded=true;
   el('mediaAutomatic').checked=data.worker.automatic;
   const pending=items.filter(item=>['pending','processing'].includes(item.state)).length;
   el('mediaStatus').textContent=`${items.length} sample(s) · ${pending} en attente ou en cours. ${data.worker.message}`;
   drawList();const current=items.find(item=>item.id===selected);
   if(current&&!dirty&&version!==current.updated)drawDetail(current);
  }finally{loading=false;}
 }
 function input(parent,label,type,value,options){
  const wrapper=make('label',label),node=make(type==='select'?'select':'input');
  if(type==='select')node.replaceChildren(...options.map(([value,label])=>new Option(label,value)));
  else node.type=type;
  node.value=value;wrapper.append(node);parent.append(wrapper);node.oninput=()=>{dirty=true;};return node;
 }
 function drawDetail(item){
  revoke();version=item.updated;const root=el('mediaDetail');root.replaceChildren();
  root.append(make('h3',item.analysis.title||item.original_name),make('p',`${item.original_name} · ${stateNames[item.state]}`));
  if(item.error)root.append(make('p',item.error));
  if(item.analysis.summary)root.append(make('p',item.analysis.summary));
  if(item.analysis.categories)root.append(make('p',item.analysis.categories.join(' · ')));
  if(item.analysis.basis)root.append(make('p',item.analysis.basis));
  (item.analysis.warnings||[]).forEach(warning=>root.append(make('p',warning)));
  (item.media.warnings||[]).forEach(warning=>root.append(make('p',warning)));
  if(item.media.metrics)root.append(make('p',`Mesures locales : niveau ${item.media.metrics.rms_dbfs} dBFS · échantillons écrêtés ${item.media.metrics.clipped_percent} %. La musique et les autres locuteurs doivent être vérifiés à l’écoute.`));
  const transcript=make('textarea');transcript.rows=4;transcript.maxLength=8000;transcript.disabled=item.state==='processing';transcript.value=item.media.transcript||'';transcript.setAttribute('aria-label','Transcription du sample');transcript.oninput=()=>{dirty=true;};
  root.append(make('h4','Transcription Vosk · à vérifier'),transcript);
  const retry=make('button','Corriger la transcription et relancer GPT');retry.disabled=item.state==='processing';
  retry.onclick=()=>execute(retry,async()=>{await ioFetch(`/api/media/${item.id}/retry`,item.media.audio?{transcript:transcript.value}:{});dirty=false;await refresh();});root.append(retry);
  if(!item.media.audio||item.state==='processing')return;
  const form=make('div');root.append(form);
  form.append(make('h4','Choisir et valider un passage'));
  const usage=input(form,'Usage','select','quote',[['quote','Réplique contextuelle'],['voice_reference','Référence vocale candidate'],['expression','Repère bouche / yeux']]);
  const title=input(form,'Nom du passage','text',item.analysis.title||item.original_name);
  const range=make('div');range.className='grid';form.append(range);
  const start=input(range,'Début (secondes)','number',0),end=input(range,'Fin (secondes)','number',Math.min(item.media.duration,10));
  [start,end].forEach(node=>{node.min=0;node.max=item.media.duration;node.step=0.01;});
  const text=make('textarea');text.rows=2;text.maxLength=1000;text.value=(item.media.transcript||'').slice(0,1000);text.setAttribute('aria-label','Texte exact du passage');text.oninput=()=>{dirty=true;};form.append(make('label','Texte exact du passage'),text);
  const mood=input(form,'Humeur proposée · à confirmer','select',item.analysis.mood||'neutral',[['neutral','Neutre'],['sarcastic','Sarcastique'],['angry','Agacé'],['excited','Énergique'],['sad','Triste']]);
  const triggers=input(form,'Mots déclencheurs pour les répliques · séparés par des virgules','text',(item.analysis.triggers||[]).join(', '));
  const reason=make('p');form.append(reason);
  if(item.analysis.segments?.length){
   const choices=input(form,'Passages suggérés par GPT','select','',[['','Choisir une suggestion'],...item.analysis.segments.map((segment,i)=>[String(i),`${segment.start.toFixed(2)}–${segment.end.toFixed(2)} s · ${segment.use} · ${segment.text.slice(0,70)}`])]);
   choices.onchange=()=>{if(choices.value==='')return;const segment=item.analysis.segments[Number(choices.value)];start.value=segment.start;end.value=segment.end;text.value=segment.text;usage.value=segment.use;reason.textContent=segment.reason;dirty=true;};
  }
  const audio=make('audio');audio.controls=true;audio.preload='metadata';form.append(audio);
  audio.ontimeupdate=()=>{if(audio.currentTime>=Number(end.value))audio.pause();};
  const listen=make('button','Écouter le passage choisi');
  listen.onclick=()=>execute(listen,async()=>{
   const response=await ioFetch(`/api/media/${item.id}/audio`,null,'GET');const url=URL.createObjectURL(await response.blob());
   if(selected!==item.id){URL.revokeObjectURL(url);return;}urls.push(url);audio.src=url;
   audio.onloadedmetadata=()=>{audio.currentTime=Number(start.value);audio.play().catch(error=>{el('mediaError').textContent=error.message;});};
  });form.append(listen);
  const verifiedLabel=make('label');verifiedLabel.className='inline';const verified=make('input');verified.type='checkbox';verified.onchange=()=>{dirty=true;};verifiedLabel.append(verified,document.createTextNode(' J’ai vérifié à l’écoute : seul Bender parle dans ce passage, sans musique gênante.'));form.append(verifiedLabel);
  const approval=make('button','Valider ce passage');approval.disabled=!['review','approved'].includes(item.state);
  approval.onclick=()=>execute(approval,async()=>{
   const result=await(await ioFetch(`/api/media/${item.id}/approve`,{use:usage.value,start:Number(start.value),end:Number(end.value),text:text.value,title:title.value,mood:mood.value,triggers:triggers.value.split(',').map(word=>word.trim()).filter(Boolean),bender_only:verified.checked})).json();
   dirty=false;await refresh();el('mediaStatus').textContent=result.note||'Passage validé et conservé pour son usage choisi.';
  });form.append(approval);
  form.append(make('p','Une sélection audio dure 30 secondes maximum. Les références vocales restent des candidates à tester avec le moteur de voix. La validation d’une expression conserve un repère, sans modifier les poses déjà créées.'));
  if(item.approved.length)root.append(make('h4','Passages validés'),...item.approved.map(entry=>make('p',`${entry.title} · ${entry.start.toFixed(2)}–${entry.end.toFixed(2)} s · ${entry.use}${entry.reference_file?' · '+entry.reference_file:''}`)));
  const frames=make('div');frames.className='media-frames';root.append(frames);
  for(const frame of item.media.frames||[]){
   const card=make('figure');card.append(make('figcaption',`${frame.time.toFixed(2)} s`));frames.append(card);
   const expression=item.analysis.expressions?.find(value=>Math.abs(value.time-frame.time)<0.1);
   if(expression)card.append(make('p',`Bouche : ${expression.mouth} · Yeux : ${expression.eyes}${expression.pose===null?'':` · Pose proposée ${expression.pose+1}`}`));
   ioFetch(frame.url,null,'GET').then(response=>response.blob()).then(blob=>{if(selected!==item.id)return;const image=make('img');const url=URL.createObjectURL(blob);urls.push(url);image.src=url;image.alt=`Image de référence à ${frame.time} secondes`;card.prepend(image);}).catch(()=>card.append(make('p','Image indisponible.')));
  }
 }
 el('mediaRefresh').onclick=()=>execute(el('mediaRefresh'),refresh);
 el('mediaResume').onclick=()=>execute(el('mediaResume'),async()=>{await ioFetch('/api/media/resume');await refresh();});
 el('mediaAutomatic').onchange=()=>execute(el('mediaAutomatic'),async()=>{await ioFetch('/api/media/options',{automatic:el('mediaAutomatic').checked});await refresh();});
 el('mediaSearch').oninput=el('mediaFilter').onchange=drawList;
 setInterval(()=>{if(loaded&&!el('panel-samples').hidden)refresh().catch(error=>{el('mediaError').textContent=error.message;});},5000);
})();
