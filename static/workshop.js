'use strict';
(() => {
 const el = id => document.getElementById(id);
 const tabs = [...document.querySelectorAll('[role=tab]')];
 function show(name) {
  const chosen = tabs.find(tab => tab.id === `tab-${name}`) || tabs[0];
  tabs.forEach(tab => {
   const active = tab === chosen; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
   el(tab.getAttribute('aria-controls')).hidden = !active;
  });
  if(!display) history.replaceState(null,'',`#${chosen.id.slice(4)}`);
 }
 tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => show(tab.id.slice(4)));
  tab.addEventListener('keydown', event => {
   const target = event.key === 'ArrowRight' ? (i+1)%tabs.length : event.key === 'ArrowLeft' ? (i+tabs.length-1)%tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : -1;
   if(target >= 0) { event.preventDefault(); show(tabs[target].id.slice(4)); tabs[target].focus(); }
  });
 });
 show(location.hash.slice(1));
 window.addEventListener('hashchange',()=>show(location.hash.slice(1)));
 let eyeTimer, mouthTimer;
 window.stopWorkshopDemos = () => { clearInterval(eyeTimer); clearInterval(mouthTimer); eyeTimer=mouthTimer=null; };
 function updateEyes() {
  if(!timeline&&!hostPlaying)sendFace({...face,eyes:el('emotion').value,mode:el('eyeMode').value,blink:el('eyeBlink').checked});
  el('eyePreviewStatus').textContent=el('emotion').selectedOptions[0].textContent+' · '+el('eyeMode').selectedOptions[0].textContent;
 }
 el('emotion').addEventListener('change',updateEyes);
 el('eyeMode').addEventListener('change',updateEyes);
 el('eyeBlink').addEventListener('change',updateEyes);
 el('demoEyes').onclick=async()=>{
  await stop(); let i=0;
  const advance=()=>{el('emotion').selectedIndex=i++%el('emotion').options.length;if(window.BenderCustomSelection)window.BenderCustomSelection.eyes=null;updateEyes();};
  advance(); eyeTimer=setInterval(advance,1500);
 };
 el('stopEyes').onclick=()=>{clearInterval(eyeTimer);eyeTimer=null;};
 function mouthFrame() {
  if(window.BenderCustomSelection)window.BenderCustomSelection.mouth=null;
  const pose=Number(el('mouthPose').value);
  sendFace({pose,eyes:el('emotion').value,active:false,rounded:el('teeth').value==='rounded',mode:el('eyeMode').value,blink:el('eyeBlink').checked});
  el('poseState').textContent=el('mouthPose').selectedOptions[0].textContent;
 }
 async function manualMouth(){await stop();mouthFrame();}
 el('previewMouth').onclick=manualMouth;
 el('mouthPose').onchange=manualMouth;el('teeth').onchange=manualMouth;
 el('demoMouth').onclick=async()=>{await stop();let i=0;const advance=()=>{el('mouthPose').value=String(i++%12);mouthFrame();};advance();mouthTimer=setInterval(advance,1300);};
 el('stopMouth').onclick=()=>{clearInterval(mouthTimer);mouthTimer=null;};
 let recordings=[];
 const methodNames={visual:'Calage visuel manuel provisoire',phonemes:'Phonèmes estimés · calage conservé',acoustic:'Estimation acoustique'};
 function methods(){
  const entry=recordings[Number(el('recording').value)];
  const values=entry?.kind==='library'?['library']:entry?.methods||[];
  el('recordingMethod').replaceChildren(...values.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=methodNames[value]||'Calage de la bibliothèque';return option;}));
  if(values.includes('visual'))el('recordingMethod').value='visual';
 }
 async function loadRecordings(){
  el('refreshRecordings').disabled=true;
  try{
   const res=await fetch('/api/bench/recordings',{cache:'no-store'});if(!res.ok)throw Error();const data=await res.json();
   recordings=[...data.references.map(r=>({...r,kind:'reference'})),...data.library.map(r=>({...r,kind:'library'}))];
   el('recording').replaceChildren(...recordings.map((entry,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=entry.kind==='reference'?`${entry.title} · ${entry.duration.toFixed(1)} s`:`Bibliothèque · ${entry.title}`;return option;}));
   el('recording').disabled=el('playRecording').disabled=!recordings.length;
   el('recordingsStatus').textContent=recordings.length?`${data.references.length} extraits de référence et ${data.library.length} répliques de bibliothèque disponibles.`:'Aucun enregistrement installé sur ce serveur. Le script de mise à jour transfère les références depuis ton dossier banc_essai.';
   methods();
  }catch(_){el('recordingsStatus').textContent='Bibliothèque indisponible. Vérifie la connexion puis actualise.';}
  finally{el('refreshRecordings').disabled=false;}
 }
 el('recording').onchange=methods;el('refreshRecordings').onclick=loadRecordings;
 el('playRecording').onclick=async()=>{
  const entry=recordings[Number(el('recording').value)];if(!entry)return;
  await stop();const token=run;el('playRecording').disabled=true;el('error').textContent='';
  try{
   const path=entry.kind==='reference'?`/api/bench/references/${encodeURIComponent(entry.id)}/prepare`:`/api/bench/library/${encodeURIComponent(entry.id)}/prepare`;
   const res=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:el('recordingMethod').value})});
   const data=await res.json();if(!res.ok)throw Error(data.detail||'Lecture indisponible');if(token!==run)return;
   el('response').textContent=entry.title;await beginBundle(data,token);
  }catch(error){el('error').textContent=error.message;}
  finally{el('playRecording').disabled=false;}
 };
 async function hardware(){
  el('refreshHardware').disabled=true;
  try{
   const res=await fetch('/api/hardware/status',{cache:'no-store'});if(!res.ok)throw Error();const state=await res.json();
   el('hardwareStatus').textContent=`Micro : ${state.microphone} · Sortie : ${state.speaker} · Caméra : ${state.camera}`;
   const ready=state.vosk_model_ready&&state.arecord_installed;
   el('recognitionStatus').textContent=ready?'✓ Reconnaissance locale prête. Renseigne la clé de contrôle avant le test.':!state.vosk_model_ready?'Modèle Vosk français absent : ouvre l’aide d’installation ci-dessous.':'Outil de capture arecord absent sur ce serveur.';
  }catch(_){el('recognitionStatus').textContent='Diagnostic indisponible. Vérifie la connexion.';}
  finally{el('refreshHardware').disabled=false;}
 }
 el('refreshHardware').onclick=hardware;
 if(!display){loadRecordings();hardware();}
})();
