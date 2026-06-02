import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityDetail } from "../components/EntityDetail";
import { Spinner } from "../components/ui/Spinner";
import { getRelationships, getCharacter } from "../api/entities";
import type { GraphNode, GraphEdge } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

/* ── simple velocity-verlet layout ── */

interface Vec2 { x: number; y: number }

function layout(nodes: GraphNode[], edges: GraphEdge[], w: number, h: number): Map<string, Vec2> {
  const pos = new Map<string, Vec2>();
  const vel = new Map<string, Vec2>();
  const cx = w / 2, cy = h / 2, r = Math.min(w, h) * 0.40;
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
    pos.set(n.id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    vel.set(n.id, { x: 0, y: 0 });
  });

  for (let iter = 0; iter < 80; iter++) {
    const alpha = 1 - iter / 80;
    for (const n of nodes) {
      const p = pos.get(n.id)!;
      let fx = (cx - p.x) * 0.01;
      let fy = (cy - p.y) * 0.01;
      for (const m of nodes) {
        if (n.id === m.id) continue;
        const q = pos.get(m.id)!;
        const dx = p.x - q.x, dy = p.y - q.y;
        const d = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        fx += (dx / d) * (r * 5) / (d * d);
        fy += (dy / d) * (r * 5) / (d * d);
      }
      for (const e of edges) {
        const other = e.source === n.id ? e.target : e.target === n.id ? e.source : null;
        if (!other) continue;
        const q = pos.get(other)!;
        const dx = q.x - p.x, dy = q.y - p.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        const deg = edges.filter(e2 => e2.source === n.id || e2.target === n.id).length;
        const ideal = 130 + 20 * deg;
        const force = (d - ideal) * 0.02;
        fx += (dx / Math.max(1, d)) * force;
        fy += (dy / Math.max(1, d)) * force;
      }
      const v = vel.get(n.id)!;
      v.x = (v.x + fx) * 0.6 * alpha;
      v.y = (v.y + fy) * 0.6 * alpha;
      p.x += v.x;
      p.y += v.y;
    }
  }
  return pos;
}

/* ── colour by graph structure ── */

const GROUP_HUES = [35, 200, 350, 120, 270, 50, 170, 320, 80, 20];

function nodeColor(n: GraphNode): string {
  const cg = n.colorGroup ?? 0;
  const deg = n.degree ?? 0;
  const hue = GROUP_HUES[cg % GROUP_HUES.length];
  const sat = 55 + Math.min(deg * 12, 35);
  const lit = 45 + Math.min(deg * 3, 15);
  return `hsl(${hue}, ${sat}%, ${lit}%)`;
}

/* ── page ── */

const MIN_SCALE = 0.2, MAX_SCALE = 3;

