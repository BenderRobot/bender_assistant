// Real browser controllers, deterministic audio/network doubles; no paid speech.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=async()=>{for(let n=0;n<20;n++)await Promise.resolve();};
function setup(){
 const elements={},tasks=new Map(),events=[];let serial=0;
 const el=id=>elements[id]??={value:'',checked:false,disabled:false,textContent:'',pause(){},addEventListener(){}};
 el('output').value='browser';el('mode').value='auto';el('emotion').value='normal';
 el('text').value='Pourquoi le ciel est bleu ?';
 const journal={begin:()=>({answered:false}),pending(){},reply(turn){turn.answered=true;},audio(){},error(){},status(){}};
 class Socket{static OPEN=1;readyState=1;send(){}}
 const context={console,AbortController,AbortSignal,URLSearchParams,URL,
  location:{search:'',protocol:'http:',host:'test'},performance:{now:()=>0},
  sessionStorage:{getItem:()=>''},WebSocket:Socket,requestAnimationFrame(){},setInterval(){},
  setTimeout(fn,delay){const id=++serial;tasks.set(id,{fn,delay});return id;},clearTimeout:id=>tasks.delete(id),
  document:{getElementById:id=>id==='waitingEnabled'?null:el(id)},
  window:{BenderConversation:journal},fetch:async()=>{throw Error('Unexpected fetch');}};
 vm.createContext(context);
 for(const file of ['waiting-cue.js','app.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../static',file),'utf8'),context);
 const tick=async delay=>{const entry=[...tasks].find(([,task])=>task.delay===delay);assert.ok(entry,`Timer ${delay} missing`);tasks.delete(entry[0]);await entry[1].fn();await flush();};
 return {context,el,events,tasks,tick,run:code=>vm.runInContext(code,context),Cue:context.window.BenderWaitingCue};
}
async function classTests(){
 const s=setup(),pending=deferred();let plays=0,cancels=0;
 const quick=new s.Cue({lookup:()=>{throw Error('Too early');},play:()=>plays++});
 await quick.finish();assert.equal(s.tasks.size,0);assert.equal(plays,0);
 const late=new s.Cue({lookup:()=>pending.promise,play:()=>plays++});
 const trigger=late.trigger();await late.finish();pending.resolve({id:'late'});await trigger;
 assert.equal(plays,0,'Late cache lookup must not start audio after the answer');
 const starting=deferred(),done=deferred();
 const cancelled=new s.Cue({lookup:async()=>({}),play:()=>starting.promise});
 const start=cancelled.trigger();await flush();const stop=cancelled.cancel();
 starting.resolve({done:done.promise,cancel:()=>{cancels++;done.resolve();}});
 await Promise.all([start,stop,cancelled.cancel()]);assert.equal(cancels,1);
 const unavailable=new s.Cue({lookup:async()=>null,play:()=>plays++});
 await unavailable.trigger();await unavailable.finish();assert.equal(plays,0);
 const broken=new s.Cue({lookup:async()=>({}),play:async()=>{throw Error('Audio unavailable');}});
 await broken.trigger();await broken.finish();
}
async function playbackTests(){
 const s=setup(),cue={id:'c'.repeat(64),duration:2,timeline_url:'/timeline',audio_url:'/audio'};
 s.context.cue=cue;s.el('output').value='dell';
 const requests=[],job='b'.repeat(32);
 s.context.fetch=async(url,options)=>{
  requests.push(url);
  return {ok:true,json:async()=>({active:true,job})};
 };
 const host=await s.run('playWaitingCue(cue,run)');
 await host.cancel();await host.done;
 assert.deepEqual(requests,['/api/hardware/play',`/api/hardware/stop?job=${job}`]);
 let busy=true,finished=false;
 s.context.fetch=async url=>({ok:true,json:async()=>url.endsWith('/playback')?{active:false,busy,job}:{active:true,job}});
 const cleaning=await s.run('playWaitingCue(cue,run)');cleaning.done.then(()=>finished=true);
 await s.tick(60);assert.equal(finished,false,'Wait for the previous Dell playback task to release ownership');
 busy=false;await s.tick(100);await cleaning.done;assert.equal(finished,true);

 // Browser cue uses a separate Audio instance, preserving the last real reply.
 s.el('output').value='browser';let audio;
 s.context.Audio=class{constructor(){audio=this;this.paused=true;}async play(){this.paused=false;}pause(){this.paused=true;}};
 s.context.fetch=async()=>({ok:true,json:async()=>({cues:[{t:0,pose:2}]})});
 const browser=await s.run('playWaitingCue(cue,run)');
 assert.equal(audio.paused,false);assert.equal(s.run('waitingFace.audio===player'),false);
 audio.onended();await browser.done;assert.equal(s.run('waitingFace'),null);
}
async function conversationTests(){
 const s=setup(),answer=deferred(),cueDone=deferred();let plays=0,cancels=0,answers=0,lookups=0;
 s.context.window.BenderWaitingAudio={enabled:true,ready:2,lookup:async()=>{lookups++;return {text:'Un instant'};}};
 s.context.fetch=async url=>{assert.equal(url,'/api/chat');s.events.push('request');return answer.promise;};
 s.context.testPlay=async()=>{plays++;s.events.push('cue');return {done:cueDone.promise,cancel:()=>{cancels++;cueDone.resolve();}};};
 s.context.testAnswer=async()=>{answers++;s.events.push('answer');};
 s.run('playWaitingCue=testPlay;beginBundle=testAnswer;');
 const performing=s.run('perform(true)');await flush();assert.deepEqual(s.events,['request']);
 await s.tick(900);assert.equal(plays,1);assert.equal(lookups,1);
 answer.resolve({ok:true,json:async()=>({response:'Réponse',speech:{segments:[]}})});
 await flush();assert.equal(answers,0,'Ready answer must wait for the current cue to finish');
 cueDone.resolve();await performing;assert.equal(answers,1);assert.equal(cancels,0);
 assert.deepEqual(s.events,['request','cue','answer']);
 assert.equal(s.el('conversationSend').disabled,false);

 // A quick answer removes the delay timer, without a cache query or extra audio.
 s.context.fetch=async()=>({ok:true,json:async()=>({response:'Vite',speech:{segments:[]}})});
 await s.run('perform(true)');assert.equal(lookups,1);assert.equal(plays,1);assert.equal(answers,2);

 // Stop invalidates an in-flight answer even if a network adapter ignores abort.
 const old=deferred();s.context.fetch=()=>old.promise;
 const stale=s.run('perform(true)');await flush();await s.tick(900);
 await s.run('stop()');assert.equal(cancels,1);
 old.resolve({ok:true,json:async()=>({response:'Ancienne réponse',speech:{segments:[]}})});
 await stale;assert.equal(answers,2);assert.equal(s.el('conversationSend').disabled,false);

 // Starting a microphone recording also cancels preparation; no new cue follows.
 s.context.window.BenderMicrophone={busy:true};await s.run('perform(true)');
 assert.equal(answers,2);assert.equal(lookups,2);
}
(async()=>{await classTests();await playbackTests();await conversationTests();console.log('Waiting audio: parallel preparation, fast answers, cancellation, microphone and handoff OK');})()
 .catch(error=>{console.error(error);process.exitCode=1;});
