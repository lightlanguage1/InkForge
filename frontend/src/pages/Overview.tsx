import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { getStatus } from "../api/status";
import { ProtagonistPortrait } from "../components/ProtagonistPortrait";

const STATS = [
  { key: "ticks",   label: "总幕数",   accent: "#8b7fd4" },
  { key: "words",   label: "总字数",   accent: "#4daa85" },
  { key: "chars",   label: "角色数",   accent: "#c8975a" },
  { key: "tension", label: "平均张力", accent: "#c8607a" },
];

export function OverviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id });

  if (isLoading) return <Spinner />;
  if (!data) return <p className="text-sm" style={{ color: "var(--text-2)" }}>无法加载项目状态</p>;

  const values: Record<string, string> = {
    ticks:   String(data.current_tick),
    words:   data.word_count.toLocaleString(),
    chars:   String(data.character_count),
    tension: data.avg_tension > 0 ? data.avg_tension.toFixed(1) : "—",
  };

  const hints: Record<string, string> = {
    ticks:   "已生成幕数",
    words:   "中文字符",
    chars:   `${data.location_count} 地点 · ${data.faction_count} 势力`,
    tension: "满分 10",
  };


  return (
    <>
      <style>{`
        @keyframes ovFadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .ov-in { animation: ovFadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both; }
        .ov-cta:hover { background: var(--accent) !important; color: var(--bg-base) !important; }
        .ov-statcard:hover { border-color: var(--accent) !important; transform: translateY(-1px); }
      `}</style>

      <div className="relative" style={{ maxWidth: "700px" }}>


        {/* Header */}
        <div className="ov-in relative z-10 flex items-start justify-between mb-10" style={{ animationDelay: "0ms" }}>
          <div>
            <p className="font-mono text-xs tracking-widest mb-2" style={{ color: "var(--text-3)", letterSpacing: "0.2em" }}>
              故事 · 状态
            </p>
            <h1 className="font-display font-semibold" style={{ fontSize: "1.6rem", color: "var(--text-1)", letterSpacing: "-0.02em", lineHeight: 1.2 }}>
              {data.novel_name}
            </h1>
            <div className="flex items-center flex-wrap mt-2" style={{ gap: "4px" }}>
              {[`第 ${data.current_tick} 幕`, `${data.scene_count} 场景`, `${data.open_loops_count} 线索`, `${data.lore_count} 世界观`].map((item, i) => (
                <span key={i} className="text-xs" style={{ color: "var(--text-3)" }}>
                  {i > 0 && <span style={{ margin: "0 5px", opacity: 0.4 }}>·</span>}
                  {item}
                </span>
              ))}
            </div>
          </div>

          <button
            className="ov-cta font-display flex-shrink-0"
            onClick={() => navigate("writing")}
            style={{
              marginTop: "4px",
              padding: "9px 24px",
              border: "1.5px solid var(--accent)",
              borderRadius: "3px",
              background: "transparent",
              color: "var(--accent)",
              fontSize: "13px",
              fontWeight: 600,
              letterSpacing: "0.06em",
              cursor: "pointer",
              transition: "background 0.18s, color 0.18s",
            }}
          >
            继续写作 →
          </button>
        </div>

        {/* Thin rule */}
        <div className="ov-in relative z-10 mb-8" style={{ animationDelay: "60ms", height: "1px", background: "var(--border)" }} />

        {/* Primary hero stats: 幕数 (large) + 字数 (large), asymmetric */}
        <div className="ov-in relative z-10 mb-8" style={{ animationDelay: "120ms", display: "grid", gridTemplateColumns: "5fr 7fr", gap: "0" }}>
          {/* 幕数 — left, most dominant */}
          <div style={{ paddingRight: "32px", borderRight: "1px solid var(--border)" }}>
            <div
              className="font-mono tabular-nums"
              style={{ fontSize: "80px", fontWeight: 800, lineHeight: 0.9, color: "var(--text-1)", letterSpacing: "-0.04em" }}
            >
              {values.ticks}
            </div>
            <div className="flex items-baseline gap-2 mt-4">
              <span className="font-mono text-xs font-bold tracking-widest" style={{ color: STATS[0].accent }}>幕数</span>
              <span className="text-xs" style={{ color: "var(--text-3)" }}>已生成</span>
            </div>
          </div>

          {/* 字数 — right, secondary dominant */}
          <div style={{ paddingLeft: "32px" }}>
            <div
              className="font-mono tabular-nums"
              style={{ fontSize: "60px", fontWeight: 700, lineHeight: 0.9, color: "var(--text-1)", letterSpacing: "-0.03em", opacity: 0.8 }}
            >
              {values.words}
            </div>
            <div className="flex items-baseline gap-2 mt-4">
              <span className="font-mono text-xs font-bold tracking-widest" style={{ color: STATS[1].accent }}>字数</span>
              <span className="text-xs" style={{ color: "var(--text-3)" }}>中文字符</span>
            </div>
          </div>
        </div>

        {/* Secondary stat cards — 角色数 + 平均张力 */}
        <div className="ov-in relative z-10 mb-6" style={{ animationDelay: "240ms", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
          {(["chars", "tension"] as const).map((key) => {
            const s = STATS.find((x) => x.key === key)!;
            return (
              <div
                key={key}
                className="ov-statcard rounded-lg"
                style={{
                  padding: "16px 20px",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderLeftColor: s.accent,
                  borderLeftWidth: "3px",
                  transition: "border-color 0.2s, transform 0.2s",
                }}
              >
                <div
                  className="font-mono tabular-nums"
                  style={{ fontSize: "36px", fontWeight: 700, lineHeight: 1, color: "var(--text-1)", letterSpacing: "-0.02em" }}
                >
                  {values[key]}
                </div>
                <div className="flex items-baseline gap-2 mt-2">
                  <span className="text-xs font-semibold" style={{ color: s.accent }}>{s.label}</span>
                  <span className="text-xs" style={{ color: "var(--text-3)" }}>{hints[key]}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Tertiary strip */}
        <div
          className="ov-in relative z-10"
          style={{ animationDelay: "360ms", display: "flex", gap: "28px", paddingTop: "18px", borderTop: "1px solid var(--border)" }}
        >
          {[
            { label: "线索", value: data.open_loops_count },
            { label: "场景", value: data.scene_count },
            { label: "世界观", value: data.lore_count },
          ].map((s) => (
            <div key={s.label} className="flex items-baseline gap-1.5">
              <span className="font-mono tabular-nums font-bold" style={{ fontSize: "22px", color: "var(--text-2)", letterSpacing: "-0.02em" }}>
                {s.value}
              </span>
              <span className="text-xs" style={{ color: "var(--text-3)", letterSpacing: "0.06em" }}>{s.label}</span>
            </div>
          ))}
        </div>

        {/* ── 点阵画像 ── */}
        {data.current_tick > 0 && (
          <div
            className="ov-in relative z-10 overflow-hidden rounded-xl"
            style={{
              animationDelay: "420ms",
              marginTop: "24px",
              height: "320px",
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
            }}
          >
            <ProtagonistPortrait
              projectId={id!}
              currentTick={data.current_tick}
            />
          </div>
        )}

        {/* Tip banners */}
        {data.current_tick === 0 && (
          <div
            className="ov-in relative z-10 rounded-lg"
            style={{
              animationDelay: "460ms",
              marginTop: "36px",
              padding: "18px 22px",
              borderLeft: "2px solid var(--accent)",
              background: "rgba(200,151,90,0.05)",
              border: "1px solid rgba(200,151,90,0.15)",
              borderLeftWidth: "2px",
              borderLeftColor: "var(--accent)",
            }}
          >
            <h3 className="text-sm font-semibold mb-1.5" style={{ color: "var(--text-1)" }}>开始你的故事</h3>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
              项目已就绪。点击右上角「继续写作」进入写作界面，AI 会先生成主角和世界观设定，然后为你撰写第一幕。
            </p>
          </div>
        )}

        {data.current_tick > 0 && data.current_tick < 5 && (
          <div
            className="ov-in relative z-10 rounded-lg"
            style={{
              animationDelay: "460ms",
              marginTop: "36px",
              padding: "18px 22px",
              border: "1px solid rgba(90,150,200,0.18)",
              borderLeftWidth: "2px",
              borderLeftColor: "#7ab0d4",
              background: "rgba(90,150,200,0.05)",
            }}
          >
            <h3 className="text-sm font-semibold mb-1.5" style={{ color: "var(--text-1)" }}>
              第 {data.current_tick} 幕 · 故事刚刚起步
            </h3>
            <p className="text-xs leading-relaxed" style={{ color: "var(--text-2)" }}>
              建议连续生成 3–5 幕让 AI 建立角色关系和世界观。在写作界面使用「场景方向指导」可以引导剧情走向。
            </p>
          </div>
        )}

      </div>
    </>
  );
}
