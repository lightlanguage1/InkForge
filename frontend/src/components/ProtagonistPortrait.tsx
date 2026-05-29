import { useRef, useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "../api/client";

type ShapeEllipse = { type:"ellipse"; cx:number; cy:number; rx:number; ry:number; density:number };
type ShapeRing    = { type:"ring";   cx:number; cy:number; r:number;  width:number; density:number };
type ShapeLine    = { type:"line";   x1:number; y1:number; x2:number; y2:number; width:number; density:number };
type ShapeArc     = { type:"arc";    cx:number; cy:number; r:number;  a1:number; a2:number; width:number; density:number };
type ShapePoly    = { type:"poly";   points:[number,number][]; density:number };
type Shape = ShapeEllipse|ShapeRing|ShapeLine|ShapeArc|ShapePoly;
interface PortraitData { color:string; caption:string; shapes:Shape[] }
interface Props { projectId:string; currentTick:number }

const PAL: Record<string,{a:string;b:string}> = {
  cyan:   {a:"#38bdf8", b:"rgba(56,189,248,0.18)"},
  purple: {a:"#a78bfa", b:"rgba(167,139,250,0.18)"},
  amber:  {a:"#fbbf24", b:"rgba(251,191,36,0.18)"},
  red:    {a:"#f87171", b:"rgba(248,113,113,0.18)"},
  pink:   {a:"#f472b6", b:"rgba(244,114,182,0.18)"},
  gold:   {a:"#eab308", b:"rgba(234,179,8,0.18)"},
};

const W = 440, H = 330, STEP = 5, DOT_R = 1.5;
const FOV = 600, DEPTH = 600; // perspective params

// ── Geometry helpers ──────────────────────────────────────────────────────────
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
  if(Math.abs(Math.hypot(px-s.cx,py-s.cy)-s.r)>s.width/2) return false;
  let a=(Math.atan2(py-s.cy,px-s.cx)*180/Math.PI+360)%360;
  const a1=(s.a1%360+360)%360,a2=(s.a2%360+360)%360;
  return a1<=a2?(a>=a1&&a<=a2):(a>=a1||a<=a2);
}
function hitShape(px:number,py:number,s:Shape):boolean {
  switch(s.type){
    case"ellipse": return (px-s.cx)**2/Math.max(s.rx,1)**2+(py-s.cy)**2/Math.max(s.ry,1)**2<=1;
    case"ring":    return Math.abs(Math.hypot(px-s.cx,py-s.cy)-s.r)<=s.width/2;
    case"line":    return distSeg(px,py,s.x1,s.y1,s.x2,s.y2)<=s.width/2;
    case"arc":     return inArc(px,py,s);
    case"poly":    return s.points.length>=3&&pip(px,py,s.points);
  }
}

// ── Build grid dots ───────────────────────────────────────────────────────────
type Dot3 = {
  hx:number; hy:number; hz:number; // home 3D (hz = depth layer)
  x:number;  y:number;
  vx:number; vy:number;
};

// Map density to depth layer: high density = foreground, low = background
function densityToDepth(density: number): number {
  if (density >= 2.5) return -20;   // foreground (closest)
  if (density >= 1.8) return 0;     // midground
  return 20;                         // background
}

