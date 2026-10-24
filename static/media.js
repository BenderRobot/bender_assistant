'use strict';
(() => {
 const stateNames={pending:'En attente',processing:'Analyse en cours',review:'À vérifier',approved:'Sélections validées',error:'À reprendre'};
 const stages=[['preparation','Préparation','Audio et images'],['transcription','Transcription','Whisper · en local'],['analysis','Analyse GPT','Noms et catégories'],['validation','Validation','Par toi, après écoute']];
 let transcriber={engine:'faster-whisper',model:'medium'};
 let voiceReferences={};
 const engineName=source=>source?.engine==='manual'?'Correction manuelle':source?.engine==='faster-whisper'?`Whisper ${source.model||''}`:source?.engine==='vosk'?'Vosk':'Ancienne transcription';
 const contentVersion=item=>JSON.stringify([item.state,item.error,item.media,item.analysis,item.approved]);
 let items=[],selected=null,loaded=false,dirty=false,version=null,urls=[],loading=false;
 let listVersion=null,countVersion=null,activityVersion=null,selectedProgressVersion=null;
 const el=id=>document.getElementById(id),make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
 function revoke(){urls.forEach(url=>URL.revokeObjectURL(url));urls=[];}
 async function execute(button,action){button.disabled=true;el('mediaError').textContent='';try{await action();}catch(error){el('mediaError').textContent=error.message;}finally{button.disabled=false;}}
 function duration(seconds){const value=Math.max(0,Math.floor(seconds));return value<60?`${value} s`:`${Math.floor(value/60)} min ${value%60} s`;}
 function progressView(item){
  const root=make('div'),p=item.progress||{},done=new Set((p.completed||[]).map(entry=>entry.stage));root.className='media-progress-view';
  // Existing catalog entries can predate checkpoints; infer only known outcomes.
  if(item.media.audio)done.add('preparation');if(item.media.transcribed&&item.media.transcript)done.add('transcription');
  if(['review','approved'].includes(item.state))['preparation','transcription','analysis'].forEach(stage=>done.add(stage));
  if(item.state==='approved')done.add('validation');
  const track=make('ol');track.className='media-stages';
  for(const [key,label,caption] of stages){
   const complete=done.has(key),active=!complete&&p.stage===key;
   const status=complete?'done':active&&item.state==='error'?'error':active&&item.state==='processing'?'current':'waiting';
   const step=make('li');step.className=`media-stage ${status}`;
   const reused=(p.completed||[]).some(entry=>entry.stage===key&&entry.reused);
   const source=key==='transcription'?(complete?item.media.transcription:transcriber):null;
   const subtitle=key==='transcription'?engineName(source)+' · local':caption;
   step.append(make('span',complete?'✓':status==='error'?'!':String(stages.findIndex(s=>s[0]===key)+1)),make('strong',label),make('small',reused?'Déjà disponible':subtitle));
   if(status==='current')step.setAttribute('aria-current','step');track.append(step);
  }
  root.append(track);
  const message=item.state==='error'?item.error:item.state==='approved'?'Sélections conservées pour leurs usages validés.':item.state==='review'?'Analyse terminée. Vérifie les passages proposés avant de les utiliser.':p.detail||(item.state==='pending'?'Dans la file, en attente de traitement.':'Traitement lancé ; attente du prochain point de suivi.');
  root.append(make('p',message));
  if(item.state==='processing'){
   const bar=make('progress');bar.max=1;bar.setAttribute('aria-label',`Avancement : ${stages.find(s=>s[0]===p.stage)?.[1]||'traitement'}`);
   const measured=Number.isFinite(p.current)&&Number.isFinite(p.total)&&p.total>0;
   if(measured){bar.value=Math.min(1,Math.max(0,p.current/p.total));root.append(make('p',`${Math.round(bar.value*100)} % de cette opération`));}
   root.append(bar);
   if(p.stage_started){const elapsed=make('p');elapsed.className='media-timing';elapsed.dataset.since=String(p.stage_started);elapsed.textContent=`Étape commencée il y a ${duration(Date.now()/1000-p.stage_started)}`;root.append(elapsed);}
   if(p.updated)root.append(make('small',`Dernier point de traitement : ${new Date(p.updated*1000).toLocaleTimeString('fr-FR')}.`));
  }else if(p.started&&p.finished&&p.status==='done')root.append(make('small',`Analyse effectuée en ${duration(p.finished-p.started)} · progression conservée sur Bender.`));
  return root;
 }
 function drawDashboard(worker){
  const counts=Object.fromEntries(Object.keys(stateNames).map(state=>[state,items.filter(item=>item.state===state).length]));
  const cards=Object.entries(stateNames).map(([state,label])=>{
   const card=make('button');card.className=`media-count ${state}`;card.setAttribute('aria-label',`${counts[state]} sample(s) : ${label}`);
   card.append(make('strong',String(counts[state])),make('span',label));card.onclick=()=>{el('mediaFilter').value=state;drawList();};return card;
  });const countKey=JSON.stringify(counts);
  if(countVersion!==countKey){el('mediaCounts').replaceChildren(...cards);countVersion=countKey;}
  const finished=counts.review+counts.approved,batch=el('mediaBatch');batch.replaceChildren();
  batch.append(make('p',items.length?`${finished} / ${items.length} analyses terminées · ${counts.review} à vérifier · ${counts.error} en erreur`:'Aucun sample importé pour le moment.'));
  if(items.length){const bar=make('progress');bar.max=items.length;bar.value=finished;bar.setAttribute('aria-label','Samples dont l’analyse est terminée');batch.append(bar);}
  el('mediaSync').textContent=`Synchronisé à ${new Date().toLocaleTimeString('fr-FR')}`;
  const active=items.find(item=>item.state==='processing'),activityKey=JSON.stringify([active,worker.automatic,worker.message,counts,items.filter(item=>item.state==='pending').map(item=>[item.id,item.error])]);
  if(activityVersion===activityKey)return;
  activityVersion=activityKey;const activity=el('mediaActivity');activity.replaceChildren();
  if(active){
   const heading=make('div');heading.className='media-current-heading';heading.append(make('span','● En cours'),make('strong',active.original_name));
   const view=make('button','Voir ce sample');view.onclick=()=>{selected=active.id;dirty=false;drawList();drawDetail(active);el('mediaDetail').scrollIntoView({behavior:'smooth',block:'nearest'});};heading.append(view);
   activity.append(heading,progressView(active));
   if(!worker.automatic)activity.append(make('p','Pause demandée : le sample en cours se termine, puis la file s’arrête.'));
  }else{
   const waiting=items.filter(item=>item.state==='pending').sort((a,b)=>a.created-b.created),blocked=waiting.find(item=>item.error);
   activity.append(make('strong',!worker.automatic?'Analyses en pause':blocked?'File en attente d’une action':counts.error?'Des samples sont à reprendre':counts.pending?'File prête à reprendre':items.length?'Traitement terminé':'Prêt à recevoir tes samples'));
   activity.append(make('p',blocked?.error||worker.message));
   if(waiting.length)activity.append(make('p',`Prochain dans la file : ${waiting[0].original_name} · ${waiting.length} en attente.`));
  }
 }
 function drawList(){
  const query=el('mediaSearch').value.toLocaleLowerCase('fr'),filter=el('mediaFilter').value;
  const filtered=items.filter(item=>(!filter||item.state===filter)&&JSON.stringify([item.original_name,item.analysis,item.media.transcript]).toLocaleLowerCase('fr').includes(query));
  const key=JSON.stringify([query,filter,loaded,selected,filtered.map(item=>[item.id,item.state,item.analysis.title,item.media.duration,item.progress?.stage])]);
  if(listVersion===key)return;listVersion=key;
  el('mediaList').replaceChildren(...filtered.map(item=>{
   const button=make('button');button.className='media-tile';button.setAttribute('aria-pressed',String(selected===item.id));
   button.append(make('strong',item.analysis.title||item.original_name),make('span',`${stateNames[item.state]} · ${item.media.duration?item.media.duration.toFixed(1)+' s':'à préparer'}`));
   if(item.state==='processing')button.append(make('small',stages.find(s=>s[0]===item.progress?.stage)?.[1]||'Démarrage…'));
   button.onclick=()=>{selected=item.id;dirty=false;version=null;drawList();drawDetail(item);};return button;
  }));
  if(!filtered.length)el('mediaList').append(make('p',loaded?'Aucun sample correspondant.':'Charge la bibliothèque pour commencer.'));
 }
 async function refresh(){
  if(loading)return;loading=true;
  try{
   const data=await(await ioFetch('/api/media',null,'GET')).json();items=data.items;loaded=true;
   window.BenderVersions?.update(data.versions);
   const previousReferences=JSON.stringify(voiceReferences);voiceReferences=data.voice_references||{};
   if(previousReferences!==JSON.stringify(voiceReferences))version=null;
   if(data.worker.transcription)transcriber=data.worker.transcription;
   el('mediaTranscriptionStatus').textContent=transcriber.engine==='faster-whisper'?`Samples : Whisper ${transcriber.model} · français · processeur · ${transcriber.ready&&transcriber.installed?'prêt hors ligne':'installation nécessaire via la mise à jour'}`:'Samples : Vosk sélectionné dans la configuration.';
   el('mediaAutomatic').checked=data.worker.automatic;
   const pending=items.filter(item=>['pending','processing'].includes(item.state)).length;
   el('mediaStatus').textContent=`${items.length} sample(s) · ${pending} en attente ou en cours. ${data.worker.message}`;
   drawDashboard(data.worker);drawList();const current=items.find(item=>item.id===selected);
   if(current&&!dirty&&version!==contentVersion(current))drawDetail(current);
   else if(current&&el('mediaSelectedProgress')&&selectedProgressVersion!==JSON.stringify(current.progress)){
    el('mediaSelectedProgress').replaceChildren(progressView(current));selectedProgressVersion=JSON.stringify(current.progress);
   }
  }catch(error){el('mediaSync').textContent='Actualisation impossible · dernier état conservé';throw error;
  }finally{loading=false;}
 }
 function input(parent,label,type,value,options){
  const wrapper=make('label',label),node=make(type==='select'?'select':'input');
  if(type==='select')node.replaceChildren(...options.map(([value,label])=>new Option(label,value)));
  else node.type=type;
  node.value=value;wrapper.append(node);parent.append(wrapper);node.oninput=()=>{dirty=true;};return node;
 }
 function drawDetail(item){
  revoke();version=contentVersion(item);const root=el('mediaDetail');root.replaceChildren();
  root.append(make('h3',item.analysis.title||item.original_name),make('p',`${item.original_name} · ${stateNames[item.state]}`));
  const progress=make('div');progress.id='mediaSelectedProgress';progress.append(progressView(item));root.append(progress);selectedProgressVersion=JSON.stringify(item.progress);
  if(item.analysis.summary)root.append(make('p',item.analysis.summary));
  if(item.analysis.categories)root.append(make('p',item.analysis.categories.join(' · ')));
  if(item.analysis.basis)root.append(make('p',item.analysis.basis));
  (item.analysis.warnings||[]).forEach(warning=>root.append(make('p',warning)));
  (item.media.warnings||[]).forEach(warning=>root.append(make('p',warning)));
  if(item.media.metrics)root.append(make('p',`Mesures locales : niveau ${item.media.metrics.rms_dbfs} dBFS · échantillons écrêtés ${item.media.metrics.clipped_percent} %. La musique et les autres locuteurs doivent être vérifiés à l’écoute.`));
  const transcript=make('textarea');transcript.rows=4;transcript.maxLength=8000;transcript.disabled=item.state==='processing';transcript.value=item.media.transcript||'';transcript.setAttribute('aria-label','Transcription du sample');transcript.oninput=()=>{dirty=true;};
  root.append(make('h4',engineName(item.media.transcription)+' · à vérifier'),transcript);
  const retry=make('button','Corriger la transcription et relancer GPT');retry.disabled=item.state==='processing';
  retry.onclick=()=>execute(retry,async()=>{await ioFetch(`/api/media/${item.id}/retry`,item.media.audio?{transcript:transcript.value}:{});dirty=false;await refresh();});root.append(retry);
  const redo=make('button',`Retranscrire avec ${engineName(transcriber)}`);redo.disabled=item.state==='processing';
  redo.onclick=()=>execute(redo,async()=>{await ioFetch(`/api/media/${item.id}/retry`,{retranscribe:true});dirty=false;await refresh();});root.append(redo);
  if(item.media.previous_transcription?.text){
   const previous=make('details');previous.append(make('summary','Comparer avec la transcription précédente'),make('p',item.media.previous_transcription.text));root.append(previous);
  }
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
  if(item.approved.length){
   root.append(make('h4','Passages validés'));
   for(const entry of item.approved){
    root.append(make('p',`${entry.title} · ${entry.start.toFixed(2)}-${entry.end.toFixed(2)} s · ${entry.use}${entry.reference_file?' · '+entry.reference_file:''}`));
    if(entry.use==='voice_reference'&&entry.reference_file){
     const active=voiceReferences[entry.mood]===entry.reference_file;
     const activate=make('button',active?`Référence Chatterbox active · ${entry.mood}`:`Utiliser cette voix avec Chatterbox · ${entry.mood}`);
     activate.disabled=active;
     activate.onclick=()=>execute(activate,async()=>{const result=await(await ioFetch(`/api/media/${item.id}/reference`,{selection_id:entry.selection_id})).json();dirty=false;await refresh();el('mediaStatus').textContent=result.note;});root.append(activate);
    }
   }
  }
  const frames=make('div');frames.className='media-frames';root.append(frames);
  for(const frame of item.media.frames||[]){
   const card=make('figure');card.append(make('figcaption',`${frame.time.toFixed(2)} s`));frames.append(card);
   const expression=item.analysis.expressions?.find(value=>Math.abs(value.time-frame.time)<0.1);
   if(expression)card.append(make('p',`Bouche : ${expression.mouth} · Yeux : ${expression.eyes}${expression.pose===null?'':` · Pose proposée ${expression.pose+1}`}`));
   ioFetch(frame.url,null,'GET').then(response=>response.blob()).then(blob=>{if(selected!==item.id)return;const image=make('img');const url=URL.createObjectURL(blob);urls.push(url);image.src=url;image.alt=`Image de référence à ${frame.time} secondes`;card.prepend(image);}).catch(()=>card.append(make('p','Image indisponible.')));
  }
 }
 el('mediaRefresh').onclick=()=>execute(el('mediaRefresh'),refresh);
 window.BenderMedia={openSample(identifier){
  const item=items.find(item=>item.id===identifier);if(!item)return;
  selected=identifier;dirty=false;version=null;drawList();drawDetail(item);
  el('mediaDetail').scrollIntoView({behavior:'smooth',block:'nearest'});
 }};
 el('mediaResume').onclick=()=>execute(el('mediaResume'),async()=>{await ioFetch('/api/media/resume');await refresh();});
 el('mediaRetranscribeLegacy').onclick=()=>execute(el('mediaRetranscribeLegacy'),async()=>{const result=await(await ioFetch('/api/media/retranscribe-legacy')).json();await refresh();el('mediaStatus').textContent=`${result.queued} ancienne(s) transcription(s) remise(s) dans la file. Les validations et corrections manuelles identifiées sont conservées.`;});
 el('mediaAutomatic').onchange=()=>execute(el('mediaAutomatic'),async()=>{await ioFetch('/api/media/options',{automatic:el('mediaAutomatic').checked});await refresh();});
 el('mediaSearch').oninput=el('mediaFilter').onchange=drawList;
 setInterval(()=>{
  if(el('panel-samples').hidden)return;
  document.querySelectorAll('.media-timing[data-since]').forEach(node=>{node.textContent=`Étape commencée il y a ${duration(Date.now()/1000-Number(node.dataset.since))}`;});
  if(loaded)refresh().catch(error=>{el('mediaError').textContent=error.message;});
 },2000);
})();
