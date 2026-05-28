import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { ProgressBar } from "../components/ui/ProgressBar";
import { getGoals } from "../api/status";

export function GoalsPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["goals", id], queryFn: () => getGoals(id!), enabled: !!id });
  if (isLoading) return <Spinner />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">目标层级</h1>

      {data.story_goal && (
        <Card className="p-4">
          <h3 className="font-semibold text-indigo-700">故事目标</h3>
          <p className="mt-1">{data.story_goal.description}</p>
          <p className="text-xs text-zinc-400 mt-1">自动浮现于第 {data.story_goal.promoted_at_tick} 幕</p>
        </Card>
      )}

      {data.protagonist_goals && (
        <Card className="p-4">
          <h3 className="font-semibold mb-3">
            {data.protagonist_name || "主角"} 的目标
            {data.protagonist_goals.arc_goal && <span className="ml-2 text-xs text-indigo-600">弧线: {data.protagonist_goals.arc_goal}</span>}
          </h3>
          <div className="space-y-2">
            {data.protagonist_goals.immediate.map((g) => (
              <ProgressBar key={g} value={data.protagonist_goals!.progress[g] ?? 0} label={g} />
            ))}
          </div>
          {data.protagonist_goals.completed.length > 0 && (
            <p className="text-sm text-emerald-600 mt-3">已完成: {data.protagonist_goals.completed.join(", ")}</p>
          )}
          {data.protagonist_goals.abandoned.length > 0 && (
            <p className="text-sm text-zinc-400 mt-1">已放弃: {data.protagonist_goals.abandoned.join(", ")}</p>
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
