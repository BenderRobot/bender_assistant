const eyes=document.getElementById('eyes').getContext('2d'),mouth=document.getElementById('mouth').getContext('2d');let mode='idle',emotion='normal';
function ellipse(c,x,y,rx,ry,color){c.fillStyle=color;c.beginPath();c.ellipse(x,y,rx,ry,0,0,Math.PI*2);c.fill()}
function drawEyes(t,blink){const c=eyes;c.fillStyle='#030709';c.fillRect(0,0,800,480);c.fillStyle='#31414a';c.beginPath();c.roundRect(25,74,750,330,150);c.fill();c.fillStyle='#050a0c';c.beginPath();c.roundRect(39,88,722,302,140);c.fill();
let gaze=mode==='thinking'?Math.sin(t*.0014)*25:mode==='listening'?0:Math.sin(t*.00039)*18;
for(const x of [244,556]){c.save();c.beginPath();c.ellipse(x,240,137,130,0,0,Math.PI*2);c.clip();c.fillStyle='#f8f2c6';c.fillRect(x-140,100,280,280);
const emotional=['sad','worried','crying'].includes(emotion);
const pupilY=emotional?258:mode==='thinking'?219:240,pupilSize=emotion==='surprised'?46:34;
c.fillStyle='#080e13';if(!emotion.startsWith('ref'))c.fillRect(x+gaze-pupilSize/2,pupilY-pupilSize/2,pupilSize,pupilSize);
if(emotional){
 const inner=x<400?x+140:x-140,outer=x<400?x-140:x+140;
 const squeeze=emotion==='crying'?(Math.sin(t*.005)*.5+.5)*53:emotion==='worried'?25:0;
 c.fillStyle='#080e13';c.beginPath();c.moveTo(outer,100);c.lineTo(inner,100);c.lineTo(inner,149+squeeze);
 c.quadraticCurveTo(x,206+squeeze,outer,224+squeeze);c.closePath();c.fill();
 c.beginPath();c.moveTo(x-140,380);c.lineTo(x+140,380);c.lineTo(x+140,315-squeeze*.5);
 c.quadraticCurveTo(x,294-squeeze*.5,x-140,315-squeeze*.5);c.closePath();c.fill();
}
if(emotion.startsWith('ref')){
 const ref=Number(emotion.slice(3));
 // Reference pairs 1/2: low eyelids; 3: half-open; 4: almost shut; 5: uneasy.
 const top={1:274,2:274,3:226,4:277,5:190}[ref];
 const bottom={1:322,2:322,3:330,4:289,5:323}[ref];
 c.fillStyle='#080e13';
 c.beginPath();c.moveTo(x-145,95);c.lineTo(x+145,95);
 c.lineTo(x+145,top+(ref===5?(x<400?-18:10):0));
 c.quadraticCurveTo(x,top+(ref===5?-10:6),x-145,top+(ref===5?(x<400?12:-8):0));c.closePath();c.fill();
 c.fillRect(x-145,bottom,290,100);
 // Repaint the visible pupil fragment at the upper edge of the yellow area.
 c.fillRect(x+(ref===5?-13:0)-15,top-9,30,ref===4?16:30);
}
if(emotion==='angry'){c.fillStyle='#080e13';c.beginPath();if(x<400){c.moveTo(x-140,100);c.lineTo(x+140,225);c.lineTo(x+140,100)}else{c.moveTo(x-140,225);c.lineTo(x+140,100);c.lineTo(x-140,100)}c.closePath();c.fill()}
let cover=emotion==='sleepy'?80:0;if(blink>0)cover=Math.max(cover,blink*135);if(cover){c.fillStyle='#080e13';c.fillRect(x-140,100,280,cover);c.fillRect(x-140,380-cover,280,cover)}
if(emotion==='happy'){ellipse(c,x,365,145,55,'#080e13')}
c.restore()}
if(mode==='alert'){c.strokeStyle='#f2b955';c.lineWidth=6;c.strokeRect(16,65,768,348)}
}
const lipPoses=[
 [[24,24,24,24,24],[40,40,40,40,40]],
 [[31,28,27,28,31],[33,36,37,36,33]],
 [[31,24,20,24,31],[33,40,44,40,33]],
 [[31,31,31,31,31],[33,33,33,33,33]],
 [[27,27,27,27,27],[37,37,37,37,37]],
 [[29,29,29,29,29],[35,35,35,35,35]],
 [[34,30,28,30,34],[36,36,36,36,36]],
 [[30,32,27,32,30],[34,32,37,32,34]],
 [[30,30,26,30,30],[34,34,38,34,34]],
 [[28,25,23,25,28],[76,76,76,76,76]],
 [[29,26,25,26,29],[35,38,39,38,35]],
 [[30,28,15,28,30],[34,36,49,36,34]]
];
function lipCurve(values,u){const pos=u*4,i=Math.min(3,Math.floor(pos)),t=pos-i;
 const p0=values[Math.max(0,i-1)],p1=values[i],p2=values[i+1],p3=values[Math.min(4,i+2)];
 return .5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t);
}
function sampleLip(pose,row,u){
 if(pose===2||pose===11){
  const left=1/6,right=5/6;
  const bump=u>left&&u<right?Math.pow(Math.sin((u-left)/(right-left)*Math.PI),2):0;
  const edgeDistance=Math.min(u,1-u);
  const edgeOpening=pose===11&&edgeDistance<left?1.5*Math.pow(Math.cos(edgeDistance/left*Math.PI/2),2):0;
  const halfGap=2+(pose===11?15:8)*bump+edgeOpening;
  return 32+(row?halfGap:-halfGap);
 }
 if(pose===9)return row?76:24;
 if(pose===8){const bump=u>.25&&u<.75?Math.pow(Math.sin((u-.25)*2*Math.PI),1.4):0;return (row?34:30)+(row?9:-9)*bump;}
 return lipCurve(lipPoses[pose][row],u);
}

function renderMouth(pose,rounded){
 const c=mouth;c.imageSmoothingEnabled=false;c.fillStyle='#030709';c.fillRect(0,0,128,64);
 c.save();c.beginPath();c.roundRect(4,9,120,46,10);c.clip();c.fillStyle='#eeeac0';c.fillRect(4,9,120,46);
 c.fillStyle='#222b24';for(let i=1;i<=5;i++)c.fillRect(4+i*20,9,1,46);
 if(pose===9){c.fillStyle='#030709';c.fillRect(4,40,120,24);c.fillStyle='#222b24';c.fillRect(4,23,120,1);c.fillRect(4,39,120,1);}
 else for(let row=0;row<2;row++)for(let x=4;x<124;x++){
 const y=sampleLip(pose,row,(x-4)/120)-(rounded?1.8*Math.sin(Math.PI*((x-4)%20)/20):0);
 c.fillRect(x,Math.round(Math.max(11,Math.min(53,y))),1,1);}
 c.restore();
}
window.BenderFace={render(state,t){emotion=state.eyes||'normal';mode=state.active?'speaking':'idle';drawEyes(t,0);renderMouth(Number.isInteger(state.pose)&&state.pose>=0&&state.pose<12?state.pose:0,state.rounded);}};