export function RelationshipsPage() {
  const { id } = useParams<{ id: string }>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [positions, setPositions] = useState<Map<string, Vec2>>(new Map());
  const [dim, setDim] = useState({ w: 800, h: 550 });

  /* viewport */
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState<Vec2>({ x: 0, y: 0 });
  const [panning, setPanning] = useState(false);
  const panStart = useRef<Vec2>({ x: 0, y: 0 });
  const panAnchor = useRef<Vec2>({ x: 0, y: 0 });
  const scaleRef = useRef(1);
  const panRef = useRef<Vec2>({ x: 0, y: 0 });
  scaleRef.current = scale;
  panRef.current = pan;

  const { data, isLoading } = useQuery({
    queryKey: ["relationships", id],
    queryFn: () => getRelationships(id!),
    enabled: !!id,
  });

  const { data: detail } = useQuery({
    queryKey: ["character", id, selectedId],
    queryFn: () => getCharacter(id!, selectedId!),
    enabled: !!selectedId,
  });

  /* layout */
  useEffect(() => {
    if (!data) return;
    setPositions(layout(data.nodes, data.edges, dim.w, dim.h));
  }, [data, dim]);

  /* resize */
  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (!el) return;
    const obs = new ResizeObserver(() => {
      setDim({ w: el.clientWidth || 800, h: el.clientHeight || 550 });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  /* connected nodes for highlight */
  const connected = useCallback((nid: string) => {
    if (!data) return new Set<string>();
    const s = new Set<string>();
    data.edges.forEach((e: GraphEdge) => {
      if (e.source === nid) s.add(e.target);
      if (e.target === nid) s.add(e.source);
    });
    return s;
  }, [data]);

  /* ── pointer events ── */

  const svgPoint = (e: React.PointerEvent): Vec2 => {
    if (!svgRef.current) return { x: 0, y: 0 };
    const r = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  /* node drag */
  const handleNodeDown = (nid: string, e: React.PointerEvent) => {
    e.stopPropagation();
    (e.target as Element).setPointerCapture(e.pointerId);
    setDragId(nid);
  };

  /* background pan */
  const handleBgDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    setPanning(true);
    const pt = svgPoint(e);
    panStart.current = pt;
    panAnchor.current = { ...pan };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    // node drag
    if (dragId && svgRef.current) {
      const pt = svgPoint(e);
      setPositions(prev => {
        const next = new Map(prev);
        next.set(dragId, { x: (pt.x - pan.x) / scale, y: (pt.y - pan.y) / scale });
        return next;
      });
      return;
    }
    // viewport pan
    if (panning) {
      const pt = svgPoint(e);
      const dx = pt.x - panStart.current.x;
      const dy = pt.y - panStart.current.y;
      setPan({ x: panAnchor.current.x + dx, y: panAnchor.current.y + dy });
    }
  };

  const handlePointerUp = () => {
    setDragId(null);
    setPanning(false);
  };

  /* zoom — native listener for passive:false support */
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (!svgRef.current) return;
      const r = svgRef.current.getBoundingClientRect();
      const pt = { x: e.clientX - r.left, y: e.clientY - r.top };
      const curScale = scaleRef.current;
      const curPan = panRef.current;
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, curScale * delta));
      const sx = (pt.x - curPan.x) / curScale;
      const sy = (pt.y - curPan.y) / curScale;
      setPan({ x: pt.x - sx * newScale, y: pt.y - sy * newScale });
      setScale(newScale);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  if (isLoading) return <Spinner />;

  const highlight = hoveredId ? connected(hoveredId) : new Set<string>();

  return (
    <div className="h-full flex flex-col">
      <PageHelp>角色关系图 — 可视化角色之间的社交网络。拖拽节点调整位置，滚轮缩放，悬停高亮关联关系。点击节点查看角色详情。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        {/* graph */}
      <div className="flex-1 relative rounded-xl overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", minHeight: 320 }}>
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          style={{ touchAction: "none", cursor: panning ? "grabbing" : dragId ? "grabbing" : "grab" }}
          onPointerDown={handleBgDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
        >
          {/* viewport group */}
          <g transform={`translate(${pan.x},${pan.y}) scale(${scale})`}>
            {/* edges */}
            {data?.edges.map((e: GraphEdge, i: number) => {
              const sp = positions.get(e.source);
              const tp = positions.get(e.target);
              if (!sp || !tp) return null;
              const mx = (sp.x + tp.x) / 2, my = (sp.y + tp.y) / 2;
              const dx = tp.x - sp.x, dy = tp.y - sp.y;
              const d = Math.sqrt(dx * dx + dy * dy) || 1;
              const nx = (-dy / d) * 28, ny = (dx / d) * 28;
              const faded = hoveredId && !(e.source === hoveredId || e.target === hoveredId);
              // Color by relationship sentiment
              const typeStr = (e.type || "关联").toLowerCase();
              const isPositive = /友|信任|合作|爱|亲密|师徒|救助|恩/.test(typeStr);
              const isNegative = /敌|仇|冲突|恨|背叛|杀|威胁/.test(typeStr);
              const edgeColor = isPositive ? "#8cc88c" : isNegative ? "#e8948c" : "#9ca3af";
              const label = e.type || e.status || "关联";
              const labelW = Math.min(label.length * 12 + 16, 200);
              return (
                <g key={i}>
                  <path d={`M${sp.x},${sp.y} Q${mx + nx},${my + ny} ${tp.x},${tp.y}`}
                    fill="none" stroke={edgeColor} strokeWidth={faded ? 0.5 : 2}
                    opacity={faded ? 0.06 : 0.55} strokeLinecap="round" />
                  <circle cx={mx + nx} cy={my + ny} r={2.5} fill={edgeColor} opacity={faded ? 0.06 : 0.4} />
                  <rect x={mx + nx - labelW / 2} y={my + ny - 22} width={labelW} height={20}
                    rx={10} fill="var(--bg-surface)" stroke={edgeColor} strokeWidth={0.8}
                    opacity={faded ? 0.05 : 0.92} />
                  <text x={mx + nx} y={my + ny - 8} textAnchor="middle" fontSize="11"
                    fill={edgeColor} fontWeight={500} opacity={faded ? 0.08 : 0.95}>
                    {label.length > 12 ? label.slice(0, 11) + "…" : label}
                  </text>
                </g>
              );
            })}

            {/* nodes */}
            {data?.nodes.map((n: GraphNode) => {
              const p = positions.get(n.id);
              if (!p) return null;
              const faded = hoveredId && !(n.id === hoveredId || highlight.has(n.id));
              const deg = n.degree || 0;
              const r = 14 + Math.min(deg * 4, 18);
              const nameW = n.name.length * 14 + 8;
              return (
                <g key={n.id} style={{ cursor: "pointer" }}
                  opacity={faded ? 0.2 : 1}
                  onPointerDown={(e) => handleNodeDown(n.id, e)}
                  onClick={() => setSelectedId(n.id)}
                  onPointerEnter={() => setHoveredId(n.id)}
                  onPointerLeave={() => setHoveredId(null)}
                >
                  <circle cx={p.x} cy={p.y} r={r + 4} fill={nodeColor(n)}
                    opacity={hoveredId === n.id ? 0.3 : 0} style={{ transition: "opacity 0.2s" }} />
                  <circle cx={p.x} cy={p.y} r={r} fill={nodeColor(n)}
                    stroke="var(--bg-base)" strokeWidth={3}
                    style={{ transition: "r 0.15s", filter: `brightness(${hoveredId === n.id ? 1.3 : 1})` }} />
                  <rect x={p.x - nameW / 2} y={p.y + r + 6} width={nameW} height={22}
                    rx={11} fill="var(--bg-surface)" stroke="var(--border)" strokeWidth={0.5}
                    opacity={faded ? 0.1 : 0.9} />
                  <text x={p.x} y={p.y + r + 20} textAnchor="middle" fontSize="12"
                    fontWeight={600} fill="var(--text-1)" opacity={faded ? 0.15 : 0.95}>
                    {n.name}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-4 text-[10px]" style={{ color: "var(--text-3)" }}>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 rounded" style={{ background: "#8cc88c" }} /> 正向</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 rounded" style={{ background: "#e8948c" }} /> 冲突</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 rounded" style={{ background: "#9ca3af" }} /> 中立</span>
        </div>
        {/* zoom controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-1"
          style={{ color: "var(--text-3)", fontSize: "11px" }}>
          <button
            onClick={() => { const s = Math.min(MAX_SCALE, scale * 1.25); setScale(s); }}
            className="w-7 h-7 rounded flex items-center justify-center transition-colors"
            style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-2)" }}
          >+</button>
          <span style={{ minWidth: 40, textAlign: "center" }}>{Math.round(scale * 100)}%</span>
          <button
            onClick={() => { const s = Math.max(MIN_SCALE, scale / 1.25); setScale(s); }}
            className="w-7 h-7 rounded flex items-center justify-center transition-colors"
            style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-2)" }}
          >−</button>
        </div>

      </div>

      {/* detail */}
      {detail && (
        <EntityDetail
          data={detail as unknown as Record<string, unknown>}
          onClose={() => setSelectedId(null)}
          title={(detail.family_name || "") + (detail.first_name || "") || detail.id}
        />
      )}
      </div>
    </div>
  );
}
