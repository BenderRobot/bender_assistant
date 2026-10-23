'use strict';
(() => {
 let controls=[];
 const field=name=>document.getElementById(`camera-${name}`);
 function syncExposure(){
  const mode=controls.find(item=>['exposure_auto','auto_exposure'].includes(item.name));
  for(const item of controls.filter(item=>['exposure_absolute','exposure_time_absolute'].includes(item.name)))
   field(item.name).disabled=!!mode&&Number(field(mode.name).value)!==1;
 }
 function render(data){
  controls=data.controls;$('cameraControls').replaceChildren();
  for(const item of controls){
   const label=document.createElement('label');label.textContent=item.label;
   let input;
   if(item.options.length||item.kind==='bool'){
    input=document.createElement('select');
    const options=item.options.length?item.options:[{value:0,label:'Désactivée'},{value:1,label:'Activée'}];
    input.replaceChildren(...options.map(option=>new Option(option.label,String(option.value))));
   }else{
    input=document.createElement('input');input.type='number';input.min=item.min;input.max=item.max;input.step=item.step||1;
   }
   input.id=`camera-${item.name}`;input.value=String(item.value);input.disabled=!!item.inactive;label.htmlFor=input.id;
   if(['exposure_auto','auto_exposure'].includes(item.name))input.onchange=syncExposure;
   label.append(input);$('cameraControls').append(label);
  }
  syncExposure();
  $('cameraApply').disabled=$('cameraAuto').disabled=!controls.length;
  const exposure=controls.some(item=>['exposure_absolute','exposure_time_absolute'].includes(item.name))&&controls.some(item=>['exposure_auto','auto_exposure'].includes(item.name)&&item.options.some(option=>option.value===1));
  $('cameraDarker').disabled=$('cameraBrighter').disabled=!exposure;
  $('cameraSettingsStatus').textContent=data.warnings.join(' ')||'Réglages lus sur la LifeCam. Ils seront conservés sur le Debian après application.';
 }
 async function action(button,mode){
  button.disabled=true;$('error').textContent='';
  try{
   let data;
   if(mode==='load')data=await(await ioFetch('/api/hardware/camera/settings',null,'GET')).json();
   else{
    const values={};
    if(mode==='custom')for(const item of controls){const input=field(item.name);if(!input.disabled)values[item.name]=Number(input.value);}
    data=await(await ioFetch('/api/hardware/camera/settings',{action:mode,controls:values})).json();
   }
   render(data);
   if(mode!=='load'){
    $('cameraSettingsStatus').textContent='Réglages enregistrés · nouvelle capture en cours, exposition en stabilisation…';
    await $('capture').onclick();
    $('cameraSettingsStatus').textContent='Réglages enregistrés. Vérifie la nouvelle photo avant de l’analyser.';
   }
  }catch(error){$('cameraSettingsStatus').textContent=error.message;$('error').textContent=error.message;}
  finally{button.disabled=false;}
 }
 $('cameraLoad').onclick=()=>action($('cameraLoad'),'load');
 $('cameraAuto').onclick=()=>action($('cameraAuto'),'auto');
 $('cameraDarker').onclick=()=>action($('cameraDarker'),'darker');
 $('cameraBrighter').onclick=()=>action($('cameraBrighter'),'brighter');
 $('cameraApply').onclick=()=>action($('cameraApply'),'custom');
})();
