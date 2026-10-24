'use strict';
(() => {
 const el=id=>document.getElementById(id);
 if(!el('bulletinStatus'))return;
 let initialized=false,busy=false,voiceInitialized=false;
 async function loadVoice(){
  if(voiceInitialized)return;
  const response=await fetch('/api/voice/status',{cache:'no-store'});
  if(!response.ok)throw Error('Diagnostic de la voix indisponible.');
  const voice=await response.json();
  el('liveEnabled').checked=voice.cloud_enabled===true;el('liveVoiceId').value=voice.cloud_voice_id||'';
  el('liveModel').value=voice.cloud_model_id||'eleven_flash_v2_5';
  el('liveVoiceStatus').textContent=voice.cloud_key_configured?'Clé API présente sur le serveur.':voice.cloud_key_configured===false?'Clé API absente sur le serveur ; transmettre .env.elevenlabs avec la mise à jour.':'Diagnostic de clé non disponible sur cette version du serveur.';
  voiceInitialized=true;
 }
 const states={absent:'Aucun bulletin du jour',queued:'En attente du service de préparation',processing:'Préparation Chatterbox en cours',ready:'Bulletin prêt à être lu',error:'Préparation à reprendre'};
 async function action(button,work,status='bulletinStatus'){button.disabled=true;try{await work();}catch(error){el(status).textContent=error.message;}finally{button.disabled=false;}}
 async function refresh(){
  if(busy||!el('controlKey').value.trim())return;busy=true;
  try{
   const data=await(await ioFetch('/api/bulletins',null,'GET')).json();
   if(!initialized){
    const settings=data.settings;
    el('bulletinFeeds').value=settings.feeds.join('\n');el('bulletinTime').value=settings.time;
    el('bulletinEnabled').checked=settings.enabled;el('bulletinMood').value=settings.mood;
    initialized=true;
   }
   const item=data.today;
   el('bulletinStatus').textContent=`${item.day} · ${states[item.state]||item.state}${item.total?' · '+item.done+'/'+item.total+' passages':''}${item.error?' · '+item.error:''}`;
   el('bulletinProgress').max=item.total||1;el('bulletinProgress').value=item.done||0;
   el('playBulletin').disabled=item.state!=='ready';
   el('queueBulletin').disabled=['queued','processing','ready'].includes(item.state);
   el('bulletinSources').replaceChildren(...(item.sources||[]).map(source=>{
    const row=document.createElement('li');row.textContent=`${source.source} : ${source.title}${source.published?'':' · date de publication inconnue'}`;
    return row;
   }));
  }catch(error){el('bulletinStatus').textContent=error.message;}finally{busy=false;}
 }
 el('saveLiveVoice').onclick=()=>action(el('saveLiveVoice'),async()=>{
  const result=await(await ioFetch('/api/voice/live-settings',{enabled:el('liveEnabled').checked,voice_id:el('liveVoiceId').value.trim(),model_id:el('liveModel').value})).json();
  el('liveVoiceStatus').textContent=result.note;
  await window.BenderVoiceStatus?.refresh();
 },'liveVoiceStatus');
 el('saveBulletin').onclick=()=>action(el('saveBulletin'),async()=>{
  await ioFetch('/api/bulletins/settings',{enabled:el('bulletinEnabled').checked,time:el('bulletinTime').value,timezone:'Europe/Paris',mood:el('bulletinMood').value,feeds:el('bulletinFeeds').value.split('\n').map(s=>s.trim()).filter(Boolean),max_items:8});
  await refresh();
 });
 el('queueBulletin').onclick=()=>action(el('queueBulletin'),async()=>{await ioFetch('/api/bulletins/queue');await refresh();});
 el('refreshBulletin').onclick=refresh;
 el('playBulletin').onclick=()=>action(el('playBulletin'),async()=>{
  await stop();const token=run;
  const bundle=await(await ioFetch('/api/bulletins/play')).json();
  el('response').textContent=bundle.text;await beginBundle(bundle,token);
 });
 setInterval(()=>{if(!el('panel-voix').hidden)refresh();},5000);
 loadVoice().catch(error=>{el('liveVoiceStatus').textContent=error.message;});refresh();
})();
