import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { getStatus } from "../api/status";

const STATS = [
  { key: "ticks",   label: "总幕数",   icon: "◈", accent: "#8b7fd4", shadow: "rgba(99,80,200,0.15)" },
  { key: "words",   label: "总字数",   icon: "◉", accent: "#4daa85", shadow: "rgba(29,150,100,0.15)" },
  { key: "chars",   label: "角色数",   icon: "◎", accent: "#c8975a", shadow: "rgba(200,151,90,0.15)" },
  { key: "tension", label: "平均张力", icon: "◇", accent: "#c8607a", shadow: "rgba(200,80,100,0.15)" },
];

export function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id });

  if (isLoading) return <Spinner />;
  if (!data) return <p className="text-sm" style={{ color: "var(--text-2)" }}>无法加载项目状态</p>;

  const values: Record<string, string | number> = {
    ticks:   data.current_tick,
    words:   data.word_count.toLocaleString(),
    chars:   data.character_count,
    tension: data.avg_tension > 0 ? data.avg_tension.toFixed(1) : "—",
  };
  const hints: Record<string, string> = {
    ticks:   "已生成幕数",
    words:   "中文字符",
    chars:   `${data.location_count} 地点 · ${data.faction_count} 势力`,
    tension: "满分 10",
  };

  return (
    <div className="animate-fade-in max-w-3xl">

      {/* Page header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-display font-semibold tracking-tight" style={{ fontSize: "1.625rem", color: "var(--text-1)" }}>
            {data.novel_name}
          </h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {[
              `第 ${data.current_tick} 幕`,
              `${data.scene_count} 场景`,
              `${data.open_loops_count} 线索`,
              `${data.lore_count} 世界观条目`,
            ].map((item, i) => (
              <span key={i} className="flex items-center gap-2">
                {i > 0 && <span className="text-xs" style={{ color: "var(--text-3)" }}>·</span>}
                <span className="text-xs" style={{ color: "var(--text-2)" }}>{item}</span>
              </span>
            ))}
          </div>
        </div>
        <Button onClick={() => navigate("writing")} size="md" className="flex-shrink-0 mt-1">
          继续写作 →
        </Button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {STATS.map((s) => (
          <div
            key={s.key}
            className="rounded-xl p-4 transition-all duration-300"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderLeftColor: s.accent,
              borderLeftWidth: "3px",
              boxShadow: `0 2px 8px ${s.shadow}`,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-3)" }}>
                {s.label}
              </p>
              <span className="text-base" style={{ color: s.accent }}>{s.icon}</span>
            </div>
            <p className="text-2xl font-bold tabular-nums leading-none font-mono" style={{ color: "var(--text-1)" }}>
              {values[s.key]}
            </p>
            <p className="text-[11px] mt-1.5" style={{ color: "var(--text-3)" }}>{hints[s.key]}</p>
          </div>
        ))}
      </div>

      {/* Secondary stats row */}
      <div className="grid grid-cols-3 gap-3 mb-8">
        {[
          { label: "线索数", value: data.open_loops_count, hint: "待推进" },
          { label: "场景数", value: data.scene_count, hint: "全幕" },
          { label: "世界观", value: data.lore_count, hint: "条目" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-xl px-4 py-3 text-center transition-all duration-300"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          >
            <p className="text-xl font-bold tabular-nums font-mono" style={{ color: "var(--text-1)" }}>{s.value}</p>
            <p className="text-[11px] font-medium mt-0.5" style={{ color: "var(--text-2)" }}>{s.label}</p>
            <p className="text-[10px] mt-0.5" style={{ color: "var(--text-3)" }}>{s.hint}</p>
          </div>
        ))}
      </div>

      {/* Tip banners */}
      {data.current_tick === 0 && (
        <div className="rounded-xl p-5 animate-fade-in" style={{ background: "rgba(200,151,90,0.07)", border: "1px solid rgba(200,151,90,0.18)" }}>
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0 font-display"
              style={{ background: "rgba(200,151,90,0.15)", color: "var(--accent)" }}>
              ◈
            </div>
            <div>
              <h3 className="font-semibold text-sm mb-1" style={{ color: "var(--text-1)" }}>开始你的故事</h3>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
                项目已就绪。点击右上角「继续写作」进入写作界面，AI 会先生成主角和世界观设定，然后为你撰写第一幕。
              </p>
            </div>
          </div>
        </div>
      )}

      {data.current_tick > 0 && data.current_tick < 5 && (
        <div className="rounded-xl p-5 animate-fade-in" style={{ background: "rgba(90,150,200,0.07)", border: "1px solid rgba(90,150,200,0.18)" }}>
          <div className="flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0"
              style={{ background: "rgba(90,150,200,0.12)", color: "#7ab0d4" }}>
              ◎
            </div>
            <div>
              <h3 className="font-semibold text-sm mb-1" style={{ color: "var(--text-1)" }}>第 {data.current_tick} 幕 · 故事刚刚起步</h3>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
                建议连续生成 3–5 幕让 AI 建立角色关系和世界观。在写作界面使用「场景方向指导」可以引导剧情走向。
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
