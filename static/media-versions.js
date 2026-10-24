'use strict';
(() => {
 const el=id=>document.getElementById(id);
 if(!el('mediaVersionsPanel'))return;
 const make=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
 const labels={quote:'Réplique enregistrée',voice_reference:'Référence Chatterbox',expression:'Repère bouche / yeux'};
 let snapshot=null,stamp=null,mood='',previewUrl=null,previewRun=0;
 function clearPreview(){
  previewRun++;el('versionAudio').pause();el('versionAudio').removeAttribute('src');
  if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;el('versionPreview').hidden=true;
 }
 async function action(button,callback){
  button.disabled=true;el('mediaError').textContent='';
  try{await callback();}catch(error){el('mediaError').textContent=error.message;}finally{button.disabled=false;}
 }
 function show(view){
  const versions=view==='versions';
  el('mediaSources').hidden=versions;el('mediaVersionsPanel').hidden=!versions;
  el('mediaShowSources').setAttribute('aria-pressed',String(!versions));
  el('mediaShowVersions').setAttribute('aria-pressed',String(versions));
  if(!versions)clearPreview();
 }
 async function preview(item){
  if(window.BenderMicrophone?.busy)throw Error('Mets le micro en pause avant d’écouter un passage.');
  const stopping=stop(),token=run;await stopping;
  if(token!==run||window.BenderMicrophone?.busy)return;
  const previewToken=previewRun;
  const response=await ioFetch(item.audio_url,null,'GET');const blob=await response.blob();
  if(token!==run||previewToken!==previewRun)return;
  previewUrl=URL.createObjectURL(blob);el('versionAudio').src=previewUrl;
  el('versionPreviewTitle').textContent=item.title;el('versionPreview').hidden=false;
  await el('versionAudio').play();
 }
 async function playWithFace(item){
  if(window.BenderMicrophone?.busy)throw Error('Mets le micro en pause avant de tester une réplique.');
  const stopping=stop(),token=run;await stopping;
  if(token!==run||window.BenderMicrophone?.busy)return;
  const bundle=await(await ioFetch(`/api/bench/library/${encodeURIComponent(item.library_id)}/prepare`,{})).json();
  if(token!==run)return;
  await beginBundle(bundle,token);
 }
 function draw(){
  if(!snapshot)return;
  const query=el('versionSearch').value.toLocaleLowerCase('fr-FR').trim(),use=el('versionUse').value;
  const filtered=snapshot.selections.filter(item=>(!mood||item.mood===mood)&&(!use||item.use===use)&&
   [item.title,item.text,item.source_name,...item.triggers].join(' ').toLocaleLowerCase('fr-FR').includes(query));
  el('versionMoods').replaceChildren(...snapshot.moods.map(version=>{
   const card=make('button');card.className='version-mood';card.dataset.mood=version.id;
   card.setAttribute('aria-pressed',String(mood===version.id));
   card.append(make('strong',version.label),make('span',`${version.quotes} réplique(s) prête(s)`),
    make('small',`${version.references} référence(s) · ${version.active_references} active(s) · ${version.expressions} repère(s)`));
   card.onclick=()=>{mood=mood===version.id?'':version.id;draw();};return card;
  }));
  el('versionAll').setAttribute('aria-pressed',String(!mood));
  el('versionStatus').textContent=`${filtered.length} passage(s) affiché(s) sur ${snapshot.total} validé(s) · ${snapshot.ready_quotes} réplique(s) prête(s) au total. ${(snapshot.warnings||[]).join(' ')}`;
  const nodes=filtered.map(item=>{
   const card=make('article');card.className='version-selection';card.dataset.mood=item.mood;
   const heading=make('div');heading.className='version-selection-heading';
   const moodLabel=snapshot.moods.find(version=>version.id===item.mood)?.label||item.mood;
   heading.append(make('h4',item.title),make('span',`${moodLabel} · ${labels[item.use]}`));card.append(heading);
   if(item.text)card.append(make('p',item.text));
   const status=make('p',item.reason);status.className='version-availability';
   status.dataset.ready=String(item.ready_for_response||item.active);card.append(status);
   card.append(make('small',`${item.source_name} · ${item.start.toFixed(2)}–${item.end.toFixed(2)} s`));
   if(item.triggers.length)card.append(make('p',`Mots déclencheurs : ${item.triggers.join(', ')}`));
   const buttons=make('div');buttons.className='buttons';
   if(item.audio_url){const listen=make('button','Écouter');listen.onclick=()=>action(listen,()=>preview(item));buttons.append(listen);}
   if(item.ready_for_response){
    const test=make('button','Tester avec la bouche');test.onclick=()=>action(test,()=>playWithFace(item));buttons.append(test);
   }
   if(item.use==='voice_reference'&&item.available){
    const activate=make('button',item.active?'Référence Chatterbox active':'Utiliser pour cette humeur');activate.disabled=item.active;
    activate.onclick=()=>action(activate,async()=>{
     await ioFetch(`/api/media/${item.sample_id}/reference`,{selection_id:item.selection_id});
     el('mediaRefresh').click();
    });buttons.append(activate);
   }
   const source=make('button','Voir le sample');source.className='secondary';
   source.onclick=()=>{show('sources');window.BenderMedia?.openSample(item.sample_id);};buttons.append(source);
   card.append(buttons);return card;
  });
  if(!nodes.length)nodes.push(make('p',snapshot.total?'Aucun passage pour ce filtre. Choisis une autre humeur ou valide un nouveau passage.':'Aucun passage validé. Dans « Préparer les samples », écoute un extrait puis valide son usage et son humeur.'));
  el('versionList').replaceChildren(...nodes);
 }
 window.BenderVersions={show,stopPreview:clearPreview,update(data){
  if(!data)return;window.BenderMoods?.updateLibrary(data);const next=JSON.stringify(data);snapshot=data;if(stamp===next)return;stamp=next;draw();
 }};
 el('mediaShowSources').onclick=()=>show('sources');
 el('mediaShowVersions').onclick=()=>{show('versions');if(!snapshot)el('mediaRefresh').click();};
 el('versionSearch').oninput=el('versionUse').onchange=draw;
 el('versionAll').onclick=()=>{mood='';draw();};
 window.addEventListener('hashchange',()=>{if(location.hash!=='#samples')clearPreview();});
})();
