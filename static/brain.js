'use strict';
(() => {
 const el=id=>document.getElementById(id);
 async function run(button, action) {
  button.disabled=true;el('brainError').textContent='';
  try {await action();} catch(error) {el('brainError').textContent=error.message;}
  finally {button.disabled=false;}
 }
 function show(data) {
  el('brainStatus').textContent=data.message+(data.model?` Modèle : ${data.model}.`:'');
  el('brainStatus').dataset.ready=String(data.authorized);
 }
 async function status() {
  const res=await fetch('/api/brain/status',{cache:'no-store'});
  if(!res.ok)throw Error('Statut du cerveau indisponible.');
  show(await res.json());
 }
 async function accounts() {
  const data=await (await ioFetch('/api/brain/accounts',null,'GET')).json();show(data);
  el('brainAccount').replaceChildren(...data.accounts.map(account=>{
   const option=document.createElement('option');option.value=account.id;option.textContent=account.label+(account.signed_in?'':' · déconnecté');return option;
  }));
  el('brainAccount').disabled=!data.accounts.length;
  el('brainAccount').value=data.active_account;
 }
 el('brainRefresh').onclick=()=>run(el('brainRefresh'),status);
 el('brainAccounts').onclick=()=>run(el('brainAccounts'),accounts);
 el('brainAccount').onchange=()=>run(el('brainAccount'),async()=>{
  await ioFetch('/api/brain/account',{account:el('brainAccount').value});
  el('brainModel').replaceChildren(new Option('Recharger les modèles du compte actif',''));el('brainModel').disabled=true;el('brainSaveModel').disabled=true;
  await accounts();
 });
 el('brainLoadModels').onclick=()=>run(el('brainLoadModels'),async()=>{
  const data=await(await ioFetch('/api/brain/models',null,'GET')).json();
  el('brainModel').replaceChildren(...data.models.map(item=>new Option(item.display_name,item.slug)));
  if(data.models.some(item=>item.slug===data.selected))el('brainModel').value=data.selected;
  el('brainModel').disabled=false;el('brainSaveModel').disabled=false;
 });
 el('brainSaveModel').onclick=()=>run(el('brainSaveModel'),async()=>{
  await ioFetch('/api/brain/model',{model:el('brainModel').value});await status();
 });
 el('brainLogout').onclick=()=>run(el('brainLogout'),async()=>{
  const data=await(await ioFetch('/api/brain/logout')).json();show(data);
  el('brainModel').disabled=true;el('brainSaveModel').disabled=true;
  if(!data.revoked)el('brainError').textContent='Session effacée localement. La révocation distante n’a pas pu être confirmée : vérifier les applications connectées dans ChatGPT.';
 });
 el('brainTest').onclick=()=>run(el('brainTest'),async()=>{
  el('brainAnswer').textContent='Réflexion en cours…';
  try{
   const data=await(await ioFetch('/api/chat',{message:el('brainQuestion').value,speech:false})).json();
   if(data.error)throw Error(data.error);
   el('brainAnswer').textContent=data.response;await status();
  }catch(error){el('brainAnswer').textContent='';throw error;}
 });
 if(!display)status().catch(error=>{el('brainStatus').textContent=error.message;});
})();
