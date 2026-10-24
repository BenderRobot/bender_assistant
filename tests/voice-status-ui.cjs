const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const nodes=new Map();
function node(){return {textContent:'',hidden:false,disabled:false,dataset:{},children:[],append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},querySelector(){return null;}};}
const get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
const calls=[];
const context={console,URLSearchParams,location:{host:'192.168.1.41:8000',search:''},
 document:{hidden:false,getElementById:get,createElement:node},window:{},setInterval(){},
 fetch:async(url)=>{calls.push(url);return {ok:true,json:async()=>url==='/api/system/version'?{ui_version:'atelier-gauche-20261024',revision:'abc123456789'}:{cloud_enabled:false,local_provider:'chatterbox'}};}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/voice-status.js'),'utf8'),context);
const voice=context.window.BenderVoiceStatus;
(async()=>{
 await voice.refresh();
 assert.match(get('voiceConfigured').textContent,/désactivé/);
 assert.equal(get('voiceVersionNote').hidden,false);
 // The configured local engine must never override the audio's real source.
 voice.show({segments:[{source:'elevenlabs',cached:false}]},{brain_seconds:1,voice_seconds:2});
 assert.equal(get('actualVoiceName').textContent,'ElevenLabs · API');
 assert.match(get('actualVoiceTiming').textContent,/GPT : 1 s/);
 assert.equal(voice.describe({source:'elevenlabs',cached:false}).apiCalled,true);
 const cached=voice.describe({source:'elevenlabs',cached:true});
 assert.equal(cached.label,'Cache · ElevenLabs');assert.equal(cached.apiCalled,false);
 assert.match(cached.note,/Aucune nouvelle génération/);
 assert.equal(voice.describe({source:'elevenlabs'}).apiCalled,false);
 voice.show({segments:[{source:'system',cached:false}],warnings:['ElevenLabs indisponible']});
 assert.equal(get('actualVoiceCard').dataset.source,'system');
 assert.match(get('actualVoiceName').textContent,/Voix système/);
 assert.equal(get('actualVoiceWarnings').children[0].textContent,'ElevenLabs indisponible');
 voice.show({segments:[{source:'chatterbox',cached:false},{source:'library',cached:true}]});
 assert.match(get('actualVoiceName').textContent,/Chatterbox/);
 assert.match(get('actualVoiceNote').textContent,/Puis : Réplique enregistrée/);
 assert.equal(voice.describe({source:'other'}).label,'Moteur non indiqué');
 voice.pending();assert.equal(get('actualVoiceCard').dataset.source,'pending');
 assert.equal(get('actualVoiceName').textContent,'Moteur à confirmer');
 voice.failed('Audio indisponible');assert.equal(get('actualVoiceName').textContent,'Aucun audio disponible');
 // The history retains each answer's source even as the last-audio card changes.
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/conversation.js'),'utf8'),context);
 const journal=context.window.BenderConversation,first=journal.begin('Bonjour');
 journal.reply(first,'Salut');journal.audio(first,{segments:[{source:'elevenlabs',cached:false}]});
 const second=journal.begin('Une autre question');journal.reply(second,'Réponse');journal.audio(second,{segments:[{source:'chatterbox',cached:false}]});
 assert.match(first.source.textContent,/ElevenLabs · API/);
 assert.match(second.source.textContent,/Chatterbox · local/);
 assert.ok(calls.every(url=>['/api/voice/status','/api/system/version'].includes(url)));
 assert.match(get('deploymentVersion').textContent,/atelier-gauche-20261024/);
 assert.match(get('deploymentVersion').textContent,/abc1234567/);
 console.log('Voice status UI: real source, cache, fallback, legacy status and per-turn history OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