function buildDots(data:PortraitData|null):Dot3[] {
  if(!data?.shapes?.length) return [];
  const shapes=data.shapes;

  // Bounding box for centering
  let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  for(const s of shapes){
    const pts:number[][]=
      s.type==="ellipse"?[[s.cx-s.rx,s.cy],[s.cx+s.rx,s.cy],[s.cx,s.cy-s.ry],[s.cx,s.cy+s.ry]]:
      s.type==="ring"||s.type==="arc"?[[s.cx-s.r,s.cy],[s.cx+s.r,s.cy],[s.cx,s.cy-s.r],[s.cx,s.cy+s.r]]:
      s.type==="line"?[[s.x1,s.y1],[s.x2,s.y2]]:
      s.points;
    for(const [px,py] of pts){if(px<x0)x0=px;if(px>x1)x1=px;if(py<y0)y0=py;if(py>y1)y1=py;}
  }
  const ox=W/2-(x0+x1)/2, oy=H/2-(y0+y1)/2;

  // Shift shapes
  const shifted:Shape[]=shapes.map(s=>{
    if(s.type==="ellipse") return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="ring")    return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="line")    return {...s,x1:s.x1+ox,y1:s.y1+oy,x2:s.x2+ox,y2:s.y2+oy};
    if(s.type==="arc")     return {...s,cx:s.cx+ox,cy:s.cy+oy};
    if(s.type==="poly")    return {...s,points:s.points.map(([px,py])=>[px+ox,py+oy] as [number,number])};
    return s;
  });

  const dots:Dot3[]=[];
  for(let gy=STEP/2;gy<H;gy+=STEP){
    for(let gx=STEP/2;gx<W;gx+=STEP){
      // Find which shape this dot belongs to (first match wins)
      const hit=shifted.find(s=>hitShape(gx,gy,s));
      if(hit){
        const hz=densityToDepth(hit.density);
        dots.push({hx:gx-W/2, hy:gy-H/2, hz, x:gx, y:gy, vx:0, vy:0});
      }
    }
  }
  return dots;
}

// ── 3D projection ─────────────────────────────────────────────────────────────
function project(hx:number,hy:number,hz:number,rotX:number,rotY:number):{sx:number;sy:number;sz:number} {
  // Rotate around Y axis
  const cosY=Math.cos(rotY),sinY=Math.sin(rotY);
  const rx1=hx*cosY-hz*sinY, rz1=hx*sinY+hz*cosY;
  // Rotate around X axis
  const cosX=Math.cos(rotX),sinX=Math.sin(rotX);
  const ry2=hy*cosX-rz1*sinX, rz2=hy*sinX+rz1*cosX;
  const sz=rz2+DEPTH;
  const scale=FOV/Math.max(sz,1);
  return {sx:W/2+rx1*scale, sy:H/2+ry2*scale, sz:rz2};
}

