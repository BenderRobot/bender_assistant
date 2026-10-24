'use strict';
(() => {
 class WaitingCue {
  constructor({lookup,play,delay=900,onStart=()=>{},onError=()=>{}}){
   Object.assign(this,{lookup,play,onStart,onError});this.closed=false;this.cancelled=false;
   this.abort=new AbortController();this.playingStart=null;this.stopPromise=null;
   this.timer=setTimeout(()=>this.trigger(),delay);
  }
  async trigger(){
   try{
    const cue=await this.lookup(this.abort.signal);
    if(this.closed||!cue)return;
    this.playingStart=Promise.resolve(this.play(cue));
    const handle=await this.playingStart;
    if(this.cancelled)await this.stopHandle(handle);
    else if(handle)this.onStart(cue);
   }catch(error){if(!this.closed&&error.name!=='AbortError')this.onError(error);}
  }
  stopHandle(handle){
   if(!this.stopPromise)this.stopPromise=Promise.resolve(handle?.cancel()).catch(()=>{});
   return this.stopPromise;
  }
  close(){this.closed=true;clearTimeout(this.timer);this.abort.abort();}
  async finish(){
   this.close();if(!this.playingStart)return;
   let timeout;
   try{
    const handle=await this.playingStart;if(!handle)return;
    await Promise.race([handle.done,new Promise(resolve=>{
     timeout=setTimeout(()=>this.stopHandle(handle).finally(resolve),6500);
    })]);
   }catch(_){}finally{clearTimeout(timeout);}
  }
  async cancel(){
   this.cancelled=true;this.close();
   if(this.playingStart){try{await this.stopHandle(await this.playingStart);}catch(_){}}
  }
 }
 window.BenderWaitingCue=WaitingCue;
 let ready=null,previous='';
 const el=id=>document.getElementById(id);
 const enabled=()=>el('waitingEnabled')?.checked!==false;
 window.BenderWaitingAudio={get enabled(){return enabled();},get ready(){return ready;},
  async lookup(message,mode,signal){
   const response=await fetch('/api/chat/acknowledgement',{method:'POST',signal,
    headers:{...authHeaders(),'Content-Type':'application/json'},body:JSON.stringify({message,mode,previous})});
   if(!response.ok)return null;
   const cue=(await response.json()).segment;if(cue)previous=cue.id;return cue;
  }
 };
 if(!el('waitingEnabled'))return;
 try{el('waitingEnabled').checked=localStorage.getItem('benderWaitingCue')!=='0';}catch(_){}
 el('waitingEnabled').onchange=()=>{try{localStorage.setItem('benderWaitingCue',enabled()?'1':'0');}catch(_){}};
 function show(data){
  ready=data.ready;
  el('waitingStatus').textContent=data.ready===data.total?'Phrases prêtes : lecture du cache pendant la préparation, sans nouvel appel ElevenLabs.':
   `${data.ready}/${data.total} phrases prêtes pour cette voix. Préparation initiale : ${data.missing_characters} caractères ElevenLabs.`;
  el('prepareWaiting').disabled=data.ready===data.total;
 }
 async function refresh(){
  try{const response=await fetch('/api/voice/waiting',{cache:'no-store'});if(!response.ok)throw Error('Catalogue indisponible');show(await response.json());}
  catch(_){ready=0;el('waitingStatus').textContent='Phrases d’attente indisponibles : vérifier la mise à jour du serveur.';}
 }
 el('refreshWaiting').onclick=refresh;
 el('prepareWaiting').onclick=async()=>{
  el('prepareWaiting').disabled=true;
  el('waitingStatus').textContent='Préparation des deux phrases avec ta voix ElevenLabs. Cette action consomme des crédits pour les phrases absentes du cache.';
  try{show(await(await ioFetch('/api/voice/waiting/prepare',{})).json());}
  catch(error){el('waitingStatus').textContent=error.message;el('prepareWaiting').disabled=false;}
 };
 refresh();
})();
