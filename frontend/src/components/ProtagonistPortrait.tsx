import { useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../api/client";

// ── Types ─────────────────────────────────────────────────────────────────────
type ShapeEllipse = { type:"ellipse"; cx:number; cy:number; rx:number; ry:number; density:number };
type ShapeRing    = { type:"ring";   cx:number; cy:number; r:number;  width:number; density:number };
type ShapeLine    = { type:"line";   x1:number; y1:number; x2:number; y2:number; width:number; density:number };
type ShapeArc     = { type:"arc";    cx:number; cy:number; r:number;  a1:number; a2:number; width:number; density:number };
type ShapePoly    = { type:"poly";   points:[number,number][]; density:number };
type Shape = ShapeEllipse | ShapeRing | ShapeLine | ShapeArc | ShapePoly;
interface PortraitData { color:string; caption:string; shapes:Shape[] }
interface Props { projectId:string; currentTick:number }

// ── Palette ───────────────────────────────────────────────────────────────────
const PAL: Record<string,{a:string;b:string}> = {
  cyan:   {a:"#38bdf8",b:"rgba(56,189,248,0.12)"},
  purple: {a:"#a78bfa",b:"rgba(167,139,250,0.12)"},
  amber:  {a:"#fbbf24",b:"rgba(251,191,36,0.12)"},
  red:    {a:"#f87171",b:"rgba(248,113,113,0.12)"},
  pink:   {a:"#f472b6",b:"rgba(244,114,182,0.12)"},
  gold:   {a:"#eab308",b:"rgba(234,179,8,0.12)"},
};

const W    = 400;
const H    = 300;
const STEP = 8;   // grid spacing px — controls dot density / spacing
const DOT_R = 1.4; // uniform dot radius

// ── Shape hit-tests ───────────────────────────────────────────────────────────
function distToSegment(px:number,py:number,x1:number,y1:number,x2:number,y2:number):number {
  const dx=x2-x1, dy=y2-y1, len2=dx*dx+dy*dy;
  if(len2===0) return Math.hypot(px-x1,py-y1);
  const t=Math.max(0,Math.min(1,((px-x1)*dx+(py-y1)*dy)/len2));
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
  const d=Math.hypot(px-s.cx,py-s.cy);
  if(Math.abs(d-s.r)>s.width/2) return false;
  let a=(Math.atan2(py-s.cy,px-s.cx)*180/Math.PI+360)%360;
  const a1=(s.a1%360+360)%360, a2=(s.a2%360+360)%360;
  return a1<=a2 ? (a>=a1&&a<=a2) : (a>=a1||a<=a2);
}
function hitShape(px:number,py:number,s:Shape):boolean {
  switch(s.type){
    case"ellipse": return (px-s.cx)**2/s.rx**2+(py-s.cy)**2/s.ry**2<=1;
    case"ring":    return Math.abs(Math.hypot(px-s.cx,py-s.cy)-s.r)<=s.width/2;
    case"line":    return distToSegment(px,py,s.x1,s.y1,s.x2,s.y2)<=s.width/2;
    case"arc":     return inArc(px,py,s);
    case"poly":    return pip(px,py,s.points);
  }
}

// ── Build grid dots ───────────────────────────────────────────────────────────
type Dot = {hx:number;hy:number;x:number;y:number;vx:number;vy:number;on:boolean};

function buildDots(data:PortraitData|null):Dot[] {
  const shapes = data?.shapes ?? [];
  const dots:Dot[] = [];

  // Determine bounding box of all shapes to compute centering offset
  let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
  for(const s of shapes){
    const pts:number[][]=[];
    if(s.type==="ellipse") pts.push([s.cx-s.rx,s.cy],[s.cx+s.rx,s.cy],[s.cx,s.cy-s.ry],[s.cx,s.cy+s.ry]);
    else if(s.type==="ring") pts.push([s.cx-s.r-s.width/2,s.cy],[s.cx+s.r+s.width/2,s.cy],[s.cx,s.cy-s.r-s.width/2],[s.cx,s.cy+s.r+s.width/2]);
    else if(s.type==="line") pts.push([s.x1,s.y1],[s.x2,s.y2]);
    else if(s.type==="arc")  pts.push([s.cx-s.r,s.cy],[s.cx+s.r,s.cy],[s.cx,s.cy-s.r],[s.cx,s.cy+s.r]);
    else if(s.type==="poly") s.points.forEach(p=>pts.push(p));
    for(const [x,y] of pts){ if(x<minX)minX=x; if(x>maxX)maxX=x; if(y<minY)minY=y; if(y>maxY)maxY=y; }
  }
  const offX = shapes.length ? W/2-(minX+maxX)/2 : 0;
  const offY = shapes.length ? H/2-(minY+maxY)/2 : 0;

  // Shift all shapes by offset so they center on canvas
  const shifted:Shape[] = shapes.map(s=>{
    if(s.type==="ellipse") return {...s,cx:s.cx+offX,cy:s.cy+offY};
    if(s.type==="ring")    return {...s,cx:s.cx+offX,cy:s.cy+offY};
    if(s.type==="line")    return {...s,x1:s.x1+offX,y1:s.y1+offY,x2:s.x2+offX,y2:s.y2+offY};
    if(s.type==="arc")     return {...s,cx:s.cx+offX,cy:s.cy+offY};
    if(s.type==="poly")    return {...s,points:s.points.map(([x,y])=>[x+offX,y+offY] as [number,number])};
    return s;
  });

  // Grid scan
  for(let gy=STEP/2;gy<H;gy+=STEP){
    for(let gx=STEP/2;gx<W;gx+=STEP){
      const on = shifted.some(s=>hitShape(gx,gy,s));
      if(on){
        dots.push({hx:gx,hy:gy,x:gx,y:gy,vx:0,vy:0,on:true});
      }
    }
  }
  return dots;
}

// ── Component ─────────────────────────────────────────────────────────────────
export function ProtagonistPortrait({projectId,currentTick}:Props){
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef  = useRef({x:-9999,y:-9999});
  const rafRef    = useRef(0);
  const dotsRef   = useRef<Dot[]>([]);

  const {data,isLoading} = useQuery<PortraitData>({
    queryKey:["portrait",projectId],
    queryFn:()=>get<PortraitData>(`/v1/project/${projectId}/portrait`),
    staleTime:Infinity,
    refetchOnMount:false,
    refetchOnWindowFocus:false,
    retry:1,
  });

  useEffect(()=>{ dotsRef.current=buildDots(data??null); },[data]);

  useEffect(()=>{
    const canvas=canvasRef.current;
    if(!canvas) return;
    const ctx=canvas.getContext("2d")!;
    const SPRING=0.048, DAMP=0.72, REP_R=50, REP_F=6;

    const frame=()=>{
      ctx.clearRect(0,0,W,H);
      const pal=PAL[data?.color??"amber"]??PAL.amber;
      const {x:mx,y:my}=mouseRef.current;

      for(const d of dotsRef.current){
        // Spring back
        d.vx+=(d.hx-d.x)*SPRING;
        d.vy+=(d.hy-d.y)*SPRING;
        // Mouse repulsion
        const dx=d.x-mx,dy=d.y-my,dist2=dx*dx+dy*dy;
        if(dist2<REP_R*REP_R&&dist2>0.01){
          const dist=Math.sqrt(dist2);
          const f=((REP_R-dist)/REP_R)**2*REP_F;
          d.vx+=dx/dist*f; d.vy+=dy/dist*f;
        }
        d.vx*=DAMP; d.vy*=DAMP;
        d.x+=d.vx; d.y+=d.vy;

        ctx.beginPath();
        ctx.arc(d.x,d.y,DOT_R,0,Math.PI*2);
        ctx.fillStyle  = d.on ? pal.a : pal.b;
        ctx.globalAlpha= d.on ? 0.90 : 1;
        ctx.fill();
      }

      ctx.globalAlpha=1;
      // Subtle edge vignette only
      const vg=ctx.createRadialGradient(W/2,H/2,H*0.25,W/2,H/2,W*0.62);
      vg.addColorStop(0,"rgba(0,0,0,0)");
      vg.addColorStop(1,"rgba(10,8,6,0.70)");
      ctx.fillStyle=vg;
      ctx.fillRect(0,0,W,H);

      rafRef.current=requestAnimationFrame(frame);
    };
    rafRef.current=requestAnimationFrame(frame);
    return ()=>cancelAnimationFrame(rafRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[data]);

  const pal=PAL[data?.color??"amber"]??PAL.amber;
  return(
    <div style={{position:"relative",width:"100%",height:"100%"}}>
      <canvas
        ref={canvasRef} width={W} height={H}
        style={{width:"100%",height:"100%",display:"block",cursor:"crosshair"}}
        onMouseMove={e=>{
          const rect=canvasRef.current!.getBoundingClientRect();
          mouseRef.current={
            x:(e.clientX-rect.left)*(W/rect.width),
            y:(e.clientY-rect.top)*(H/rect.height),
          };
        }}
        onMouseLeave={()=>{mouseRef.current={x:-9999,y:-9999};}}
      />
      {!isLoading&&data?.caption&&(
        <div style={{position:"absolute",bottom:0,left:0,right:0,padding:"6px 14px 10px",
          background:"linear-gradient(to top,rgba(10,8,6,0.88) 50%,transparent)",
          pointerEvents:"none"}}>
          <span style={{fontSize:"11px",color:pal.a,letterSpacing:"0.06em"}}>{data.caption}</span>
        </div>
      )}
      {isLoading&&(
        <div style={{position:"absolute",inset:0,display:"flex",alignItems:"center",
          justifyContent:"center",pointerEvents:"none"}}>
          <span style={{fontSize:"11px",color:"var(--text-3)",letterSpacing:"0.1em"}}>正在生成图腾…</span>
        </div>
      )}
    </div>
  );
}
