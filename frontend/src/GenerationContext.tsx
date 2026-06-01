import { createContext, useContext, useRef, useState, useCallback, type ReactNode } from "react";
import type { TickResponse } from "./types/generation";
import { useQueryClient } from "@tanstack/react-query";

const PHASE_LABELS: Record<string, string> = {
  context: "收集上下文", planning: "规划情节", execution: "执行工具",
  writing: "准备写作", generating: "正在生成", evaluation: "评估质量",
  tension: "张力分析", committing: "保存场景", post_commit: "提交后处理",
  memory: "更新记忆", entity_generation: "生成实体",
};

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
  const esRef = useRef<EventSource | null>(null);
  const runCountRef = useRef(0);
  const pendingCountRef = useRef(0);
  const paramsRef = useRef<{ notes?: string; backend?: string; model?: string; finale?: boolean }>({});

  const [session, setSession] = useState<GenerationSession | null>(null);

  const stopAll = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setSession(prev => prev ? { ...prev, running: false, phase: "" } : null);
  }, []);

  const startSSE = useCallback((
    projectId: string,
    count: number,
    params: { notes?: string; backend?: string; model?: string; finale?: boolean } = {},
  ) => {
    esRef.current?.close();
    runCountRef.current = 0;
    pendingCountRef.current = count;
    paramsRef.current = params;

    setSession({ projectId, running: true, text: "", phase: "", result: null });

    const runOne = () => {
      const { notes, backend, model, finale } = paramsRef.current;
      const qs = new URLSearchParams();
      const token = localStorage.getItem("inkforge_token");
      if (token) qs.set("token", token);
      if (notes) qs.set("notes", notes);
      if (backend) qs.set("llm_backend", backend);
      if (model) qs.set("llm_model", model);
      if (finale) qs.set("finale", "true");
      const url = `/api/v1/project/${projectId}/tick/stream${qs.toString() ? "?" + qs : ""}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("phase", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setSession(prev => prev ? { ...prev, phase: PHASE_LABELS[d.name] || d.name } : prev);
      });

      es.addEventListener("tick_complete", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        runCountRef.current++;
        // Play completion chime
        try {
          const ctx = new AudioContext();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.connect(gain); gain.connect(ctx.destination);
          osc.type = "sine";
          osc.frequency.setValueAtTime(880, ctx.currentTime);
          osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.08);
          gain.gain.setValueAtTime(0.3, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
          osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
        } catch { /* audio not supported */ }
        const newText = d.text as string | undefined;
        setSession(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            text: prev.text + (prev.text && newText ? "\n\n---\n\n" : "") + (newText ?? ""),
            result: { success: true, tick: d.tick, scene_id: d.scene_id, scene_file: d.scene_file, word_count: d.word_count, actions_executed: 0 },
          };
        });
        qc.invalidateQueries({ queryKey: ["status", projectId] });
        qc.invalidateQueries({ queryKey: ["scenes", projectId] });
        qc.invalidateQueries({ queryKey: ["read", projectId] });
        es.close();

        if (runCountRef.current < pendingCountRef.current) {
          setTimeout(runOne, 500);
        } else {
          setSession(prev => prev ? { ...prev, running: false, phase: "" } : prev);
        }
      });

      es.addEventListener("tick_error", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setSession(prev => prev ? {
          ...prev,
          text: prev.text + `\n\n[错误] ${d.error}`,
          running: false,
          phase: "",
        } : prev);
        es.close();
      });

      es.onerror = () => {
        es.close();
        setSession(prev => prev ? { ...prev, running: false, phase: "" } : prev);
      };
    };

    runOne();
  }, [qc]);

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
