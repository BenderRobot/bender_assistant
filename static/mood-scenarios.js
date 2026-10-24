'use strict';
(() => {
 const el=id=>document.getElementById(id);if(!el('moodScenarios'))return;
 const eyes=[['normal','Normaux'],['sad','Tristes'],['worried','Inquiets'],['crying','Pleurs'],['angry','En colère'],['happy','Heureux'],['surprised','Surpris'],['sleepy','Lassés'],...Array.from({length:5},(_,i)=>['ref'+(i+1),'Référence '+(i+1)])];
 let catalog=null,current=null,customs=[],recordings=[],libraryStamp='';
 const option=(value,label)=>{const node=document.createElement('option');node.value=value;node.textContent=label;return node;};
 function recordingOptions(){
  const select=el('scenarioRecording'),selected=select.value;
  select.replaceChildren(option('','Faire prononcer le texte ci-dessous'),...recordings.map(item=>option(item.library_id,item.title)));
  if(current?.library_id&&!recordings.some(item=>item.library_id===current.library_id))select.append(option(current.library_id,'Réplique actuelle introuvable · '+current.library_id));
  select.value=selected||'';
 }
 function recordingText(){
  const item=recordings.find(item=>item.library_id===el('scenarioRecording').value);
  el('scenarioText').readOnly=!!el('scenarioRecording').value;
  if(item)el('scenarioText').value=item.text;
  else if(!el('scenarioRecording').value&&current)el('scenarioText').value=current.text;
 }
 function fill(){
  current=catalog?.items.find(item=>item.id===el('scenarioChoice').value)||null;
  el('saveScenario').disabled=el('copyScenario').disabled=!current;
  if(!current)return;
  el('scenarioName').value=current.name;el('scenarioText').value=current.text;el('scenarioEnabled').checked=current.enabled;
  recordingOptions();el('scenarioRecording').value=current.library_id||'';recordingText();
  el('scenarioEyes').replaceChildren(...eyes.map(([value,label])=>option(value,label)),
   ...customs.map(item=>option('custom:'+item.id,'Création · '+item.name)));
  if(current.custom_eyes)el('scenarioEyes').append(option('stored','Yeux personnalisés enregistrés'));
  el('scenarioEyes').value=current.custom_eyes?'stored':current.eyes;
 }
 function choices(){
  const available=(catalog?.items||[]).filter(item=>item.mood===el('scenarioMood').value&&item.intensity===Number(el('scenarioIntensity').value));
  el('scenarioChoice').replaceChildren(...available.map(item=>option(item.id,item.name+(item.enabled?'':' · désactivé'))));
  if(!available.length)el('scenarioChoice').append(option('','Aucun scénario ; recharge les modèles de départ'));
  fill();
 }
 async function action(button,callback){
  button.disabled=true;el('mediaError').textContent='';
  try{await callback();}catch(error){el('mediaError').textContent=error.message;}finally{button.disabled=false;}
 }
 async function load(){
  const results=await Promise.allSettled([
   ioFetch('/api/moods',null,'GET').then(r=>r.json()),
   fetch('/api/poses').then(r=>{if(!r.ok)throw Error();return r.json();}),
   ioFetch('/api/media/versions',null,'GET').then(r=>r.json())]);
  if(results[0].status==='rejected')throw results[0].reason;
  catalog=results[0].value;
  customs=results[1].status==='fulfilled'?results[1].value.items.filter(item=>item.kind==='eyes'):[];
  if(results[2].status==='fulfilled')window.BenderMoods.updateLibrary(results[2].value);
  choices();el('scenarioResult').textContent=`${catalog.items.filter(item=>item.enabled).length} scénarios actifs · 3 intensités · tirage sans répétition immédiate quand plusieurs variantes sont actives.`;
 }
 async function save(copy){
  if(!current)throw Error('Charge d’abord les scénarios.');
  const selected=el('scenarioEyes').value;
  const custom=selected==='stored'?current.custom_eyes:customs.find(item=>'custom:'+item.id===selected)?.definition||null;
  const scenario={...current,name:el('scenarioName').value,text:el('scenarioText').value,
   eyes:custom?current.eyes:selected,custom_eyes:custom,library_id:el('scenarioRecording').value||null,enabled:el('scenarioEnabled').checked};
  const data=await(await ioFetch('/api/moods',{revision:catalog.revision,scenario,copy})).json();
  catalog=data;choices();
  if(copy){el('scenarioChoice').value=data.items.at(-1).id;fill();}
  el('scenarioResult').textContent='Scénario enregistré sur Bender. Le prochain tirage utilisera cette configuration.';
 }
 window.BenderMoods={
  updateLibrary(data){
   const next=JSON.stringify(data.selections);if(next===libraryStamp)return;libraryStamp=next;
   recordings=data.selections.filter(item=>item.use==='quote'&&item.ready_for_response);
   recordingOptions();
  },
  showResult(data){
   const scene=data?.mood_scenario;
   if(!scene){if(el('moodReaction'))el('moodReaction').hidden=true;return;}
   el('scenarioResult').textContent=`Scénario joué : ${scene.name} · intensité ${scene.intensity}/3 · yeux ${scene.eyes}. ${data.note||''}`;
   const labels={sad:'Triste',neutral:'Neutre',sarcastic:'Sarcastique',angry:'Agacé',excited:'Énergique'};
   const note=el('moodReaction');if(note){note.hidden=false;note.textContent=`Humeur : ${labels[scene.mood]} · intensité ${scene.intensity}/3 · ${scene.name}`;}
  }
 };
 el('loadScenarios').onclick=()=>action(el('loadScenarios'),load);
 el('scenarioMood').onchange=el('scenarioIntensity').onchange=choices;
 el('scenarioChoice').onchange=fill;el('scenarioRecording').onchange=recordingText;
 el('saveScenario').onclick=()=>action(el('saveScenario'),()=>save(false));
 el('copyScenario').onclick=()=>action(el('copyScenario'),()=>save(true));
 el('testScenario').onclick=()=>action(el('testScenario'),async()=>{
  if(activePreparation||preparationStarting)throw Error('Une réponse est déjà en préparation.');
  const adjectives={sad:'triste',neutral:'neutre',sarcastic:'sarcastique',angry:'agacé',excited:'joyeux'};
  el('text').value=`Sois ${adjectives[el('scenarioMood').value]} niveau ${el('scenarioIntensity').value}`;
  await perform(true);
 });
})();
