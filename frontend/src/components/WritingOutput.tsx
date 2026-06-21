import { Badge } from "./ui/Badge";
import type { TickResponse } from "../types/generation";
import type { WritingTheme } from "../types/theme";

export type { WritingTheme };

export function buildTheme(): WritingTheme {
  return {
    cardBg:     "var(--bg-surface)",
    cardBorder: "var(--border)",
    shadow:     "var(--shadow)",
    text:       "var(--text-1)",
    text2:      "var(--text-2)",
    text3:      "var(--text-3)",
    accent:     "var(--accent)",
    outputBg:   "var(--bg-base)",
    preBg:      "var(--pre-bg)",
  };
}


/* ── Component ──────────────────────────────────────── */
interface Props {
  text: string;
  result: TickResponse | null;
  running: boolean;
  streamMode: boolean;
  tickPending: boolean;
  isDayMode: boolean;
  phase?: string;
  theme: WritingTheme;
  onToggleTheme: () => void;
}

export function WritingOutput({ text, result, running, streamMode, tickPending, phase, theme }: Props) {
  const t = theme;
  return (
    <div
      className="flex-1 flex flex-col rounded-xl overflow-hidden transition-all duration-300"
      style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}`, boxShadow: t.shadow }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3 flex-shrink-0 transition-colors duration-300"
        style={{ borderBottom: `1px solid ${t.cardBorder}` }}
      >
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-[13px] transition-colors duration-300" style={{ color: t.text2 }}>输出</h3>
          {phase && (
            <span className="text-[11px] px-2 py-0.5 rounded-full animate-pulse"
              style={{ background: "var(--accent)", color: "var(--bg-base)" }}>
              {phase}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {running && (
            <span className="flex items-center gap-1.5 text-[11px] font-medium transition-colors duration-300" style={{ color: t.accent }}>
              <span
                className="w-3 h-3 rounded-full border-2 animate-spin inline-block"
                style={{ borderColor: `${t.accent}30`, borderTopColor: t.accent }}
              />
              生成中
            </span>
          )}
          {!running && result && <Badge variant="success">完成</Badge>}
        </div>
      </div>

      {/* Body */}
      <div
        className="flex-1 overflow-auto p-5 transition-colors duration-300"
        style={{ background: t.outputBg }}
      >
        {/* Stream / completed text */}
        {text ? (
          <pre
            className="text-sm whitespace-pre-wrap font-sans leading-[1.9] transition-colors duration-300"
            style={{ color: t.text }}
          >
            {text}
          </pre>

        ) : running ? (
          /* Generating — show current pipeline phase */
          <div className="flex flex-col items-center justify-center h-full gap-5 text-center">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-xl animate-pulse transition-all duration-300"
              style={{ background: `${t.accent}22`, color: t.accent, border: `1px solid ${t.accent}33` }}
            >
              ✦
            </div>
            <div>
              <p className="text-sm font-medium transition-colors duration-300" style={{ color: t.text2 }}>
                {phase ? `管线中：${phase}` : "AI 正在创作中..."}
              </p>
              <p className="text-xs mt-1 transition-colors duration-300" style={{ color: t.text3 }}>
                {phase ? "请稍候，当前阶段完成后自动进入下一步" : "请稍候"}
              </p>
            </div>
          </div>

        ) : result ? (
          /* Completed — show result summary if no scene text */
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-xl transition-all duration-300"
              style={{ background: "rgba(77,170,133,0.12)", color: "#4daa85", border: "1px solid rgba(77,170,133,0.2)" }}
            >
              ✦
            </div>
            <div>
              <p className="text-sm font-semibold transition-colors duration-300" style={{ color: t.text }}>
                本幕写作完成
              </p>
              <p className="text-xs mt-1.5 tabular-nums transition-colors duration-300" style={{ color: t.text2 }}>
                {result.word_count} 字 · {result.actions_executed} 个动作
                {result.tension ? ` · 张力 ${result.tension.level}/10` : ""}
                {result.quality_score != null ? ` · 质量 ${result.quality_score}分` : ""}
                {result.polish_rounds != null ? ` (${result.polish_rounds}轮打磨)` : ""}
              </p>
            </div>
          </div>

        ) : (
          /* Idle */
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mb-4 transition-all duration-300"
              style={{ background: `${t.accent}12`, border: `1px solid ${t.accent}22`, color: t.accent }}
            >
              ✦
            </div>
            <h3 className="text-sm font-semibold mb-2 transition-colors duration-300" style={{ color: t.text2 }}>
              准备开始写作
            </h3>
            <p className="text-xs max-w-[220px] leading-relaxed transition-colors duration-300" style={{ color: t.text3 }}>
              点击左侧「生成一幕」让 AI 创作下一个场景。首次生成时会先创建主角和世界观。
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