// ── Component ─────────────────────────────────────────────────────────────────
export function ProtagonistPortrait({projectId,currentTick}:Props){
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef  = useRef({x:-9999,y:-9999});
  const rafRef    = useRef(0);
  const dotsRef   = useRef<Dot3[]>([]);
  const rotRef    = useRef({x:-0.18,y:0.25}); // slight initial tilt
  const dragRef   = useRef({active:false,lx:0,ly:0});
  const [is3D,    setIs3D]    = useState(true);
  const [flatRot, setFlatRot] = useState({x:-0.18,y:0.25});

  const {data,isLoading} = useQuery<PortraitData>({
    queryKey:["portrait",projectId],
    queryFn:()=>get<PortraitData>(`/v1/project/${projectId}/portrait`),
    staleTime:Infinity, refetchOnMount:false, refetchOnWindowFocus:false, retry:1,
  });

  useEffect(()=>{ dotsRef.current=buildDots(data??null); },[data]);

  useEffect(()=>{
    const canvas=canvasRef.current; if(!canvas) return;
    const ctx=canvas.getContext("2d")!;
    const SPRING=0.055, DAMP=0.70, REP_R=48, REP_F=5;

    const frame=()=>{
      ctx.clearRect(0,0,W,H);
      const pal=PAL[data?.color??"amber"]??PAL.amber;
      const {x:mx,y:my}=mouseRef.current;
      const rotX=rotRef.current.x, rotY=rotRef.current.y;
      const use3D=is3D;

      // Sort by depth for painter's algorithm in 3D
      const dots=dotsRef.current;
      const projected=dots.map(d=>{
        if(use3D){
          const {sx,sy,sz}=project(d.hx,d.hy,d.hz,rotX,rotY);
          return {d,sx,sy,sz};
        }
        return {d,sx:d.x,sy:d.y,sz:0};
      });
      if(use3D) projected.sort((a,b)=>b.sz-a.sz);

      for(const {d,sx,sy,sz} of projected){
        // Physics in screen space
        const tx=use3D?sx:d.hx+W/2, ty=use3D?sy:d.hy+H/2;
        d.vx+=(tx-d.x)*SPRING;
        d.vy+=(ty-d.y)*SPRING;
        const dx=d.x-mx,dy=d.y-my,dist2=dx*dx+dy*dy;
        if(dist2<REP_R*REP_R&&dist2>0.01){
          const dist=Math.sqrt(dist2);
          const f=((REP_R-dist)/REP_R)**2*REP_F;
          d.vx+=dx/dist*f; d.vy+=dy/dist*f;
        }
        d.vx*=DAMP; d.vy*=DAMP;
        d.x+=d.vx; d.y+=d.vy;

        // Size & alpha scale with depth in 3D
        const depthScale=use3D?FOV/Math.max(sz+DEPTH,1):1;
        const r=DOT_R*Math.min(depthScale,1.6);
        const a=use3D?Math.min(0.92,0.4+depthScale*0.5):0.88;

        ctx.beginPath();
        ctx.arc(d.x,d.y,r,0,Math.PI*2);
        ctx.fillStyle=pal.a;
        ctx.globalAlpha=a;
        ctx.fill();
      }

      ctx.globalAlpha=1;
      const vg=ctx.createRadialGradient(W/2,H/2,H*0.2,W/2,H/2,W*0.62);
      vg.addColorStop(0,"rgba(0,0,0,0)");
      vg.addColorStop(1,"rgba(10,8,6,0.72)");
      ctx.fillStyle=vg; ctx.fillRect(0,0,W,H);

      rafRef.current=requestAnimationFrame(frame);
    };
    rafRef.current=requestAnimationFrame(frame);
    return ()=>cancelAnimationFrame(rafRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[data,is3D]);

  // Mouse handlers
  const onMouseMove=useCallback((e:React.MouseEvent)=>{
    const rect=canvasRef.current!.getBoundingClientRect();
    const cx=(e.clientX-rect.left)*(W/rect.width);
    const cy=(e.clientY-rect.top)*(H/rect.height);
    mouseRef.current={x:cx,y:cy};
    if(is3D&&dragRef.current.active){
      const dx=(e.clientX-dragRef.current.lx)*0.006;
      const dy=(e.clientY-dragRef.current.ly)*0.006;
      const MAX_ROT=0.42; // ±24°, shape never collapses to a line
      rotRef.current={
        x:Math.max(-MAX_ROT,Math.min(MAX_ROT,rotRef.current.x+dy)),
        y:Math.max(-MAX_ROT,Math.min(MAX_ROT,rotRef.current.y+dx)),
      };
      dragRef.current.lx=e.clientX; dragRef.current.ly=e.clientY;
    }
  },[is3D]);

  const onMouseDown=useCallback((e:React.MouseEvent)=>{
    if(is3D){ dragRef.current={active:true,lx:e.clientX,ly:e.clientY}; }
  },[is3D]);

  const onMouseUp=useCallback(()=>{ dragRef.current.active=false; },[]);

  const onMouseLeave=useCallback(()=>{
    mouseRef.current={x:-9999,y:-9999};
    dragRef.current.active=false;
  },[]);

  const toggle3D=()=>{
    if(is3D){
      setFlatRot({x:rotRef.current.x,y:rotRef.current.y});
      rotRef.current={x:0,y:0};
    } else {
      rotRef.current=flatRot;
    }
    setIs3D(v=>!v);
  };

  const pal=PAL[data?.color??"amber"]??PAL.amber;

  return(
    <div style={{position:"relative",width:"100%",height:"100%"}}>
      <canvas
        ref={canvasRef} width={W} height={H}
        style={{width:"100%",height:"100%",display:"block",
          cursor:is3D?"grab":"crosshair"}}
        onMouseMove={onMouseMove}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseLeave}
      />

      {/* 3D toggle */}
      <button
        onClick={toggle3D}
        style={{
          position:"absolute",top:10,right:12,
          fontSize:"10px",padding:"3px 8px",borderRadius:"4px",
          background:"rgba(10,8,6,0.7)",border:`1px solid ${is3D?pal.a:"var(--border)"}`,
          color:is3D?pal.a:"var(--text-3)",cursor:"pointer",letterSpacing:"0.06em",
          pointerEvents:"all",
        }}
      >
        {is3D?"3D ·拖拽旋转":"2D"}
      </button>

      {!isLoading&&data?.caption&&(
        <div style={{position:"absolute",bottom:0,left:0,right:0,
          padding:"6px 14px 10px",
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
