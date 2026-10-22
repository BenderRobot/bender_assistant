const $=id=>document.getElementById(id);
const display=new URLSearchParams(location.search).get('display');
if(display){document.body.classList.add('display',display==='eyes'?'eyes-only':'mouth-only');document.addEventListener('dblclick',()=>document.documentElement.requestFullscreen());}
let socket,lastFace=0,face={pose:0,eyes:'normal',active:false},bundle=null,segments=[],index=0,timeline=null,run=0,hostPlaying=false,photo=null,photoBlob=null;
const player=$('player');
$('controlKey').value=sessionStorage.getItem('benderControlKey')||'';
$('controlKey').onchange=()=>sessionStorage.setItem('benderControlKey',$('controlKey').value);
function authHeaders(){return {'X-Bender-Control-Token':$('controlKey').value.trim()};}
async function ioFetch(path,payload,method='POST'){
 const res=await fetch(path,{method,headers:{...authHeaders(),...(method==='POST'?{'Content-Type':'application/json'}:{})},...(method==='POST'?{body:JSON.stringify(payload||{})}:{})});
 if(!res.ok){const data=await res.json().catch(()=>({}));throw Error(data.detail||'Périphérique indisponible');}return res;
}
function hostState(state){
 hostPlaying=state.active;
 if(state.active){$('state').textContent=`Parole sur le Dell · ${state.elapsed||0} s`;$('poseState').textContent=`Lecture sur le Dell · pose ${face.pose+1}`;}
 else{$('state').textContent=state.status==='error'?'Erreur audio Dell':state.status==='stopped'?'Arrêté':'Terminé';$('poseState').textContent='Repos';if(state.error)$('error').textContent=state.error;}
}
function connect(){socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/face');socket.onmessage=e=>{face=JSON.parse(e.data);lastFace=performance.now();if(face.playback)hostState(face.playback);};socket.onclose=()=>setTimeout(connect,1500);}
connect();
function sendFace(state){face=state;lastFace=performance.now();if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify(state));}
async function stop(){
 run++;segments=[];player.pause();player.currentTime=0;timeline=null;
 if(hostPlaying||($('output').value==='dell'&&$('controlKey').value.trim())){try{await ioFetch('/api/hardware/stop');}catch(error){if(hostPlaying)$('error').textContent=error.message;}}
 hostPlaying=false;sendFace({pose:0,eyes:$('emotion').value,active:false});$('state').textContent='Arrêté';$('poseState').textContent='Repos';
}
function cueAt(time){let current={t:0,pose:0,family:'REST'};for(const cue of timeline?.cues||[]){if(cue.t>time)break;current=cue;}return current;}
async function playSegment(token){
 if(token!==run)return;
 if(index>=segments.length){timeline=null;sendFace({pose:0,eyes:$('emotion').value,active:false});$('state').textContent='Terminé';$('poseState').textContent='Repos';return;}
 const segment=segments[index];const res=await fetch(segment.timeline_url);if(!res.ok)throw Error('Timeline indisponible');
 const data=await res.json();if(token!==run)return;timeline=data;player.src=segment.audio_url;player.playbackRate=Number($('speed').value);
 $('details').textContent=[`Source : ${segment.source}${segment.cached?' · déjà enregistré':''}`, ...new Set([...(bundle.warnings||[]),...(segment.warnings||[])])].join('\n');
 await player.play();$('state').textContent='Parole dans ce navigateur';
}
async function beginBundle(data,token){
 if(token!==run)return;bundle=data;segments=bundle.segments;index=0;$('replay').disabled=false;
 $('details').textContent=segments.map(s=>`Source : ${s.source}${s.cached?' · déjà enregistré':''}`).concat(...segments.map(s=>s.warnings||[])).join('\n');
 if($('output').value==='dell'){
  timeline=null;player.pause();const res=await ioFetch('/api/hardware/play',{ids:segments.map(s=>s.id),eyes:$('emotion').value});
  const state=await res.json();if(token!==run){await ioFetch('/api/hardware/stop');return;}hostState(state);
  hostState(await (await ioFetch('/api/hardware/playback',null,'GET')).json());
 }else await playSegment(token);
}
player.addEventListener('ended',()=>{index++;playSegment(run).catch(error=>{$('error').textContent=error.message;});});
setInterval(()=>{
 if(display||hostPlaying)return;
 if(timeline){const cue=cueAt(player.currentTime),eyes=segments[index]?.eyes;
 sendFace({pose:player.ended?0:cue.pose,eyes:eyes&&eyes!=='normal'?eyes:$('emotion').value,active:!player.paused,rounded:!!cue.rounded});
 $('poseState').textContent=(cue.phone?`Son estimé : ${cue.phone}`:cue.family==='ACOUSTIC_FALLBACK'?'Estimation acoustique':cue.family||'Repère manuel')+` · pose ${cue.pose+1}`;
 }
},50);
function render(now){if(display&&now-lastFace>1200)face={...face,pose:0,active:false};BenderFace.render(face,now);requestAnimationFrame(render);}requestAnimationFrame(render);
async function perform(chat){
 await stop();$('error').textContent='';$('say').disabled=$('chat').disabled=true;$('state').textContent='Préparation…';
 const text=$('text').value,payload={mode:$('mode').value,mood:$('mood').value,allow_quote:$('quotes').checked},token=run;
 try{
  Object.assign(payload,chat?{message:text}:{text,context:$('context').value,topic:$('topic').value});
  const res=await fetch(chat?'/api/chat':'/api/speech',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await res.json();if(!res.ok||data.error)throw Error(data.detail||data.error||'Génération impossible');if(token!==run)return;
  $('response').textContent=chat?data.response:text;if(chat&&!data.speech)throw Error(data.speech_error||'Audio indisponible');await beginBundle(chat?data.speech:data,token);
 }catch(error){$('error').textContent=error.message;$('state').textContent='Indisponible';}finally{$('say').disabled=$('chat').disabled=false;}
}
$('say').onclick=()=>perform(false);$('chat').onclick=()=>perform(true);$('stop').onclick=stop;
$('emotion').onchange=()=>{if(!timeline&&!hostPlaying)sendFace({pose:0,eyes:$('emotion').value,active:false});};
$('speed').onchange=()=>{player.playbackRate=Number($('speed').value);};
$('output').onchange=()=>{player.hidden=$('output').value==='dell';};$('output').onchange();
$('replay').onclick=async()=>{if(!bundle)return;await stop();try{await beginBundle(bundle,run);}catch(e){$('error').textContent=e.message;}};
$('listen').onclick=async()=>{
 await stop();const token=run;$('listen').disabled=true;$('error').textContent='';const seconds=Number($('recordSeconds').value);$('state').textContent=`Écoute sur le Dell (${seconds} s), puis transcription…`;
 try{const data=await (await ioFetch('/api/hardware/listen',{seconds})).json();if(token!==run)return;
  $('text').value=data.text;$('heard').textContent=data.text?`Entendu : ${data.text}`:data.warning;
  $('state').textContent='Transcription locale terminée';if(data.text&&$('askAfterListen').checked)await perform(true);
 }catch(error){$('error').textContent=error.message;$('state').textContent='Micro indisponible';}finally{$('listen').disabled=false;}
};
$('capture').onclick=async()=>{
 $('capture').disabled=true;$('error').textContent='';$('state').textContent='Capture sur la LifeCam…';
 try{photo=await (await ioFetch('/api/hardware/camera')).json();const res=await ioFetch(photo.image_url,null,'GET');
  if(photoBlob)URL.revokeObjectURL(photoBlob);photoBlob=URL.createObjectURL(await res.blob());$('cameraPreview').src=photoBlob;$('cameraPreview').hidden=false;$('vision').disabled=false;$('state').textContent='Photo reçue du Dell';
 }catch(error){$('error').textContent=error.message;$('state').textContent='Caméra indisponible';}finally{$('capture').disabled=false;}
};
$('vision').onclick=async()=>{
 if(!photo)return;await stop();const token=run;$('vision').disabled=true;$('error').textContent='';$('state').textContent='Analyse de la photo avec Gemini…';
 try{const data=await (await ioFetch('/api/hardware/vision',{photo_id:photo.id,question:$('visionQuestion').value,mode:$('mode').value,mood:$('mood').value})).json();
  if(token!==run)return;$('response').textContent=data.response;if(data.speech)await beginBundle(data.speech,token);else throw Error(data.speech_error||'Audio indisponible');
 }catch(error){$('error').textContent=error.message;$('state').textContent='Vision indisponible';}finally{$('vision').disabled=false;}
};
if(!display)fetch('/api/hardware/status').then(r=>r.json()).then(s=>{$('hardwareStatus').textContent=`Micro : ${s.microphone} · Sortie : ${s.speaker} · Caméra : ${s.camera} · Modèle français : ${s.vosk_model_ready?'prêt':'à télécharger'}`;}).catch(()=>{$('hardwareStatus').textContent='État des périphériques indisponible';});
