// Exercise the real UI controller with a simulated Dell, without a real microphone.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function setup({automatic=true,transcript='bonjour bender',startError=false}={}){
 const elements={};
 const $=id=>elements[id]??=( {disabled:false,value:'',checked:false,textContent:'',dataset:{}} );
 $('askAfterListen').checked=automatic;$('recordSeconds').value='60';
 $('replay').disabled=true;$('vision').disabled=true;
 const tasks=new Map(),calls=[],replies=[],turns=[];let serial=0,state='idle';
 const journal={status(){},begin(text){const turn={answer:{textContent:''},answered:false};turns.push({text,turn});return turn;}};
 const context={$,console,window:{BenderConversation:journal,addEventListener(){}},
  setTimeout(fn){const id=++serial;tasks.set(id,fn);return id;},clearTimeout(id){tasks.delete(id);},
  stop:async()=>{},authHeaders:()=>({}),fetch:async()=>{},
  perform:async(chat,turn)=>{assert.equal(context.window.BenderMicrophone.busy,false);replies.push($('text').value);turn.answered=true;},
  ioFetch:async(url,body)=>{
   calls.push({url,body});
   if(url.endsWith('/start')){if(startError)throw Error('Clé de contrôle requise');state='recording';}
   if(url.endsWith('/stop'))state=body.cancel?'cancelled':'finished';
   return {json:async()=>({session_id:'a'.repeat(32),status:state,max_seconds:60,elapsed:1,text:state==='finished'?transcript:'',warning:'Aucune parole reconnue'})};
  }
 };
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/microphone.js'),'utf8'),context);
 async function tick(){const next=tasks.entries().next().value;if(next){tasks.delete(next[0]);await next[1]();}}
 return {$,calls,replies,turns,context,tick};
}
(async()=>{
 const auto=setup();await auto.$('listen').onclick();
 assert.equal(auto.context.window.BenderMicrophone.busy,true);
 assert.equal(auto.replies.length,0);assert.equal(auto.$('say').disabled,true);
 await auto.tick();assert.equal(auto.replies.length,0);
 await auto.$('pauseMicrophone').onclick();
 assert.equal(auto.context.window.BenderMicrophone.busy,false);
 assert.equal(auto.$('heardText').value,'bonjour bender');assert.equal(auto.replies[0],'bonjour bender');
 assert.equal(auto.$('replay').disabled,true);assert.equal(auto.$('say').disabled,false);

 const manual=setup({automatic:false});await manual.$('listen').onclick();await manual.$('pauseMicrophone').onclick();
 assert.equal(manual.replies.length,0);assert.equal(manual.turns.length,1);
 manual.$('heardText').value='texte corrigé';await manual.$('sendTranscript').onclick();
 assert.equal(manual.replies[0],'texte corrigé');assert.equal(manual.turns.length,1);

 const cancelled=setup();await cancelled.$('listen').onclick();await cancelled.$('cancelMicrophone').onclick();
 assert.equal(cancelled.replies.length,0);assert.equal(cancelled.turns.length,0);
 assert.match(cancelled.$('heard').textContent,/annulée/);

 const empty=setup({transcript:''});await empty.$('listen').onclick();await empty.$('pauseMicrophone').onclick();
 assert.equal(empty.replies.length,0);assert.equal(empty.$('sendTranscript').disabled,true);

 const failed=setup({startError:true});await failed.$('listen').onclick();
 assert.equal(failed.context.window.BenderMicrophone.busy,false);
 assert.equal(failed.$('listen').disabled,false);assert.equal(failed.$('pauseMicrophone').disabled,true);
 assert.match(failed.$('error').textContent,/Clé de contrôle/);
 console.log('Micro UI: start, pause, correction, cancellation, empty audio and recovery OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
