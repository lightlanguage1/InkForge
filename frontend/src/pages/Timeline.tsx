import { useState, useCallback, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTimeline, switchBranch as apiSwitchBranch } from "../api/entities";
import { listCheckpoints, restoreCheckpoint } from "../api/checkpoints";
import { PageHelp } from "../components/PageHelp";
import { Spinner } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";

/* ── 大树布局 ── */
const TICK_GAP = 90;
const NODE_R = 7;
const TRUNK_X = 440;
const BRANCH_SPREAD = 55;

/* ── 颜色 ── */
const AUTO_CP = "#4daa85";
const MANUAL_CP = "#c8975a";
const ACTIVE = "var(--accent)";

export function TimelinePage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: tl, isLoading } = useQuery({
    queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: !!id,
  });
  const { data: cps } = useQuery({
    queryKey: ["checkpoints", id], queryFn: () => listCheckpoints(id!), enabled: !!id,
  });

  const [hoveredCp, setHoveredCp] = useState<string | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<{ id: string; type: string } | null>(null);
  const [branchTarget, setBranchTarget] = useState<{ id: string; headTick: number; backupId: string } | null>(null);

  const restoreMut = useMutation({
    mutationFn: (cpId: string) => restoreCheckpoint(id!, cpId),
    onSuccess: () => {
      // 全量刷新——状态/场景/时间线/存档全部变化
      qc.invalidateQueries();
      setRestoreTarget(null);
      setBranchTarget(null);
      // 延迟一下让后端状态落盘
      setTimeout(() => window.location.reload(), 500);
    },
  });

  const handleRestore = useCallback(() => {
    if (restoreTarget && confirm(`切换到存档 "${restoreTarget.id}"？当前进度自动备份为分支，历史不丢失。`)) {
      restoreMut.mutate(restoreTarget.id);
    }
  }, [restoreTarget, restoreMut]);

  const switchMut = useMutation({
    mutationFn: (branchName: string) => apiSwitchBranch(id!, branchName),
    onSuccess: () => {
      qc.invalidateQueries();
      setBranchTarget(null);
      setTimeout(() => window.location.reload(), 300);
    },
  });

  const handleBranchSwitch = useCallback(() => {
    if (branchTarget && confirm(`切换到分支 "${branchTarget.id}"（共 ${branchTarget.headTick + 1} 幕）？`)) {
      switchMut.mutate(branchTarget.id);
    }
  }, [branchTarget, switchMut]);

  // ── 构建大树布局 ──
  const { trunkNodes, branchGroups, treeH, svgW } = useMemo(() => {
    const rawNodes = (tl?.nodes ?? []) as any[];
    const currentTick = tl?.current_tick ?? 0;
    const activeBranch = tl?.current_branch ?? "main";

    // 主干 = 当前活跃分支
    const main = rawNodes.filter((n: any) => n.branch === activeBranch).sort((a: any, b: any) => a.tick - b.tick);
    const maxT = Math.max(...rawNodes.map((n: any) => n.tick), currentTick);

    // 分支分组 = 非活跃分支
    const groups: { id: string; nodes: any[]; forkTick: number }[] = [];
    const seen = new Set<string>();
    rawNodes.forEach((n: any) => {
      if (n.branch !== activeBranch && !seen.has(n.branch)) {
        seen.add(n.branch);
        const bn = rawNodes.filter((x: any) => x.branch === n.branch).sort((a: any, b: any) => a.tick - b.tick);
        groups.push({ id: n.branch, nodes: bn, forkTick: bn[0].tick - 1 });
      }
    });

    return {
      trunkNodes: main,
      branchGroups: groups,
      treeH: (maxT + 2) * TICK_GAP + 80,
      svgW: 960,
    };
  }, [tl]);

  if (isLoading) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (!trunkNodes.length) return <p className="text-sm py-24 text-center" style={{ color: "var(--text-2)" }}>暂无场景，先生成一些章节</p>;

  const currentTick = tl?.current_tick ?? 0;
  const cpList = (cps?.checkpoints ?? []) as any[];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>时间线 — 大树主干向上生长，存档是分枝。点击存档可切换节点，历史永久保留。主干越往上越新，根部是最初的起点。</PageHelp>

      <div className="flex-1 overflow-auto" style={{ background: "var(--bg-base)" }}>
        <svg width={svgW} height={treeH} style={{ display: "block", margin: "0 auto" }}>
          <defs>
            <filter id="nodeGlow">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="cpGlow">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* ── Title ── */}
          <text x={TRUNK_X} y={24} fontSize={14} fill="var(--text-2)" textAnchor="middle" fontWeight={600}>
            故事时间线
          </text>

          {/* ── 主干 ── */}
          {trunkNodes.map((n: any, i: number) => {
            const y = treeH - 80 - i * TICK_GAP;
            const nextY = i < trunkNodes.length - 1 ? treeH - 80 - (i + 1) * TICK_GAP : y;
            const thick = Math.max(2, 8 - (i / Math.max(trunkNodes.length - 1, 1)) * 6);
            const opacity = 0.3 + (i / Math.max(trunkNodes.length - 1, 1)) * 0.6;
            const isHead = n.tick === currentTick && i === trunkNodes.length - 1;
            const cpsHere = cpList.filter((c: any) => c.tick === n.tick);
            // 该节点是否有分支从此处分叉
            const forksHere = branchGroups.filter((g) => g.forkTick === n.tick);

            return (
              <g key={n.tick} style={{ cursor: "pointer" }}>
                {/* 主干线段 */}
                <line x1={TRUNK_X} y1={y} x2={TRUNK_X} y2={nextY}
                  stroke={ACTIVE} strokeWidth={thick} strokeLinecap="round" opacity={opacity} />

                {/* ── 分支（回滚后的旧时间线，可点击切回）── */}
                {forksHere.map((bg, bi) => {
                  const side = bi % 2 === 0 ? -1 : 1;
                  const offset = BRANCH_SPREAD + bi * 35;
                  const bx = TRUNK_X + side * offset;
                  const by = y + (bi % 2 === 0 ? -30 : 30);
                  const midX = TRUNK_X + side * offset * 0.5;
                  const midY = (y + by) / 2;
                  return (
                    <g key={bg.id} style={{ cursor: "pointer" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setBranchTarget({ id: bg.id, headTick: bg.nodes[bg.nodes.length - 1]?.tick || 0, backupId: bg.id });
                      }}
                      opacity={0.5}>
                      <path d={`M${TRUNK_X},${y} Q${midX},${midY} ${bx},${by}`}
                        fill="none" stroke="#555" strokeWidth={0.8} strokeDasharray="4,6" />
                      <circle cx={bx} cy={by} r={4} fill="#555" />
                      <text x={bx + (side > 0 ? 8 : -8)} y={by + 3} fontSize={8}
                        fill="#777" textAnchor={side > 0 ? "start" : "end"}>
                        分支 {bg.nodes.length}幕
                      </text>
                      <text x={bx + (side > 0 ? 8 : -8)} y={by + 14} fontSize={7}
                        fill="#666" textAnchor={side > 0 ? "start" : "end"}>
                        点击切换
                      </text>
                    </g>
                  );
                })}

                {/* ── 存档分枝 ── */}
                {cpsHere.map((cp: any, ci: number) => {
                  const side = ci % 2 === 0 ? -1 : 1;
                  const bx = TRUNK_X + side * (BRANCH_SPREAD + ci * 35);
                  const by = y + (ci % 2 === 0 ? -18 : 18);
                  const midX = TRUNK_X + side * BRANCH_SPREAD * 0.5;
                  const midY = (y + by) / 2;
                  const cpColor = cp.created_by === "auto" ? AUTO_CP : MANUAL_CP;
                  const isHovered = hoveredCp === cp.checkpoint_id;

                  return (
                    <g key={cp.checkpoint_id}
                      onMouseEnter={() => setHoveredCp(cp.checkpoint_id)}
                      onMouseLeave={() => setHoveredCp(null)}
                      onClick={(e) => { e.stopPropagation(); setRestoreTarget({ id: cp.checkpoint_id, type: cp.created_by }); }}>
                      <path d={`M${TRUNK_X},${y} Q${midX},${midY} ${bx},${by}`}
                        fill="none" stroke={cpColor}
                        strokeWidth={isHovered ? 2.2 : 1.4} opacity={isHovered ? 1 : 0.7}
                        style={{ transition: "all 0.15s" }} />
                      <circle cx={bx} cy={by} r={NODE_R} fill={cpColor}
                        filter={isHovered ? "url(#cpGlow)" : undefined} opacity={isHovered ? 1 : 0.85} />
                      <text x={bx + (side > 0 ? 12 : -12)} y={by + 4} fontSize={10}
                        fill={cpColor} textAnchor={side > 0 ? "start" : "end"} fontWeight={isHovered ? 600 : 400}>
                        {cp.type === "auto" ? "自动存档" : "手动存档"}
                      </text>
                      {isHovered && (
                        <text x={bx + (side > 0 ? 12 : -12)} y={by + 17} fontSize={9}
                          fill="var(--text-3)" textAnchor={side > 0 ? "start" : "end"}>
                          点击切换
                        </text>
                      )}
                    </g>
                  );
                })}

                {/* ── 主干节点 ── */}
                <circle cx={TRUNK_X} cy={y} r={isHead ? NODE_R + 3 : NODE_R}
                  fill={isHead ? "#ff6b35" : ACTIVE}
                  filter={isHead ? "url(#nodeGlow)" : undefined}
                  opacity={0.85} />
                <text x={TRUNK_X + 16} y={y + 1} fontSize={12} fill="var(--text-2)" fontWeight={isHead ? 700 : 500}>
                  第 {n.tick} 幕{isHead ? " ◀" : ""}
                </text>
                {n.title && (
                  <text x={TRUNK_X + 16} y={y + 15} fontSize={10} fill="var(--text-3)" opacity={0.6}>
                    {n.title.slice(0, 25)}
                  </text>
                )}
              </g>
            );
          })}

          {/* ── 根 ── */}
          {trunkNodes.length > 0 && (
            <>
              <circle cx={TRUNK_X} cy={treeH - 80 - (trunkNodes.length - 1) * TICK_GAP}
                r={12} fill="none" stroke={ACTIVE} strokeWidth={2} opacity={0.5} />
              <text x={TRUNK_X} y={treeH - 40} fontSize={12} fill="var(--text-2)" textAnchor="middle" fontWeight={600}>🌱 根</text>
            </>
          )}
        </svg>
      </div>

      {/* ── 存档切换弹窗 ── */}
      {restoreTarget && (
        <Modal open={!!restoreTarget} onClose={() => setRestoreTarget(null)}>
          <div className="p-5 space-y-3">
            <h3 className="font-semibold text-base" style={{ color: "var(--text-1)" }}>切换节点</h3>
            <p className="text-sm" style={{ color: "var(--text-2)" }}>
              切换到 <b>{restoreTarget.id}</b>？当前进度自动备份，可随时切回。
            </p>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setRestoreTarget(null)}>取消</Button>
              <Button variant="danger" size="sm" onClick={handleRestore} loading={restoreMut.isPending}>确认切换</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── 分支切换弹窗 ── */}
      {branchTarget && (
        <Modal open={!!branchTarget} onClose={() => setBranchTarget(null)}>
          <div className="p-5 space-y-3">
            <h3 className="font-semibold text-base" style={{ color: "var(--text-1)" }}>切换分支（git checkout）</h3>
            <p className="text-sm" style={{ color: "var(--text-2)" }}>
              切换到分支 <b>{branchTarget.id}</b>（{branchTarget.headTick + 1} 幕）
            </p>
            <p className="text-xs" style={{ color: "var(--text-3)" }}>HEAD 将移动到该分支的最新位置，主分支不动。</p>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setBranchTarget(null)}>取消</Button>
              <Button variant="danger" size="sm" onClick={handleBranchSwitch} loading={switchMut.isPending}>确认切换</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
