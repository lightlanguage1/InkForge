import { useRef, useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../api/client";

// ── Types ─────────────────────────────────────────────────────────────────────
type ShapeEllipse = { type:"ellipse"; cx:number; cy:number; rx:number; ry:number; width:number; density:number };
type ShapeRing    = { type:"ring";   cx:number; cy:number; r:number;  width:number; density:number };
type ShapeLine    = { type:"line";   x1:number; y1:number; x2:number; y2:number; width:number; density:number };
type ShapeArc     = { type:"arc";    cx:number; cy:number; r:number;  a1:number; a2:number; width:number; density:number };
type ShapePoly    = { type:"poly";   points:[number,number][]; width:number; density:number };
type ShapeGrid    = { type:"dot_grid"; cx:number; cy:number; w:number; h:number; spacing:number; dot_r:number; density:number };
type ShapeScatter = { type:"scatter"; cx:number; cy:number; rx:number; ry:number; count:number; dot_r:number; density:number };
type ShapeRadial  = { type:"radial"; cx:number; cy:number; r:number; rays:number; width:number; density:number };
type ShapeZigzag  = { type:"zigzag"; x1:number; y1:number; x2:number; y2:number; amplitude:number; segments:number; width:number; density:number };
type ShapeSpiral  = { type:"spiral"; cx:number; cy:number; r0:number; r1:number; turns:number; width:number; density:number };
type Shape = ShapeEllipse|ShapeRing|ShapeLine|ShapeArc|ShapePoly|ShapeGrid|ShapeScatter|ShapeRadial|ShapeZigzag|ShapeSpiral;

interface PortraitData { color:string; caption:string; shapes:Shape[] }
interface Props { projectId:string; currentTick:number }

const W = 440, H = 330;
const STEP = 3.5;
const DOT_R = 1.6;
const FOV = 600, DEPTH = 600;

// ── Geometry ──────────────────────────────────────────────────────────────────
function distSeg(px:number,py:number,x1:number,y1:number,x2:number,y2:number):number {
  const dx=x2-x1,dy=y2-y1,l2=dx*dx+dy*dy;
  if(l2===0) return Math.hypot(px-x1,py-y1);
  const t=Math.max(0,Math.min(1,((px-x1)*dx+(py-y1)*dy)/l2));
  return Math.hypot(px-x1-t*dx,py-y1-t*dy);
}
function pip(px:number,py:number,v:[number,number][]):boolean {
  let inside=false;
  for(let i=0,j=v.length-1;i<v.length;j=i++){
    if(((v[i][1]>py)!==(v[j][1]>py))&&px<((v[j][0]-v[i][0])*(py-v[i][1]))/(v[j][1]-v[i][1])+v[i][0])
      inside=!inside;
  }
  return inside;
}
function inArc(px:number,py:number,s:ShapeArc):boolean {
  if(Math.abs(Math.hypot(px-s.cx,py-s.cy)-s.r)>s.width/2+1) return false;
  let a=(Math.atan2(py-s.cy,px-s.cx)*180/Math.PI+360)%360;
  const a1=(s.a1%360+360)%360,a2=(s.a2%360+360)%360;
  return a1<=a2?(a>=a1&&a<=a2):(a>=a1||a<=a2);
}

// ── Dot placement per shape ───────────────────────────────────────────────────
type Dot3 = { hx:number; hy:number; hz:number; r:number; x:number; y:number; vx:number; vy:number };

function densityToHz(s:Shape):number {
  const d=s.density;
  if(d>=2.5||s.type==="line"||s.type==="arc"||s.type==="zigzag"||s.type==="spiral"||s.type==="radial") return -15;
  if(d>=1.5) return 0;
  return 15;
}

// hit-test: is grid point (px,py) inside shape s?
function hitShape(px:number,py:number,s:Shape):boolean {
  switch(s.type){
    case"ellipse":{
      const rx=Math.min(s.rx??10,20),ry=Math.min(s.ry??10,20);
      return (px-s.cx)**2/Math.max(rx,1)**2+(py-s.cy)**2/Math.max(ry,1)**2<=1;
    }
    case"ring": return Math.abs(Math.hypot(px-s.cx,py-s.cy)-s.r)<=(s.width??4)/2+1;
    case"line": return distSeg(px,py,s.x1,s.y1,s.x2,s.y2)<=(s.width??3)/2+1;
    case"arc": return inArc(px,py,s);
    case"poly": return s.points?.length>=3&&pip(px,py,s.points);
    case"dot_grid":{
      const x0=s.cx-s.w/2,x1=s.cx+s.w/2,y0=s.cy-s.h/2,y1=s.cy+s.h/2;
      return px>=x0&&px<=x1&&py>=y0&&py<=y1;
    }
    case"scatter":{
      const rxx=Math.max(s.rx??30,1),ryy=Math.max(s.ry??30,1);
      return (px-s.cx)**2/rxx**2+(py-s.cy)**2/ryy**2<=1;
    }
    case"radial":{
      for(let i=0;i<(s.rays??8);i++){
        const a=(2*Math.PI*i)/(s.rays??8);
        const ex=s.cx+(s.r??100)*Math.cos(a),ey=s.cy+(s.r??100)*Math.sin(a);
        if(distSeg(px,py,s.cx,s.cy,ex,ey)<=(s.width??3)/2+1) return true;
      }
      return false;
    }
    case"zigzag":{
      const segs=s.segments??6,amp=s.amplitude??30;
      const dx_=(s.x2-s.x1)/segs,dy_=(s.y2-s.y1)/segs,len=Math.hypot(dx_,dy_)||1;
      for(let i=0;i<segs;i++){
        const mid=i%2===0?amp:-amp,px_=-dy_/len*mid,py_=dx_/len*mid;
        const xa=s.x1+dx_*i+px_,ya=s.y1+dy_*i+py_;
        const xb=s.x1+dx_*(i+1)-px_,yb=s.y1+dy_*(i+1)-py_;
        if(distSeg(px,py,xa,ya,xb,yb)<=(s.width??3)/2+1) return true;
      }
      return false;
    }
    case"spiral":{
      const r0=s.r0??10,r1=s.r1??90,trn=s.turns??2,steps=Math.floor((s.density??30)*2);
      for(let i=0;i<steps;i++){
        const t=i/steps*trn*2*Math.PI,r=r0+(r1-r0)*i/steps;
        if(Math.hypot(px-s.cx-r*Math.cos(t),py-s.cy-r*Math.sin(t))<=(s.width??3)/2+1.5) return true;
      }
      return false;
    }
  }
}

// ── Build + center all dots ───────────────────────────────────────────────────
function buildDots(data:PortraitData|null):Dot3[] {
  if(!data?.shapes?.length) return [];

  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  for(const s of data.shapes){
    const pts:number[][] =
      s.type==="ellipse"||s.type==="scatter"?[[s.cx-s.rx,s.cy],[s.cx+s.rx,s.cy],[s.cx,s.cy-s.ry],[s.cx,s.cy+s.ry]]:
      (s.type==="ring"||s.type==="arc")?[[s.cx-s.r,s.cy],[s.cx+s.r,s.cy],[s.cx,s.cy-s.r],[s.cx,s.cy+s.r]]:
      s.type==="line"||s.type==="zigzag"?[[s.x1,s.y1],[s.x2,s.y2]]:
      s.type==="radial"?[[s.cx-s.r,s.cy],[s.cx+s.r,s.cy],[s.cx,s.cy-s.r],[s.cx,s.cy+s.r]]:
      s.type==="spiral"?[[s.cx-s.r1,s.cy],[s.cx+s.r1,s.cy],[s.cx,s.cy-s.r1],[s.cx,s.cy+s.r1]]:
      s.type==="dot_grid"?[[s.cx-s.w/2,s.cy],[s.cx+s.w/2,s.cy],[s.cx,s.cy-s.h/2],[s.cx,s.cy+s.h/2]]:
      (s as ShapePoly).points;
    for(const [px,py] of pts){if(px<x0)x0=px;if(px>x1)x1=px;if(py<y0)y0=py;if(py>y1)y1=py;}
  }
  const ox=W/2-(x0+x1)/2, oy=H/2-(y0+y1)/2;

  const shifted:Shape[]=data.shapes.map(s=>{
    if(s.type==="ellipse"||s.type==="scatter") return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="ring"||s.type==="arc")       return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="line"||s.type==="zigzag")     return {...s,x1:s.x1+ox,y1:s.y1+oy,x2:s.x2+ox,y2:s.y2+oy};
    if(s.type==="radial"||s.type==="spiral")    return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="dot_grid")                     return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="poly")                         return {...s,points:s.points.map(([px,py]:[number,number])=>[px+ox,py+oy] as [number,number])};
    return s;
  });

  const all:Dot3[]=[];
  for(let gy=STEP/2;gy<H;gy+=STEP){
    for(let gx=STEP/2;gx<W;gx+=STEP){
      const hit=shifted.find(s=>hitShape(gx,gy,s));
      if(hit){
        const hz=densityToHz(hit);
        all.push({hx:gx-W/2,hy:gy-H/2,hz,r:DOT_R,x:gx,y:gy,vx:0,vy:0});
      }
    }
  }
  return all;
}

