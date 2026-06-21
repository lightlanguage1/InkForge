import { useState, useMemo, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTimeline, switchBranch as apiSwitchBranch, type TimelineNode, type TimelineBranch, type TimelineCheckpoint } from "../api/timeline";
import { restoreCheckpoint, listCheckpoints } from "../api/checkpoints";
import { Spinner } from "../components/ui/Spinner";
import { PageHelp } from "../components/PageHelp";

/* ═══════════════════════════════════════════════════════════════
   Timeline — 故事时间线
   主线 + IF 分支 + 存档联动
   ═══════════════════════════════════════════════════════════════ */

function shortHash(h: string) { return h?.slice(0, 7) ?? ""; }

export function TimelinePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);

  /* ── 数据 ── */
  const { data: tl, isLoading } = useQuery({
    queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: !!id,
  });
  const { data: cps } = useQuery({
    queryKey: ["checkpoints", id], queryFn: () => listCheckpoints(id!), enabled: !!id, staleTime: 0,
  });

  /* ── 状态 ── */
  const [detailNode, setDetailNode] = useState<TimelineNode | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<TimelineCheckpoint | null>(null);
  const [branchTarget, setBranchTarget] = useState<TimelineBranch | null>(null);
  const [showBranches, setShowBranches] = useState(false);

  /* ── mutations ── */
  const restoreMut = useMutation({
    mutationFn: (cpId: string) => restoreCheckpoint(id!, cpId),
    onSuccess: () => { qc.invalidateQueries(); setRestoreTarget(null); navigate(`/project/${id}`, { replace: true }); },
  });
  const switchMut = useMutation({
    mutationFn: (name: string) => apiSwitchBranch(id!, name),
    onSuccess: () => { qc.invalidateQueries(); setBranchTarget(null); navigate(`/project/${id}`, { replace: true }); },
  });

  /* ── 构建时间线 ── */
  const { mainLine, forkLines, allBranches } = useMemo(() => {
    if (!tl?.nodes?.length) return { mainLine: [], forkLines: [] as TimelineNode[][], allBranches: [] as TimelineBranch[] };
    const nodes = [...tl.nodes].sort((a, b) => a.tick - b.tick);
    const activeBranch = tl.current_branch || "main";
    const branches = (tl.branches ?? []) as TimelineBranch[];

    const main = nodes.filter(n => n.branch === activeBranch && !n.archived);
    const seen = new Set<number>();
    const deduped = main.filter(n => { if (seen.has(n.tick)) return false; seen.add(n.tick); return true; });

    const forks: TimelineNode[][] = [];
    const forkNames = new Set(nodes.filter(n => n.branch !== activeBranch).map(n => n.branch));
    forkNames.forEach(fn => {
      const fnodes = nodes.filter(n => n.branch === fn).sort((a, b) => a.tick - b.tick);
      if (fnodes.length > 0) forks.push(fnodes);
    });

    return { mainLine: deduped, forkLines: forks, allBranches: branches };
  }, [tl]);

  const checkpoints = (cps?.checkpoints ?? []) as any[];
  const timelineCheckpoints = (tl?.checkpoints ?? []) as TimelineCheckpoint[];

  /* ── 自动滚到当前 tick ── */
  useEffect(() => {
    if (!scrollRef.current || !mainLine.length) return;
    const ct = tl?.current_tick ?? 0;
    const idx = mainLine.findIndex(n => n.tick === ct);
    if (idx >= 0) {
      const el = scrollRef.current.children[idx + 1] as HTMLElement; // +1 因为第一个是分支面板
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [tl?.current_tick]);

  if (isLoading) return <div className="flex justify-center py-32"><Spinner /></div>;

  const currentTick = tl?.current_tick ?? 0;
  const currentBranch = tl?.current_branch ?? "main";
  const activeBranches = allBranches.filter(b => b.active);
  const inactiveBranches = allBranches.filter(b => !b.active);

  if (!mainLine.length) return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <span className="text-5xl mb-4 opacity-10">◈</span>
      <p className="text-sm" style={{ color: "var(--text-2)" }}>暂无场景，先生成一些章节</p>
    </div>
  );

  return (
    <div className="h-full flex flex-col" style={{ background: "var(--bg-base)" }}>
      <PageHelp>时间线 — 主线如树干向上生长，存档点和 IF 分支可在侧栏查看。点击存档可恢复，点击分支可切换查看。</PageHelp>

      {/* ═══════════════════ Header ═══════════════════ */}
      <header className="flex-shrink-0 flex items-center justify-between px-4 md:px-6 py-3"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate(`/project/${id}`)}
            className="text-xs flex items-center gap-1.5 hover:opacity-70"
            style={{ color: "var(--text-3)", background: "none", border: "none", cursor: "pointer" }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            返回
          </button>
          <h1 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>故事时间线</h1>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded hidden sm:inline"
            style={{ background: "var(--bg-raised)", color: "var(--text-3)" }}>
            {currentBranch} · tick {currentTick}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* 分支选择器 */}
          {inactiveBranches.length > 0 && (
            <div className="relative">
              <button onClick={() => setShowBranches(!showBranches)}
                className="flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-lg transition-all"
                style={{
                  background: showBranches ? "rgba(200,151,90,0.1)" : "var(--bg-raised)",
                  color: showBranches ? "var(--accent)" : "var(--text-3)",
                  border: `1px solid ${showBranches ? "rgba(200,151,90,0.2)" : "var(--border)"}`,
                  cursor: "pointer",
                }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 3v18M18 9a3 3 0 100-6 3 3 0 000 6zM18 21a3 3 0 100-6 3 3 0 000 6z"/>
                </svg>
                IF 分支 ({inactiveBranches.length})
              </button>
              {showBranches && (
                <div className="absolute right-0 top-full mt-1 w-64 rounded-xl overflow-hidden z-30"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 12px 40px rgba(0,0,0,0.4)" }}>
                  <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider"
                    style={{ color: "var(--text-3)", borderBottom: "1px solid var(--border)" }}>
                    可用分支
                  </div>
                  {activeBranches.map(b => (
                    <div key={b.name} className="px-3 py-2 text-[12px] flex justify-between items-center"
                      style={{ background: "rgba(200,151,90,0.06)", color: "var(--accent)" }}>
                      <span className="font-mono text-[11px]">{b.name}</span>
                      <span className="text-[10px]">← 当前</span>
                    </div>
                  ))}
                  {inactiveBranches.map(b => (
                    <button key={b.name}
                      onClick={() => { setShowBranches(false); setBranchTarget(b); }}
                      className="w-full px-3 py-2 text-[12px] flex justify-between items-center hover:brightness-110 transition-all"
                      style={{ background: "transparent", color: "var(--text-2)", border: "none", borderBottom: "1px solid var(--border)", cursor: "pointer" }}>
                      <span>
                        <span className="font-mono text-[11px]">{b.name.replace("fork_", "").slice(0, 12)}</span>
                        {b.message && <span className="ml-2 text-[10px]" style={{ color: "var(--text-3)" }}>{b.message.slice(0, 20)}</span>}
                      </span>
                      <span className="text-[10px] font-mono" style={{ color: "var(--text-3)" }}>{b.tick}幕</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* 存档按钮 */}
          {checkpoints.length > 0 && (
            <span className="text-[11px] hidden sm:inline" style={{ color: "var(--text-3)" }}>
              ● {checkpoints.length} 存档
            </span>
          )}
        </div>
      </header>

      {/* ═══════════════════ 存档面板 ═══════════════════ */}
      {checkpoints.length > 0 && (
        <div className="flex-shrink-0 px-4 md:px-6 py-2 flex items-center gap-2 overflow-x-auto"
          style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          <span className="text-[10px] font-semibold uppercase tracking-wider flex-shrink-0" style={{ color: "var(--text-3)" }}>
            存档点
          </span>
          {checkpoints.map((cp: any) => (
            <button key={cp.checkpoint_id || cp.id}
              onClick={() => setRestoreTarget({ id: cp.checkpoint_id || cp.id, tick: cp.tick, hash: "", label: cp.created_by || cp.label || "" })}
              className="flex-shrink-0 text-[10px] px-2 py-1 rounded-full transition-all hover:brightness-110"
              style={{
                background: cp.tick === currentTick ? "rgba(77,170,133,0.12)" : "var(--bg-raised)",
                color: cp.tick === currentTick ? "#4daa85" : "var(--text-3)",
                border: "none", cursor: "pointer",
              }}>
              t{cp.tick} {cp.created_by === "auto" || (cp.checkpoint_id || cp.id || "").includes("auto") ? "自动" : "手动"}
            </button>
          ))}
        </div>
      )}

      {/* ═══════════════════ 主线时间线 ═══════════════════ */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-1.5">

        {mainLine.map((n, i) => {
          const isCurrent = n.tick === currentTick;
          const cpHere = checkpoints.filter((c: any) => c.tick === n.tick);
          const isFirst = n.tick === 0;
          const isLatest = i === mainLine.length - 1;

          return (
            <div key={n.tick} className="relative mx-auto w-full max-w-2xl">
              {/* 连接线 */}
              {!isFirst && (
                <div className="absolute left-[13px] top-[-8px] w-px h-2"
                  style={{ background: isCurrent ? "var(--accent)" : "var(--border)" }} />
              )}

              {/* 节点卡片 */}
              <div className="flex items-start gap-3 py-2 px-3 rounded-lg cursor-pointer transition-all duration-150"
                style={{
                  background: isCurrent ? "rgba(200,151,90,0.06)" : "transparent",
                  border: isCurrent ? "1px solid rgba(200,151,90,0.12)" : "1px solid transparent",
                }}
                onClick={() => setDetailNode(n)}
                onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = "var(--bg-raised)"; }}
                onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.background = "transparent"; }}>

                {/* 圆点 */}
                <div className="flex-shrink-0 relative mt-0.5">
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: isCurrent ? "var(--accent)" : isFirst ? "#4daa85" : "var(--border)",
                    boxShadow: isCurrent ? "0 0 8px var(--accent)" : "none",
                  }} />
                  {isCurrent && (
                    <div style={{
                      position: "absolute", inset: -3, borderRadius: "50%",
                      border: "1px solid var(--accent)", opacity: 0.25,
                      animation: "tlPulse 2s ease-out infinite",
                    }} />
                  )}
                </div>

                {/* 内容 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-mono font-medium" style={{ color: isCurrent ? "var(--accent)" : "var(--text-2)" }}>
                      S{n.tick.toString().padStart(3, "0")}
                    </span>
                    {n.title ? (
                      <span className="text-[12px] truncate" style={{ color: isCurrent ? "var(--text-1)" : "var(--text-2)" }}>
                        {n.title.slice(0, 45)}{n.title.length > 45 ? "…" : ""}
                      </span>
                    ) : (
                      <span className="text-[11px] italic" style={{ color: "var(--text-3)" }}>未命名场景</span>
                    )}
                    {isFirst && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(77,170,133,0.1)", color: "#4daa85" }}>ROOT</span>}
                    {isLatest && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(200,151,90,0.1)", color: "var(--accent)" }}>HEAD</span>}
                  </div>

                  {/* 存档点标记 */}
                  {cpHere.length > 0 && (
                    <div className="flex items-center gap-1.5 mt-1">
                      {cpHere.map((cp: any) => (
                        <button key={cp.checkpoint_id || cp.tick}
                          onClick={e => { e.stopPropagation(); setRestoreTarget({ id: cp.checkpoint_id || cp.id, tick: cp.tick, hash: "", label: cp.created_by || cp.label || "" }); }}
                          className="text-[9px] px-1.5 py-0.5 rounded-full font-medium transition-all hover:brightness-110"
                          style={{ background: "rgba(77,170,133,0.08)", color: "#4daa85", border: "none", cursor: "pointer" }}>
                          ●
                        </button>
                      ))}
                    </div>
                  )}

                  {/* commit hash */}
                  <div className="text-[9px] font-mono mt-0.5" style={{ color: "var(--text-3)", opacity: 0.5 }}>
                    {shortHash(n.hash)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        {/* 底部 */}
        <div className="flex justify-center py-8">
          <span className="text-[10px]" style={{ color: "var(--text-3)", opacity: 0.4, fontFamily: "'Cormorant Garamond', serif" }}>
            —— 故事从根部开始生长 ——
          </span>
        </div>
      </div>

      {/* ═══════════════════ 节点详情弹窗 ═══════════════════ */}
      {detailNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
          onClick={e => { if (e.target === e.currentTarget) setDetailNode(null); }}>
          <div className="rounded-2xl p-5 w-full max-w-xs animate-fade-in"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>
                S{String(detailNode.tick).padStart(3, "0")}
              </h3>
              <button onClick={() => setDetailNode(null)}
                className="text-base opacity-30 hover:opacity-60"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-2)" }}>✕</button>
            </div>
            <div className="space-y-2 text-[12px]">
              {[
                ["标题", detailNode.title || "—"],
                ["分支", detailNode.branch],
                ["Tick", String(detailNode.tick)],
                ["Commit", shortHash(detailNode.hash)],
                ["Parent", detailNode.parent ? shortHash(detailNode.parent) : "— (root)"],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between">
                  <span style={{ color: "var(--text-3)" }}>{label}</span>
                  <span className="font-mono text-[11px]" style={{ color: label === "Commit" ? "var(--accent)" : "var(--text-2)" }}>{val}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-5">
              <button onClick={() => { setDetailNode(null); navigate(`/project/${id}`); }}
                className="flex-1 py-2 rounded-lg text-[12px] font-medium"
                style={{ background: "rgba(200,151,90,0.08)", color: "var(--accent)", border: "1px solid rgba(200,151,90,0.12)", cursor: "pointer" }}>
                返回概览
              </button>
              <button onClick={() => setDetailNode(null)}
                className="px-4 py-2 rounded-lg text-[12px]"
                style={{ background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)", cursor: "pointer" }}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ 存档恢复确认 ═══════════════════ */}
      {restoreTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
          onClick={e => { if (e.target === e.currentTarget) setRestoreTarget(null); }}>
          <div className="rounded-2xl p-5 w-full max-w-xs animate-fade-in"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
            <h3 className="font-semibold text-sm mb-2" style={{ color: "var(--text-1)" }}>恢复存档</h3>
            <p className="text-[12px] leading-relaxed mb-1" style={{ color: "var(--text-2)" }}>
              恢复到 <b style={{ color: "#4daa85" }}>{restoreTarget.id}</b>（tick {restoreTarget.tick}）
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-3)" }}>当前进度自动保存为新分支，不会丢失。</p>
            <div className="flex gap-2 mt-4">
              <button onClick={() => restoreMut.mutate(restoreTarget.id)} disabled={restoreMut.isPending}
                className="flex-1 py-2 rounded-lg text-[12px] font-medium"
                style={{ background: "#4daa85", color: "#fff", border: "none", cursor: "pointer", opacity: restoreMut.isPending ? 0.5 : 1 }}>
                {restoreMut.isPending ? "…" : "确认恢复"}
              </button>
              <button onClick={() => setRestoreTarget(null)}
                className="px-4 py-2 rounded-lg text-[12px]"
                style={{ background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)", cursor: "pointer" }}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ 分支切换确认 ═══════════════════ */}
      {branchTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
          onClick={e => { if (e.target === e.currentTarget) setBranchTarget(null); }}>
          <div className="rounded-2xl p-5 w-full max-w-xs animate-fade-in"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
            <h3 className="font-semibold text-sm mb-2" style={{ color: "var(--text-1)" }}>切换到 IF 分支</h3>
            <p className="text-[12px] leading-relaxed mb-1" style={{ color: "var(--text-2)" }}>
              进入 <b style={{ color: "var(--accent-lit)" }}>{branchTarget.name}</b>（{branchTarget.tick} 幕）
            </p>
            <p className="text-[11px]" style={{ color: "var(--text-3)" }}>当前主线进度保留，可随时切回。</p>
            <div className="text-[10px] font-mono mt-2" style={{ color: "var(--text-3)" }}>
              {shortHash(branchTarget.hash)}{branchTarget.message ? ` · ${branchTarget.message.slice(0, 30)}` : ""}
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => switchMut.mutate(branchTarget.name)} disabled={switchMut.isPending}
                className="flex-1 py-2 rounded-lg text-[12px] font-medium"
                style={{ background: "rgba(200,151,90,0.1)", color: "var(--accent)", border: "1px solid rgba(200,151,90,0.2)", cursor: "pointer", opacity: switchMut.isPending ? 0.5 : 1 }}>
                {switchMut.isPending ? "…" : "确认切换"}
              </button>
              <button onClick={() => setBranchTarget(null)}
                className="px-4 py-2 rounded-lg text-[12px]"
                style={{ background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)", cursor: "pointer" }}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes tlPulse {
          0% { transform: scale(1); opacity: 0.35; }
          100% { transform: scale(2.2); opacity: 0; }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(6px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .animate-fade-in { animation: fadeIn 0.2s ease-out; }
      `}</style>
    </div>
  );
}
