import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { getPlotStatus, generateBeats, clearBeats } from "../api/plot";
import type { BeatInfo } from "../types/plot";

const STATUS_CN: Record<string, { label: string; variant: "default" | "success" | "warning" | "info" }> = {
  pending:     { label: "待执行", variant: "default" },
  in_progress: { label: "进行中", variant: "warning" },
  completed:   { label: "已完成", variant: "success" },
  skipped:     { label: "已跳过", variant: "default" },
};

export function PlotPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["plot", id],
    queryFn: () => getPlotStatus(id!),
    enabled: !!id,
  });

  const genMut = useMutation({
    mutationFn: () => generateBeats(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plot", id] });
    },
  });

  const clearMut = useMutation({
    mutationFn: () => clearBeats(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plot", id] });
    },
  });

  if (isLoading) return <Spinner />;
  if (!data) return <p className="text-sm" style={{ color: "var(--text-2)" }}>无法加载情节节拍</p>;

  const stats = [
    { label: "总计", value: data.total_beats },
    { label: "待执行", value: data.pending },
    { label: "进行中", value: data.in_progress },
    { label: "已完成", value: data.completed },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>情节节拍</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => { if (confirm("确认清空所有节拍？")) clearMut.mutate(); }} loading={clearMut.isPending}>清空</Button>
          <Button onClick={() => genMut.mutate()} loading={genMut.isPending}>生成节拍</Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {stats.map(s => (
          <Card key={s.label} className="p-4 text-center">
            <p className="text-2xl font-bold tabular-nums" style={{ color: "var(--text-1)" }}>{s.value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>{s.label}</p>
          </Card>
        ))}
      </div>

      {data.current_arc && (
        <Card className="p-4">
          <p className="text-sm" style={{ color: "var(--text-2)" }}>
            当前弧线：<span style={{ color: "var(--text-1)" }}>{data.current_arc}</span>
            {data.arc_progress != null && `（${Math.round(data.arc_progress * 100)}%）`}
          </p>
        </Card>
      )}

      {(data?.beats?.length ?? 0) > 0 && (
        <div>
          <h3 className="font-semibold text-sm mb-3" style={{ color: "var(--text-1)" }}>
            节拍列表
          </h3>
          <div className="space-y-2">
            {(data?.beats ?? []).map(b => {
              const s = STATUS_CN[b.status] || { label: b.status, variant: "default" as const };
              return (
                <Card key={b.id} className="p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm leading-relaxed" style={{ color: "var(--text-1)" }}>{b.description}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        <span className="text-[11px]" style={{ color: "var(--text-3)" }}>{b.id}</span>
                        {b.characters_involved.length > 0 && (
                          <span className="text-[11px]" style={{ color: "var(--text-2)" }}>
                            角色：{b.characters_involved.join("、")}
                          </span>
                        )}
                        {b.location && (
                          <span className="text-[11px]" style={{ color: "var(--text-2)" }}>地点：{b.location}</span>
                        )}
                        {b.tension_target != null && (
                          <span className="text-[11px]" style={{ color: "var(--text-2)" }}>目标张力：{b.tension_target}/10</span>
                        )}
                      </div>
                    </div>
                    <Badge variant={s.variant}>{s.label}</Badge>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {data.missing_prerequisites?.length > 0 && (
        <div className="p-4 rounded-xl" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderLeft: "3px solid var(--accent)" }}>
          <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-1)" }}>缺失前置条件</p>
          {data.missing_prerequisites.map((m, i) => (
            <p key={i} className="text-xs" style={{ color: "var(--text-2)" }}>
              {m.beat_id} ← 需要 {m.prerequisite}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
