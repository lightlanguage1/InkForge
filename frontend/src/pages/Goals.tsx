import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { ProgressBar } from "../components/ui/ProgressBar";
import { getGoals } from "../api/status";
import { PageHelp } from "../components/PageHelp";

export function GoalsPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["goals", id], queryFn: () => getGoals(id!), enabled: !!id });
  if (isLoading) return <Spinner />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <PageHelp>角色目标 — 查看主角的即时目标、角色弧线目标和故事终极目标。追踪目标完成进度，了解当前叙事驱动力。</PageHelp>
      <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--text-1)" }}>目标层级</h1>

      {data.story_goal && (
        <Card className="p-4">
          <h3 className="font-semibold text-indigo-700">故事目标</h3>
          <p className="mt-1">{data.story_goal.description}</p>
          <p className="text-xs text-zinc-400 mt-1">自动浮现于第 {data.story_goal.promoted_at_tick} 幕</p>
        </Card>
      )}

      {data.protagonist_goals && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3" style={{ color: "var(--text-1)" }}>
            {data.protagonist_name || "主角"} 的目标
            {data.protagonist_goals.arc_goal && (
              <span className="ml-2 text-xs" style={{ color: "var(--accent)" }}>弧线: {data.protagonist_goals.arc_goal}</span>
            )}
          </h3>
          {/* 有进度数据时用进度条，否则纯列表（去重，最近20条） */}
          {Object.keys(data.protagonist_goals.progress).length > 0 ? (
            <div className="space-y-2">
              {data.protagonist_goals.immediate.map((g) => (
                <ProgressBar key={g} value={data.protagonist_goals!.progress[g] ?? 0} label={g} />
              ))}
            </div>
          ) : (
            <ul className="space-y-1.5">
              {[...new Set(data.protagonist_goals.immediate)].slice(-20).reverse().map((g, i) => (
                <li key={i} className="flex items-start gap-2 text-sm" style={{ color: "var(--text-2)" }}>
                  <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full mt-1.5" style={{ background: "var(--accent)", opacity: 0.7 }} />
                  {g}
                </li>
              ))}
            </ul>
          )}
          {data.protagonist_goals.completed.length > 0 && (
            <p className="text-sm mt-3" style={{ color: "var(--success, #4ade80)" }}>已完成: {data.protagonist_goals.completed.join("、")}</p>
          )}
          {data.protagonist_goals.abandoned.length > 0 && (
            <p className="text-sm mt-1" style={{ color: "var(--text-3)" }}>已放弃: {data.protagonist_goals.abandoned.join("、")}</p>
          )}
        </Card>
      )}

      {data.story_goal_loops.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">关联线索</h3>
          <div className="space-y-2">
            {data.story_goal_loops.map((l) => (
              <div key={l.id} className="flex items-center justify-between text-sm">
                <span>{l.description}</span>
                <span className="text-zinc-400">提及 {l.scenes_mentioned} 次</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