// ── 3D projection ─────────────────────────────────────────────────────────────
function project(hx:number,hy:number,hz:number,rx:number,ry:number){
  const cosY=Math.cos(ry),sinY=Math.sin(ry);
  const rx1=hx*cosY-hz*sinY,rz1=hx*sinY+hz*cosY;
  const cosX=Math.cos(rx),sinX=Math.sin(rx);
  const ry2=hy*cosX-rz1*sinX,rz2=hy*sinX+rz1*cosX;
  const scale=FOV/Math.max(rz2+DEPTH,1);
  return {sx:W/2+rx1*scale,sy:H/2+ry2*scale,sz:rz2,scale};
}

// ── Component ─────────────────────────────────────────────────────────────────
export function ProtagonistPortrait({projectId,currentTick}:Props){
  const canvasRef=useRef<HTMLCanvasElement>(null);
  const mouseRef =useRef({x:-9999,y:-9999});
  const rafRef   =useRef(0);
  const dotsRef  =useRef<Dot3[]>([]);
  const rotRef   =useRef({x:-0.15,y:0.20});
  const dragRef  =useRef({active:false,lx:0,ly:0});
  const [is3D,setIs3D]=useState(true);

  const {data,isLoading}=useQuery<PortraitData>({
    queryKey:["portrait",projectId],
    queryFn:()=>get<PortraitData>(`/v1/project/${projectId}/portrait`),
    staleTime:Infinity,refetchOnMount:false,refetchOnWindowFocus:false,retry:1,
  });

  useEffect(()=>{dotsRef.current=buildDots(data??null);},[data]);

  useEffect(()=>{
    const canvas=canvasRef.current;if(!canvas)return;
    const ctx=canvas.getContext("2d")!;
    const SPRING=0.22,DAMP=0.60,REP_R=45,REP_F=6;

    const frame=()=>{
      ctx.clearRect(0,0,W,H);
      const color=data?.color??"#FFB74D";
      const {x:mx,y:my}=mouseRef.current;
      const {x:rotX,y:rotY}=rotRef.current;
      const use3D=is3D;

      const dots=dotsRef.current;
      type Entry={d:Dot3;sx:number;sy:number;sz:number;scale:number};
      const proj:Entry[]=dots.map(d=>{
        if(use3D){const p=project(d.hx,d.hy,d.hz,rotX,rotY);return{d,...p};}
        return{d,sx:d.hx+W/2,sy:d.hy+H/2,sz:0,scale:1};
      });
      if(use3D) proj.sort((a,b)=>b.sz-a.sz);

      for(const{d,sx,sy,sz,scale}of proj){
        const tx=use3D?sx:d.hx+W/2,ty=use3D?sy:d.hy+H/2;
        d.vx+=(tx-d.x)*SPRING;d.vy+=(ty-d.y)*SPRING;
        const dx=d.x-mx,dy=d.y-my,dist2=dx*dx+dy*dy;
        if(dist2<REP_R*REP_R&&dist2>0.01){
          const dist=Math.sqrt(dist2);
          const f=((REP_R-dist)/REP_R)**2*REP_F;
          d.vx+=dx/dist*f;d.vy+=dy/dist*f;
        }
        d.vx*=DAMP;d.vy*=DAMP;d.x+=d.vx;d.y+=d.vy;

        const depthA=use3D?Math.min(1,Math.max(0.25,FOV/Math.max(sz+DEPTH,1))):1;
        const dotR=d.r*Math.min(scale,1.5);
        ctx.beginPath();
        ctx.arc(d.x,d.y,dotR,0,Math.PI*2);
        ctx.fillStyle=color;
        ctx.globalAlpha=depthA*0.88;
        ctx.fill();
      }
      ctx.globalAlpha=1;

      const vg=ctx.createRadialGradient(W/2,H/2,H*0.2,W/2,H/2,W*0.65);
      vg.addColorStop(0,"rgba(0,0,0,0)");
      vg.addColorStop(1,"rgba(10,8,6,0.70)");
      ctx.fillStyle=vg;ctx.fillRect(0,0,W,H);

      rafRef.current=requestAnimationFrame(frame);
    };
    rafRef.current=requestAnimationFrame(frame);
    return()=>cancelAnimationFrame(rafRef.current);
  },[data,is3D]);

  const onMouseMove=useCallback((e:React.MouseEvent)=>{
    const rect=canvasRef.current!.getBoundingClientRect();
    mouseRef.current={x:(e.clientX-rect.left)*(W/rect.width),y:(e.clientY-rect.top)*(H/rect.height)};
    if(is3D&&dragRef.current.active){
      const MAX=1.2217;
      rotRef.current={
        x:Math.max(-MAX,Math.min(MAX,rotRef.current.x+(e.clientY-dragRef.current.ly)*0.005)),
        y:Math.max(-MAX,Math.min(MAX,rotRef.current.y+(e.clientX-dragRef.current.lx)*0.005)),
      };
      dragRef.current.lx=e.clientX;dragRef.current.ly=e.clientY;
    }
  },[is3D]);

  const onMouseDown=useCallback((e:React.MouseEvent)=>{
    if(is3D)dragRef.current={active:true,lx:e.clientX,ly:e.clientY};
  },[is3D]);
  const onUp=useCallback(()=>{dragRef.current.active=false;},[]);
  const onLeave=useCallback(()=>{mouseRef.current={x:-9999,y:-9999};dragRef.current.active=false;},[]);

  const toggle=()=>{
    if(is3D) rotRef.current={x:0,y:0};
    else rotRef.current={x:-0.15,y:0.20};
    setIs3D(v=>!v);
  };

  const color=data?.color??"#FFB74D";

  return(
    <div style={{position:"relative",width:"100%",height:"100%"}}>
      <canvas ref={canvasRef} width={W} height={H}
        style={{width:"100%",height:"100%",display:"block",cursor:is3D?"grab":"crosshair"}}
        onMouseMove={onMouseMove} onMouseDown={onMouseDown}
        onMouseUp={onUp} onMouseLeave={onLeave}/>

      <button onClick={toggle} style={{
        position:"absolute",top:10,right:12,fontSize:"10px",padding:"3px 8px",
        borderRadius:"4px",background:"rgba(10,8,6,0.7)",
        border:`1px solid ${is3D?color:"var(--border)"}`,
        color:is3D?color:"var(--text-3)",cursor:"pointer",letterSpacing:"0.06em",
      }}>{is3D?"3D":"2D"}</button>

      {isLoading&&(
        <div style={{position:"absolute",inset:0,display:"flex",alignItems:"center",
          justifyContent:"center",pointerEvents:"none"}}>
          <span style={{fontSize:"11px",color:"var(--text-3)",letterSpacing:"0.1em"}}>正在生成图腾…</span>
        </div>
      )}
    </div>
  );
}
