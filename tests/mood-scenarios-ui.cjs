const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
class Element{
 constructor(){this.children=[];this._value='';this.disabled=false;this.hidden=false;this.checked=true;}
 get value(){return this._value||this.children[0]?.value||'';}set value(value){this._value=value;}
 replaceChildren(...children){this.children=children;this._value=children[0]?.value||'';}
 append(...children){this.children.push(...children);}
 click(){return this.onclick?.();}
}
const elements={},el=id=>elements[id]??=new Element();
el('scenarioMood').value='sad';el('scenarioIntensity').value='2';
const scene=(id,level=2)=>({id,name:id,mood:'sad',intensity:level,text:'Mes circuits sont tristes.',eyes:'sad',custom_eyes:null,library_id:null,enabled:true});
let catalog={revision:1,items:[scene('sad-a'),scene('sad-b'),scene('sad-c',1)]};
const shape={kind:'eyes',eyes:[{cx:240},{cx:550}]},calls=[],played=[];
const ctx={console,document:{getElementById:el,createElement:()=>new Element()},window:{},activePreparation:null,preparationStarting:false,
 fetch:async()=>({ok:true,json:async()=>({items:[{id:'custom-one',name:'Yeux doux',kind:'eyes',definition:shape}]})}),
 ioFetch:async(url,body,method)=>{
  calls.push({url,body,method});
  if(url==='/api/media/versions')return {json:async()=>({selections:[{use:'quote',ready_for_response:true,library_id:'sample-one',title:'Réplique triste',text:'Le texte réellement enregistré.'}]})};
  if(body){catalog={revision:catalog.revision+1,items:catalog.items.map(item=>item.id===body.scenario.id?body.scenario:item)};}
  return {json:async()=>structuredClone(catalog)};
 },perform:async chat=>played.push({chat,text:el('text').value})};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/mood-scenarios.js'),'utf8'),ctx);
(async()=>{
 await el('loadScenarios').click();assert.equal(el('scenarioChoice').children.length,2);
 assert.equal(el('scenarioText').value,'Mes circuits sont tristes.');
 el('scenarioEyes').value='custom:custom-one';el('scenarioName').value='Triste doux';
 await el('saveScenario').click();const saved=calls.at(-1).body;
 assert.equal(saved.revision,1);assert.equal(saved.scenario.custom_eyes.kind,'eyes');assert.equal(saved.scenario.name,'Triste doux');
 el('scenarioRecording').value='sample-one';el('scenarioRecording').onchange();
 assert.equal(el('scenarioText').readOnly,true);assert.equal(el('scenarioText').value,'Le texte réellement enregistré.');
 await el('saveScenario').click();assert.equal(calls.at(-1).body.scenario.library_id,'sample-one');
 el('scenarioIntensity').value='1';el('scenarioIntensity').onchange();assert.equal(el('scenarioChoice').children.length,1);
 await el('testScenario').click();assert.deepEqual(played,[{chat:true,text:'Sois triste niveau 1'}]);
 ctx.window.BenderMoods.showResult({mood_scenario:{name:'Triste doux',mood:'sad',intensity:1,eyes:'sad'}});
 assert.equal(el('moodReaction').hidden,false);assert.match(el('moodReaction').textContent,/Triste/);
 ctx.window.BenderMoods.showResult({response:'Normal'});assert.equal(el('moodReaction').hidden,true);
 console.log('Mood editor: intensity filters, custom eyes, recorded words, protected saves and explicit test command OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
