import { Button } from "./ui/Button";
import { Badge } from "./ui/Badge";
import { ThemedSelect } from "./ui/ThemedSelect";
import { ThemedTextarea } from "./ui/ThemedTextarea";
import type { StatusInfo } from "../types/status";
import type { TickResponse } from "../types/generation";
import type { WritingTheme } from "../types/theme";

const BACKENDS = [
  { value: "api",    label: "API" },
  { value: "codex",  label: "Codex CLI" },
  { value: "ollama", label: "Ollama" },
];

const MODELS = [
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "gpt-5.1",      label: "GPT-5.1" },
  { value: "claude-4.5",   label: "Claude 4.5" },
  { value: "qwen3:8b",     label: "Qwen3 8B" },
];

interface Props {
  status: StatusInfo | undefined;
  result: TickResponse | null;
  notes: string;
  backend: string;
  model: string;
  streamMode: boolean;
  running: boolean;
  tickPending: boolean;
  runPending: boolean;
  theme: WritingTheme;
  onNotesChange: (v: string) => void;
  onBackendChange: (v: string) => void;
  onModelChange: (v: string) => void;
  onTick: () => void;
  onRun5: () => void;
  onStartStream: () => void;
  onStopStream: () => void;
}

export function WritingControls({
  status, result, notes, backend, model, streamMode, running,
  tickPending, runPending, theme: t,
  onNotesChange, onBackendChange, onModelChange,
  onTick, onRun5, onStartStream, onStopStream,
}: Props) {
  return (
    <div className="w-64 flex-shrink-0 flex flex-col gap-3">

      {/* Control card */}
      <div
        className="rounded-xl flex flex-col overflow-hidden transition-all duration-300"
        style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}`, boxShadow: t.shadow }}
      >
        <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
          <h3 className="font-semibold text-sm" style={{ color: t.text }}>写作控制台</h3>
          {status && (
            <p className="text-[11px] tabular-nums" style={{ color: t.text3 }}>
              第 {status.current_tick} 幕 · {status.word_count.toLocaleString()} 字
            </p>
          )}
        </div>

        <div className="px-4 pt-3.5 pb-3 space-y-3">
          <ThemedSelect label="LLM 后端" value={backend} onChange={onBackendChange} options={BACKENDS} theme={t} />
          <ThemedSelect label="模型"     value={model}   onChange={onModelChange}   options={MODELS}   theme={t} />
          <ThemedTextarea
            label="场景指导（可选）"
            value={notes}
            onChange={onNotesChange}
            rows={3}
            placeholder="描述本幕想写的内容，例如「两位主角在月光下互诉衷肠」"
            theme={t}
          />
        </div>

        <div className="px-4 pb-4 pt-3 space-y-2 flex-shrink-0" style={{ borderTop: `1px solid ${t.cardBorder}` }}>
          <Button onClick={onTick} loading={tickPending} disabled={running} className="w-full justify-center">
            生成一幕
          </Button>
          <Button variant="ghost" onClick={onRun5} loading={runPending} disabled={running} className="w-full justify-center">
            连续 5 幕
          </Button>
          <div className="pt-1">
            {!streamMode ? (
              <Button variant="ghost" onClick={onStartStream} disabled={running} className="w-full justify-center text-xs">
                SSE 流式输出
              </Button>
            ) : (
              <Button variant="danger" onClick={onStopStream} disabled={!running} className="w-full justify-center text-xs">
                停止流式
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Result card */}
      {result && (
        <div
          className="rounded-xl overflow-hidden animate-slide-up transition-all duration-300"
          style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}`, boxShadow: t.shadow }}
        >
          <div className="px-4 py-3" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
            <h3 className="font-semibold text-[13px]" style={{ color: t.text2 }}>上次结果</h3>
          </div>
          <div className="px-4 py-3 space-y-2">
            {[
              { label: "字数",   value: result.word_count },
              { label: "动作数", value: result.actions_executed },
            ].map((row) => (
              <div key={row.label} className="flex justify-between items-center">
                <span className="text-xs" style={{ color: t.text3 }}>{row.label}</span>
                <span className="text-sm font-semibold tabular-nums" style={{ color: t.text }}>{row.value}</span>
              </div>
            ))}
            {result.tension && (
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: t.text3 }}>张力</span>
                <Badge variant="info">{String(result.tension.level)}/10</Badge>
              </div>
            )}
          </div>
        </div>
      )}

      {!running && !result && (
        <p className="text-[11px] text-center px-3 leading-relaxed" style={{ color: t.text3 }}>
          填写「场景指导」引导 AI 的写作方向。<br />留空则 AI 自行决定本幕内容。
        </p>
      )}
    </div>
  );
}
