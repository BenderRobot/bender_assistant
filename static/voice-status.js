'use strict';
(() => {
 const el=id=>document.getElementById(id);
 const names={elevenlabs:'ElevenLabs',chatterbox:'Chatterbox',system:'Voix système · générique',library:'Réplique enregistrée',reference:'Extrait de référence'};
 function describe(segment={}){
  const source=segment.source,known=Object.hasOwn(names,source),cached=segment.cached===true;
  const recording=source==='library'||source==='reference';
  const origin=known?names[source]:'Moteur non indiqué';
  const label=cached&&!recording?`Cache · ${origin}`:source==='elevenlabs'&&segment.cached===false?'ElevenLabs · API':source==='chatterbox'?'Chatterbox · local':origin;
  let note='Le serveur ne précise pas le moteur de cet audio.';
  if(recording)note='Extrait enregistré, sans nouvelle synthèse vocale.';
  else if(cached&&known)note='Audio déjà préparé et réutilisé. Aucune nouvelle génération pour cette lecture.';
  else if(source==='elevenlabs')note=segment.cached===false?'Audio généré par un nouvel appel à l’API ElevenLabs.':'Audio issu d’ElevenLabs ; état du cache non précisé.';
  else if(source==='chatterbox')note='Audio généré localement par Chatterbox.';
  else if(source==='system')note='Audio produit par la voix générique installée sur le serveur.';
  return {source:known?source:'unknown',label,note,cached,apiCalled:source==='elevenlabs'&&segment.cached===false};
 }
 function summarize(data){
  const parts=(data?.segments||[]).map(describe);
  return {primary:parts[0]||describe(),parts,
   warnings:[...new Set([...(data?.warnings||[]),...(data?.segments||[]).flatMap(s=>s.warnings||[])].filter(s=>typeof s==='string'&&s))]};
 }
 function timing(data={}){
  const seconds=value=>Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})+' s';
  const valid=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
  const parts=[];
  if(valid(data.brain_seconds)){
   const origin=data.brain_source==='local'?'Réponse locale':data.brain_model?`GPT (${data.brain_model})`:'GPT';
   parts.push(`${origin} : ${seconds(data.brain_seconds)}`);
  }
  if(valid(data.voice_seconds))parts.push(`Préparation audio : ${seconds(data.voice_seconds)}`);
  if(!parts.length&&valid(data.request_seconds))parts.push(`Réponse et audio prêts en ${seconds(data.request_seconds)}`);
  return parts.join(' · ');
 }
 function show(data,timings={}){
  if(!el('actualVoiceCard'))return;
  const result=summarize(data);
  el('actualVoiceCard').dataset.source=result.primary.source;
  el('actualVoiceName').textContent=result.primary.label;
  const extra=result.parts.slice(1).map(p=>p.label);
  el('actualVoiceNote').textContent=result.primary.note+(extra.length?` Puis : ${extra.join(', ')}.`:'');
  el('actualVoiceTiming').textContent=timing(timings);
  el('actualVoiceWarnings').replaceChildren(...result.warnings.map(message=>{const item=document.createElement('li');item.textContent=message;return item;}));
  el('actualVoiceWarnings').hidden=!result.warnings.length;
 }
 function pending(){
  if(!el('actualVoiceCard'))return;
  el('actualVoiceCard').dataset.source='pending';el('actualVoiceName').textContent='Moteur à confirmer';
  el('actualVoiceNote').textContent='Réponse en préparation. La source sera confirmée par l’audio reçu.';
  el('actualVoiceTiming').textContent='';el('actualVoiceWarnings').hidden=true;
 }
 function failed(message){
  if(el('actualVoiceCard')?.dataset.source!=='pending')return;
  el('actualVoiceCard').dataset.source='unknown';el('actualVoiceName').textContent='Aucun audio disponible';el('actualVoiceNote').textContent=message;
 }
 async function refreshVersion(){
  const node=el('deploymentVersion');if(!node)return;
  try{
   const response=await fetch('/api/system/version',{cache:'no-store'});
   if(!response.ok)throw Error();
   const data=await response.json();
   node.textContent=`Version : ${data.ui_version} · ${data.revision?data.revision.slice(0,10):'copie locale sans révision déployée'}`;
  }catch(_){node.textContent='Version non confirmée : ce serveur nécessite une mise à jour.';}
 }
 async function refresh(){
  const button=el('voiceStatusRefresh');if(!button)return;
  button.disabled=true;
  try{
   const response=await fetch('/api/voice/status',{cache:'no-store'});if(!response.ok)throw Error();
   const data=await response.json();
   const local=data.local_provider==='chatterbox'?'Chatterbox':data.local_provider==='system'?'voix système':'moteur non précisé';
   if(data.cloud_enabled===true){
    const missing=[];
    if(data.cloud_key_configured===false)missing.push('clé API');
    if(data.cloud_voice_id==='')missing.push('Voice ID');
    if(data.cloud_sdk_installed===false)missing.push('SDK ElevenLabs');
    el('voiceConfigured').textContent=missing.length?'ElevenLabs · configuration incomplète':'ElevenLabs activé';
    el('voiceConfigurationNote').textContent=missing.length?`À configurer : ${missing.join(', ')}.`:`Moteur cloud configuré${data.cloud_model_id?' · '+data.cloud_model_id:''}. Le cache peut être réutilisé avant un nouvel appel.`;
   }else{
    el('voiceConfigured').textContent='ElevenLabs désactivé';
    el('voiceConfigurationNote').textContent=`Moteur local annoncé : ${local}. Ouvre « Configurer la voix » pour activer l’API.`;
   }
   const option=el('mode')?.querySelector('option[value="local"]');if(option)option.textContent=`Local · ${local}${local==='Chatterbox'?' (plus lent sur CPU)':''}`;
   el('voiceVersionNote').hidden=Boolean(data.cloud_integration);
   el('voiceVersionNote').textContent='Cette version du serveur ne fournit pas le diagnostic ElevenLabs complet. Installe la dernière mise à jour Bender.';
  }catch(_){el('voiceConfigured').textContent='Diagnostic indisponible';el('voiceConfigurationNote').textContent='Vérifie la connexion au serveur puis actualise.';}
  finally{button.disabled=false;}
 }
 window.BenderVoiceStatus={describe,summarize,timing,show,pending,failed,refresh};
 if(el('voiceStatusRefresh')){
  el('voiceStatusRefresh').onclick=refresh;
  el('voiceSettingsShortcut').onclick=()=>window.BenderWorkshop?.show('voix');
  el('voiceServerAddress').textContent=`Serveur connecté : ${location.host}`;
  if(!new URLSearchParams(location.search).has('display')){
   refreshVersion();refresh();setInterval(()=>{if(!document.hidden){refresh();refreshVersion();}},15000);
  }
 }
})();
