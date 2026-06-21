import { createContext, useContext, useRef, useState, useCallback, type ReactNode } from "react";
import type { TickResponse } from "./types/generation";
import { useQueryClient } from "@tanstack/react-query";

const PHASE_LABELS: Record<string, string> = {
  context: "收集上下文", planning: "规划情节", execution: "执行工具",
  writing: "准备写作", generating: "正在生成", evaluation: "评估质量",
  scoring: "质量打分", polishing: "打磨重写",
  tension: "张力分析", committing: "保存场景", post_commit: "提交后处理",
  memory: "更新记忆", finalizing: "整理收尾", entity_generation: "生成实体",
};
const MAX_URL_LENGTH = 1900; // safe limit for URL (nginx default is ~8KB, but be conservative)

interface GenerationSession {
  projectId: string;
  running: boolean;
  text: string;
  phase: string;
  result: TickResponse | null;
}

interface GenerationContextValue {
  session: GenerationSession | null;
  generatingProjectId: string | null;
  startSSE: (projectId: string, count: number, params: { notes?: string; backend?: string; model?: string; finale?: boolean; quality?: boolean; quality_threshold?: number }) => void;
  stopAll: () => void;
  setGenerating: (projectId: string | null) => void;
}

const GenerationContext = createContext<GenerationContextValue | null>(null);

export function GenerationProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  const runCountRef = useRef(0);
  const pendingCountRef = useRef(0);
  const runOneRef = useRef<(() => void) | null>(null);
  const paramsRef = useRef<{ notes?: string; backend?: string; model?: string; finale?: boolean; quality?: boolean; quality_threshold?: number }>({});
  const streamTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const STREAM_TIMEOUT_MS = 180_000; // 3 分钟无 SSE 事件 → 自动清理

  const [session, setSession] = useState<GenerationSession | null>(null);
  const [generatingProjectId, setGeneratingProjectId] = useState<string | null>(null);

  const endGeneration = useCallback(() => {
    if (streamTimeoutRef.current) { clearTimeout(streamTimeoutRef.current); streamTimeoutRef.current = null; }
    setGeneratingProjectId(null);
    setSession(prev => prev ? { ...prev, running: false, phase: "" } : prev);
  }, []);

  const setGenerating = useCallback((projectId: string | null) => {
    setGeneratingProjectId(projectId);
  }, []);

  const stopAll = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    endGeneration();
  }, [endGeneration]);

  const resetStreamTimeout = useCallback(() => {
    if (streamTimeoutRef.current) clearTimeout(streamTimeoutRef.current);
    streamTimeoutRef.current = setTimeout(() => {
      console.warn("SSE stream timeout — no events for 3 minutes");
      endGeneration();
    }, STREAM_TIMEOUT_MS);
  }, [endGeneration]);

  /** Consume SSE stream from either GET or POST endpoint */
  const streamSSE = useCallback(async (
    url: string, init: RequestInit, projectId: string,
  ) => {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(url, { ...init, signal: ctrl.signal });
      if (!res.ok) {
        const text = await res.text();
        setSession(prev => prev ? { ...prev, text: `[HTTP ${res.status}] ${text}`, running: false, phase: "" } : prev);
        setGeneratingProjectId(null);
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) { endGeneration(); return; }
      const decoder = new TextDecoder();
      let buffer = "";
      resetStreamTimeout();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        let i = 0;
        while (i < lines.length) {
          const line = lines[i];
          if (line.startsWith("event: ") && i + 1 < lines.length && lines[i + 1].startsWith("data: ")) {
            resetStreamTimeout(); // 收到有效事件，刷新超时
            const evType = line.slice(7).trim();
            const data = JSON.parse(lines[i + 1].slice(6));
            i += 2;
            if (evType === "phase") {
              setSession(prev => prev ? { ...prev, phase: PHASE_LABELS[data.name] || data.name } : prev);
            } else if (evType === "tick_complete") {
              runCountRef.current++;
              try {
                const ctx = new AudioContext(); const osc = ctx.createOscillator(); const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination); osc.type = "sine";
                osc.frequency.setValueAtTime(880, ctx.currentTime);
                osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.08);
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
              } catch { /* audio not supported */ }
              const newText = data.text as string | undefined;
              setSession(prev => prev ? {
                ...prev,
                text: prev.text + (prev.text && newText ? "\n\n---\n\n" : "") + (newText ?? ""),
                result: { success: true, tick: data.tick, scene_id: data.scene_id, scene_file: data.scene_file, word_count: data.word_count, actions_executed: 0 },
              } : prev);
              qc.invalidateQueries({ queryKey: ["status", projectId] });
              qc.invalidateQueries({ queryKey: ["scenes", projectId] });
              qc.invalidateQueries({ queryKey: ["read", projectId] });
              if (runCountRef.current < pendingCountRef.current) {
                setTimeout(() => runOneRef.current?.(), 500);
              } else {
                endGeneration();
              }
            } else if (evType === "tick_error") {
              setSession(prev => prev ? { ...prev, text: prev.text + `\n\n[错误] ${data.error}`, running: false, phase: "" } : prev);
              setGeneratingProjectId(null);
              if (streamTimeoutRef.current) { clearTimeout(streamTimeoutRef.current); streamTimeoutRef.current = null; }
              return;
            }
          } else {
            i++;
          }
        }
      }
      // 流自然结束——确保清理状态，防止 UI 卡在"生成中"
      endGeneration();
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        endGeneration();
      }
    }
  }, [qc, endGeneration, resetStreamTimeout]);

  const startSSE = useCallback((
    projectId: string, count: number,
    params: { notes?: string; backend?: string; model?: string; finale?: boolean; quality?: boolean; quality_threshold?: number } = {},
  ) => {
    abortRef.current?.abort();
    runCountRef.current = 0;
    pendingCountRef.current = count;
    paramsRef.current = params;
    setSession({ projectId, running: true, text: "", phase: "", result: null });
    setGeneratingProjectId(projectId);

    runOneRef.current = () => {
      const { notes, backend, model, finale, quality, quality_threshold } = paramsRef.current;
      const token = localStorage.getItem("inkforge_token");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const bodyParams = new URLSearchParams();
      if (backend) bodyParams.set("llm_backend", backend);
      if (model) bodyParams.set("llm_model", model);
      if (finale) bodyParams.set("finale", "true");
      if (quality !== undefined) bodyParams.set("quality", String(quality));
      if (quality_threshold !== undefined) bodyParams.set("quality_threshold", String(quality_threshold));

      // For long notes, use POST; otherwise GET
      const needsPost = notes && encodeURIComponent(notes).length > MAX_URL_LENGTH;

      if (needsPost && notes) {
        const body = JSON.stringify({ notes, ...Object.fromEntries(bodyParams) });
        headers["Content-Type"] = "application/json";
        streamSSE(
          `/api/v1/project/${projectId}/tick/stream`,
          { method: "POST", headers, body },
          projectId,
        );
      } else {
        if (notes) bodyParams.set("notes", notes);
        const qs = bodyParams.toString();
        const url = `/api/v1/project/${projectId}/tick/stream${qs ? "?" + qs : ""}`;
        streamSSE(url, { method: "GET", headers }, projectId);
      }
    };

    runOneRef.current();
  }, [streamSSE]);

  return (
    <GenerationContext.Provider value={{ session, generatingProjectId, startSSE, stopAll, setGenerating }}>
      {children}
    </GenerationContext.Provider>
  );
}

export function useGeneration() {
  const ctx = useContext(GenerationContext);
  if (!ctx) throw new Error("useGeneration must be inside GenerationProvider");
  return ctx;
}
