'use strict';
(() => {
 let session=null, busy=false, polling=null, discard=false, turn=null, saved=[];
 const journal=window.BenderConversation;
 const controller=window.BenderMicrophone={get busy(){return busy;}};
 function lock(active){
  busy=active;
  if(active){saved=['say','chat','replay','playRecording','capture','vision'].map(id=>[$(id),$(id).disabled]);saved.forEach(([button])=>button.disabled=true);}
  else{saved.forEach(([button,disabled])=>button.disabled=disabled);saved=[];}
  $('listen').disabled=active;$('recordSeconds').disabled=active;
  $('pauseMicrophone').disabled=$('cancelMicrophone').disabled=!active;
  $('sendTranscript').disabled=active||!$('heardText').value.trim();
 }
 function describe(state){
  const recording=state.status==='recording';
  $('microphoneState').dataset.recording=String(recording);
  const message=recording?`Micro actif · ${Math.floor(state.elapsed||0)} / ${state.max_seconds} s · parle puis clique sur Pause.`:
   state.status==='stopping'?'Arrêt du micro…':state.status==='transcribing'?'Micro en pause · transcription Vosk en cours…':'Micro en pause.';
  $('microphoneState').textContent=message;journal.status(message);
 }
 async function send(){
  const text=$('heardText').value.trim();if(!text||busy)return;
  $('text').value=text;
  if(!turn||turn.answered)turn=journal.begin(text,'micro Vosk');
  $('sendTranscript').disabled=true;
  try{await perform(true,turn);}finally{$('sendTranscript').disabled=busy||!$('heardText').value.trim();}
 }
 async function finish(state){
  clearTimeout(polling);session=null;lock(false);describe(state);
  if(discard||state.status==='cancelled'){$('heard').textContent='Écoute annulée · aucun texte envoyé au cerveau.';return;}
  if(state.status==='error'){$('heard').textContent=state.error||'Transcription impossible.';$('error').textContent=$('heard').textContent;return;}
  $('heardText').value=state.text||'';$('text').value=state.text||'';
  $('heard').textContent=state.text?'Transcription terminée. Tu peux la corriger ci-dessous.':state.warning;
  $('sendTranscript').disabled=!state.text;
  if(state.text){
   turn=journal.begin(state.text,'micro Vosk');
   if($('askAfterListen').checked)await send();
   else{turn.answer.textContent='En attente de l’envoi de cette transcription.';journal.status('Transcription prête · envoi manuel.');}
  }
 }
 async function poll(){
  if(!session)return;
  const current=session;let delay=400;
  try{
   const state=await(await ioFetch(`/api/hardware/listen/status?session_id=${encodeURIComponent(current)}`,null,'GET')).json();
   if(session!==current)return;
   describe(state);
   if(['finished','cancelled','error'].includes(state.status)){await finish(state);return;}
  }catch(error){$('heard').textContent=`Suivi du micro indisponible : ${error.message}. Nouvelle tentative en cours.`;delay=2000;}
  if(session===current)polling=setTimeout(poll,delay);
 }
 $('listen').onclick=async()=>{
  if(busy)return;
  await stop();lock(true);discard=false;turn=null;$('heardText').value='';$('heard').textContent='Ouverture du micro…';$('error').textContent='';
  $('pauseMicrophone').disabled=$('cancelMicrophone').disabled=true;
  try{
   const state=await(await ioFetch('/api/hardware/listen/start',{max_seconds:Number($('recordSeconds').value)})).json();
   session=state.session_id;$('pauseMicrophone').disabled=$('cancelMicrophone').disabled=false;
   $('heard').textContent='Le micro du Dell écoute. Aucun texte n’est envoyé avant la fin de la transcription.';describe(state);polling=setTimeout(poll,200);
  }catch(error){lock(false);$('microphoneState').textContent='Micro en pause.';$('heard').textContent=error.message;$('error').textContent=error.message;}
 };
 async function pause(cancel){
  if(!session)return;
  const current=session;
  discard=discard||cancel;
  $('pauseMicrophone').disabled=$('cancelMicrophone').disabled=true;
  try{
   const state=await(await ioFetch('/api/hardware/listen/stop',{session_id:current,cancel})).json();if(session!==current)return;describe(state);
   clearTimeout(polling);await poll();
  }catch(error){$('heard').textContent=error.message;}
  finally{if(session)$('pauseMicrophone').disabled=$('cancelMicrophone').disabled=false;}
 }
 $('pauseMicrophone').onclick=()=>pause(false);$('cancelMicrophone').onclick=()=>pause(true);
 $('sendTranscript').onclick=send;
 $('heardText').oninput=()=>{$('sendTranscript').disabled=busy||!$('heardText').value.trim();};
 window.addEventListener('pagehide',()=>{
  if(session)fetch('/api/hardware/listen/stop',{method:'POST',keepalive:true,headers:{...authHeaders(),'Content-Type':'application/json'},body:JSON.stringify({session_id:session,cancel:true})}).catch(()=>{});
 });
})();
