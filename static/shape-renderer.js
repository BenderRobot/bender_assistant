'use strict';
window.BenderShapes = (() => {
 function ellipse(ctx, x, y, rx, ry) {ctx.beginPath();ctx.ellipse(x,y,rx,ry,0,0,Math.PI*2);}
 function mouth(ctx, shape) {
  ctx.save();ctx.imageSmoothingEnabled=false;ctx.fillStyle='#030709';ctx.fillRect(0,0,128,64);
  ctx.beginPath();ctx.roundRect(4,9,120,46,10);ctx.clip();ctx.fillStyle='#eeeac0';ctx.fillRect(4,9,120,46);
  ctx.fillStyle='#222b24';for(let i=1;i<=shape.teeth;i++)ctx.fillRect(Math.round(4+i*120/(shape.teeth+1)),9,1,46);
  for(const line of [shape.top,shape.bottom])for(let x=0;x<120;x++){
   const rounded=shape.rounded?1.8*Math.sin(Math.PI*(x%20)/20):0;
   ctx.fillRect(x+4,Math.round(line[x]-rounded),1,shape.thickness);
  }
  ctx.fillStyle='#030709';ctx.fillRect(4,shape.cutoff,120,80);ctx.restore();
 }
 function curve(ctx, eye, values, top) {
  const left=eye.cx-eye.rx,right=eye.cx+eye.rx;
  const y=values.map(value=>eye.cy-eye.ry+value*2*eye.ry);
  const control=2*y[1]-(y[0]+y[2])/2;
  ctx.beginPath();ctx.moveTo(left,top?-200:700);ctx.lineTo(right,top?-200:700);
  ctx.lineTo(right,y[2]);ctx.quadraticCurveTo(eye.cx,control,left,y[0]);ctx.closePath();ctx.fill();
 }
 function eyes(ctx, shape, blink=0) {
  ctx.save();ctx.fillStyle='#030709';ctx.fillRect(0,0,800,480);
  ctx.fillStyle='#31414a';ctx.beginPath();ctx.roundRect(25,74,750,330,150);ctx.fill();
  ctx.fillStyle='#050a0c';ctx.beginPath();ctx.roundRect(39,88,722,302,140);ctx.fill();
  for(const eye of shape.eyes){
   ctx.save();ellipse(ctx,eye.cx,eye.cy,eye.rx,eye.ry);ctx.clip();ctx.fillStyle=shape.color;ctx.fillRect(0,0,800,480);
   ctx.fillStyle='#080e13';ctx.fillRect(eye.cx+eye.pupil_x-eye.pupil_size/2,eye.cy+eye.pupil_y-eye.pupil_size/2,eye.pupil_size,eye.pupil_size);
   curve(ctx,eye,eye.top,true);curve(ctx,eye,eye.bottom,false);
   if(blink){ctx.fillRect(eye.cx-eye.rx,eye.cy-eye.ry,2*eye.rx,eye.ry*blink);ctx.fillRect(eye.cx-eye.rx,eye.cy+eye.ry-eye.ry*blink,2*eye.rx,eye.ry*blink);}
   ctx.restore();
  }ctx.restore();
 }
 const fraction=y=>Math.max(0,Math.min(1,(y-110)/260));
 function eyesPreset(expression) {
  const shape={kind:'eyes',color:'#f8f2c6',eyes:[244,556].map(cx=>({cx,cy:240,rx:137,ry:130,pupil_x:0,pupil_y:0,pupil_size:34,top:[0,0,0],bottom:[1,1,1]}))};
  shape.eyes.forEach((eye,index)=>{
   const left=index===0;
   if(expression==='surprised')eye.pupil_size=46;
   if(expression==='sleepy'){eye.top=[180,180,180].map(fraction);eye.bottom=[300,300,300].map(fraction);}
   if(expression==='happy')eye.bottom=[1,fraction(310),1];
   if(expression==='angry')eye.top=(left?[100,162.5,225]:[225,162.5,100]).map(fraction);
   if(['sad','worried','crying'].includes(expression)){
    const extra=expression==='worried'?25:expression==='crying'?26:0;
    eye.top=(left?[224+extra,196.25+extra,149+extra]:[149+extra,196.25+extra,224+extra]).map(fraction);
    eye.bottom=[315-extra*.5,304.5-extra*.5,315-extra*.5].map(fraction);eye.pupil_y=18;
   }
   if(expression.startsWith('ref')){
    const ref=Number(expression.slice(3)),top={1:274,2:274,3:226,4:277,5:190}[ref],bottom={1:322,2:322,3:330,4:289,5:323}[ref];
    eye.top=(ref===5?(left?[top+12,top-6.5,top-18]:[top-8,top-4.5,top+10]):[top,top+3,top]).map(fraction);
    eye.bottom=[bottom,bottom,bottom].map(fraction);eye.pupil_size=30;eye.pupil_x=ref===5?-13:0;eye.pupil_y=top+6-240;
   }
  });return shape;
 }
 return {mouth,eyes,eyesPreset};
})();
