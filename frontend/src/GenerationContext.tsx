import { createContext, useContext, useRef, useState, useCallback, type ReactNode } from "react";
import type { TickResponse } from "./types/generation";
import { useQueryClient } from "@tanstack/react-query";

const PHASE_LABELS: Record<string, string> = {
  context: "收集上下文", planning: "规划情节", execution: "执行工具",
  writing: "准备写作", generating: "正在生成", evaluation: "评估质量",
  tension: "张力分析", committing: "保存场景", post_commit: "提交后处理",
  memory: "更新记忆", entity_generation: "生成实体",
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
  startSSE: (projectId: string, count: number, params: { notes?: string; backend?: string; model?: string; finale?: boolean }) => void;
  stopAll: () => void;
}

const GenerationContext = createContext<GenerationContextValue | null>(null);

export function GenerationProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  const runCountRef = useRef(0);
  const pendingCountRef = useRef(0);
  const paramsRef = useRef<{ notes?: string; backend?: string; model?: string; finale?: boolean }>({});

  const [session, setSession] = useState<GenerationSession | null>(null);

  const stopAll = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setSession(prev => prev ? { ...prev, running: false, phase: "" } : null);
  }, []);

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
        return;
      }
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
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
                setTimeout(runOne, 500);
              } else {
                setSession(prev => prev ? { ...prev, running: false, phase: "" } : prev);
              }
            } else if (evType === "tick_error") {
              setSession(prev => prev ? { ...prev, text: prev.text + `\n\n[错误] ${data.error}`, running: false, phase: "" } : prev);
              return;
            }
          } else {
            i++;
          }
        }
      }
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setSession(prev => prev ? { ...prev, running: false, phase: "" } : prev);
      }
    }
  }, [qc]);

  const startSSE = useCallback((
    projectId: string, count: number,
    params: { notes?: string; backend?: string; model?: string; finale?: boolean } = {},
  ) => {
    abortRef.current?.abort();
    runCountRef.current = 0;
    pendingCountRef.current = count;
    paramsRef.current = params;
    setSession({ projectId, running: true, text: "", phase: "", result: null });

    const runOne = () => {
      const { notes, backend, model, finale } = paramsRef.current;
      const token = localStorage.getItem("inkforge_token");
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const bodyParams = new URLSearchParams();
      if (backend) bodyParams.set("llm_backend", backend);
      if (model) bodyParams.set("llm_model", model);
      if (finale) bodyParams.set("finale", "true");

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

    runOne();
  }, [streamSSE]);

  return (
    <GenerationContext.Provider value={{ session, startSSE, stopAll }}>
      {children}
    </GenerationContext.Provider>
  );
}

export function useGeneration() {
  const ctx = useContext(GenerationContext);
  if (!ctx) throw new Error("useGeneration must be inside GenerationProvider");
  return ctx;
}
