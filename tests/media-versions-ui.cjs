const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.value='';this.hidden=false;this.textContent='';this.paused=true;}
 set innerHTML(value){throw Error('Untrusted sample content must use textContent');}
 append(...children){this.children.push(...children);}
 replaceChildren(...children){this.children=children;}
 setAttribute(key,value){this.attributes[key]=value;}
 removeAttribute(key){delete this[key];}
 click(){return this.onclick?.();}
 pause(){this.paused=true;}
 async play(){this.paused=false;}
}
const elements={},el=id=>elements[id]??=new Element();
const requests=[],played=[],revoked=[],sources=[];let refreshed=0;
const context={console,document:{getElementById:el,createElement:tag=>new Element(tag)},
 window:{addEventListener(){},BenderMedia:{openSample:id=>sources.push(id)}},location:{hash:'#samples'},
 URL:{createObjectURL:()=>`blob:test-${requests.length}`,revokeObjectURL:url=>revoked.push(url)},
 run:0,stop:async()=>{context.run++;context.window.BenderVersions?.stopPreview();},
 ioFetch:async(url,payload,method)=>{requests.push({url,payload,method});return {blob:async()=>new Uint8Array([0]),json:async()=>({segments:[{id:'recorded'}]})};},
 beginBundle:async bundle=>played.push(bundle)};
el('mediaRefresh').onclick=()=>refreshed++;
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/media-versions.js'),'utf8'),context);
const base={sample_id:'a'.repeat(64),selection_id:'1'.repeat(16),start:0,end:2,triggers:[],available:true,active:false,ready_for_response:false,source_name:'video.mp4',reason:'À vérifier'};
const data={total:3,ready_quotes:1,moods:['neutral','sarcastic','angry','excited','sad'].map(id=>({id,label:id,quotes:id==='sarcastic'?1:0,references:id==='neutral'?1:0,active_references:0,expressions:id==='excited'?1:0})),
 selections:[
  {...base,id:'quote',use:'quote',mood:'sarcastic',title:'<img onerror=alert(1)>',text:'Bonne question',triggers:['question'],ready_for_response:true,audio_url:'/approved/quote.wav',library_id:'quote-one'},
  {...base,id:'reference',use:'voice_reference',mood:'neutral',title:'Voix neutre',audio_url:'/approved/reference.wav'},
  {...base,id:'expression',use:'expression',mood:'excited',title:'Bouche ouverte'},
 ]};
const list=()=>el('versionList').children;
const buttons=card=>card.children.find(child=>child.className==='buttons').children;
const find=(card,text)=>buttons(card).find(button=>button.textContent===text);
(async()=>{
 context.window.BenderVersions.update(data);
 assert.equal(el('versionMoods').children.length,5);assert.equal(list().length,3);
 assert.equal(list()[0].children[0].children[0].textContent,'<img onerror=alert(1)>');
 el('versionMoods').children[1].onclick();assert.equal(list().length,1);
 el('versionSearch').value='inexistant';el('versionSearch').oninput();assert.match(list()[0].textContent,/Aucun passage/);
 el('versionSearch').value='';el('versionSearch').oninput();el('versionAll').onclick();assert.equal(list().length,3);
 el('versionUse').value='voice_reference';el('versionUse').onchange();assert.equal(list().length,1);
 await find(list()[0],'Utiliser pour cette humeur').onclick();
 assert.equal(requests.at(-1).url,`/api/media/${base.sample_id}/reference`);
 assert.equal(requests.at(-1).payload.selection_id,base.selection_id);assert.equal(refreshed,1);
 assert.equal(find(list()[0],'Tester avec la bouche'),undefined,'References do not become generated answers');
 el('versionUse').value='';el('versionUse').onchange();
 await find(list()[0],'Écouter').onclick();
 assert.equal(el('versionAudio').paused,false);assert.equal(el('versionPreview').hidden,false);
 assert.equal(requests.at(-1).url,'/approved/quote.wav');
 await context.stop();assert.equal(el('versionAudio').paused,true);assert.equal(el('versionPreview').hidden,true);assert.equal(revoked.length,1);
 await find(list()[0],'Tester avec la bouche').onclick();
 assert.equal(requests.at(-1).url,'/api/bench/library/quote-one/prepare');assert.equal(played.length,1);
 context.window.BenderMicrophone={busy:true};const previous=requests.length;
 await find(list()[0],'Écouter').onclick();assert.equal(requests.length,previous);assert.match(el('mediaError').textContent,/micro/);
 context.window.BenderMicrophone.busy=false;
 let resolve;
 context.ioFetch=()=>new Promise(yes=>resolve=yes);
 const loading=find(list()[0],'Écouter').onclick();for(let n=0;n<20;n++)await Promise.resolve();
 assert.equal(typeof resolve,'function');await context.stop();
 resolve({blob:async()=>new Uint8Array([0])});await loading;
 assert.equal(el('versionPreview').hidden,true,'A late preview cannot restart after Stop');
 find(list()[2],'Voir le sample').onclick();assert.deepEqual(sources,[base.sample_id]);assert.equal(el('mediaSources').hidden,false);
 assert.ok(!requests.some(item=>item.url==='/api/speech'||item.url==='/api/chat'));
 console.log('Media versions: filtering, safe text, reference activation, recorded audio, mouth playback and cancellation OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
