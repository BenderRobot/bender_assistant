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
function sendFace(state){const custom=window.BenderCustomSelection||{};state={...state,custom_eyes:custom.eyes||null,custom_mouth:state.active?null:custom.mouth||null};face=state;lastFace=performance.now();if(socket.readyState===WebSocket.OPEN)socket.send(JSON.stringify(state));}
async function stop(){
 window.stopWorkshopDemos?.();
 window.BenderVoiceStatus?.failed('Préparation annulée ; aucun nouvel audio lancé.');
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
async function beginBundle(data,token,timings={}){
 if(window.BenderMicrophone?.busy)throw Error('Mets le micro en pause avant de lire un enregistrement.');
 if(token!==run)return;bundle=data;segments=bundle.segments;index=0;$('replay').disabled=false;
 window.BenderVoiceStatus?.show(data,timings);
 $('details').textContent=segments.map(s=>`Source : ${s.source}${s.cached?' · déjà enregistré':''}`).concat(...segments.map(s=>s.warnings||[])).join('\n');
 if($('output').value==='dell'){
  timeline=null;player.pause();const res=await ioFetch('/api/hardware/play',{ids:segments.map(s=>s.id),eyes:$('emotion').value,custom_eyes:window.BenderCustomSelection?.eyes||null});
  const state=await res.json();if(token!==run){await ioFetch('/api/hardware/stop');return;}hostState(state);
  hostState(await (await ioFetch('/api/hardware/playback',null,'GET')).json());
 }else await playSegment(token);
}
player.addEventListener('ended',()=>{index++;playSegment(run).catch(error=>{$('error').textContent=error.message;});});
setInterval(()=>{
 if(display||hostPlaying)return;
 if(timeline){const cue=cueAt(player.currentTime),eyes=segments[index]?.eyes;
 sendFace({pose:player.ended?0:cue.pose,eyes:eyes&&eyes!=='normal'?eyes:$('emotion').value,active:!player.paused,rounded:!!cue.rounded||$('teeth').value==='rounded',mode:$('eyeMode').value,blink:$('eyeBlink').checked});
 $('poseState').textContent=(cue.phone?`Son estimé : ${cue.phone}`:cue.family==='ACOUSTIC_FALLBACK'?'Estimation acoustique':cue.family||'Repère manuel')+` · pose ${cue.pose+1}`;
 }
},50);
function render(now){if(display&&now-lastFace>1200)face={...face,pose:0,active:false};BenderFace.render(face,now);requestAnimationFrame(render);}requestAnimationFrame(render);
async function perform(chat,conversationTurn=null){
 if(window.BenderMicrophone?.busy){$('error').textContent='Mets le micro en pause avant de faire parler Bender.';return;}
 await stop();$('error').textContent='';$('say').disabled=$('chat').disabled=$('conversationSend').disabled=true;$('state').textContent='Préparation…';
 window.BenderVoiceStatus?.pending();const requestStarted=performance.now();
 const text=$('text').value,payload={mode:$('mode').value,mood:$('mood').value,allow_quote:$('quotes').checked},token=run;
 const turn=chat?(conversationTurn||window.BenderConversation.begin(text)):null;
 if(turn)window.BenderConversation.pending(turn,text);
 try{
  Object.assign(payload,chat?{message:text}:{text,context:$('context').value,topic:$('topic').value});
  const res=await fetch(chat?'/api/chat':'/api/speech',{method:'POST',headers:{'Content-Type':'application/json',...(chat?authHeaders():{})},body:JSON.stringify(payload)});
  const data=await res.json();if(!res.ok||data.error)throw Error(data.detail||data.error||'Génération impossible');if(token!==run){if(turn)window.BenderConversation.error(turn,'Lecture annulée ; réponse non prononcée.');return;}
  if(turn)window.BenderConversation.reply(turn,data.response);
  const audio=chat?data.speech:data,timings={...(data.timings||{}),request_seconds:(performance.now()-requestStarted)/1000};
  if(turn&&audio)window.BenderConversation.audio(turn,audio,timings);
  $('response').textContent=chat?data.response:text;if(chat&&!data.speech)throw Error(data.speech_error||'Audio indisponible');await beginBundle(audio,token,timings);
 }catch(error){$('error').textContent=error.message;$('state').textContent='Indisponible';window.BenderVoiceStatus?.failed(error.message);if(turn)window.BenderConversation.error(turn,error.message);}finally{$('say').disabled=$('chat').disabled=$('conversationSend').disabled=false;}
}
 $('conversationForm').onsubmit=event=>{event.preventDefault();const text=$('conversationText').value.trim();if(!text||$('conversationSend').disabled)return;$('text').value=text;perform(true);};
$('say').onclick=()=>perform(false);$('chat').onclick=()=>perform(true);$('stop').onclick=stop;
$('emotion').onchange=()=>{if(window.BenderCustomSelection)window.BenderCustomSelection.eyes=null;if(!timeline&&!hostPlaying)sendFace({...face,eyes:$('emotion').value,mode:$('eyeMode').value,blink:$('eyeBlink').checked});};
$('speed').onchange=()=>{player.playbackRate=Number($('speed').value);};
$('output').onchange=()=>{player.hidden=$('output').value==='dell';};$('output').onchange();
$('replay').onclick=async()=>{if(!bundle)return;const replay={...bundle,segments:bundle.segments.map(s=>({...s,cached:true}))};await stop();try{await beginBundle(replay,run);}catch(e){$('error').textContent=e.message;}};
async function showCameraImage(){
 if(!photo)return;
 const current=photo.id,url=$('cameraView').value==='original'?photo.original_image_url:photo.image_url;
 const res=await ioFetch(url,null,'GET'),blob=await res.blob();if(photo?.id!==current)return;
 if(photoBlob)URL.revokeObjectURL(photoBlob);photoBlob=URL.createObjectURL(blob);$('cameraPreview').src=photoBlob;$('cameraPreview').hidden=false;
}
$('cameraView').onchange=()=>showCameraImage().catch(error=>{$('error').textContent=error.message;});
$('capture').onclick=async()=>{
 $('capture').disabled=true;$('error').textContent='';$('state').textContent='Capture sur la LifeCam · stabilisation de l’exposition…';photo=null;$('vision').disabled=true;
 $('cameraView').disabled=true;
 try{photo=await (await ioFetch('/api/hardware/camera')).json();$('cameraView').value='enhanced';await showCameraImage();
  $('cameraView').disabled=false;$('vision').disabled=false;$('state').textContent='Photo corrigée reçue du Dell';
  const enhancement=photo.enhancement||{};
  $('cameraInfo').textContent=`Photo ${photo.width} × ${photo.height} · correction automatique avant GPT. ${(enhancement.operations||[]).join(' · ')}. ${[...(photo.warnings||[]),...(enhancement.warnings||[])].join(' ')}`;
 }catch(error){$('error').textContent=error.message;$('state').textContent='Caméra indisponible';}finally{$('capture').disabled=false;}
};
$('vision').onclick=async()=>{
 if(!photo)return;await stop();const token=run;$('vision').disabled=true;$('error').textContent='';$('state').textContent='Analyse de la photo avec GPT…';
 try{const data=await (await ioFetch('/api/hardware/vision',{photo_id:photo.id,question:$('visionQuestion').value,mode:$('mode').value,mood:$('mood').value})).json();
  if(token!==run)return;$('response').textContent=data.response;if(data.speech)await beginBundle(data.speech,token);else throw Error(data.speech_error||'Audio indisponible');
 }catch(error){$('error').textContent=error.message;$('state').textContent='Vision indisponible';}finally{$('vision').disabled=false;}
};
