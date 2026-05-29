import { useState, useRef, useCallback, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WritingControls } from "../components/WritingControls";
import { WritingOutput, buildTheme } from "../components/WritingOutput";
import { getStatus } from "../api/status";
import { listSkills, applySkills } from "../api/skills";
import { useTheme } from "../ThemeContext";
import type { TickResponse } from "../types/generation";
import type { SkillInfo } from "../types/skill";

type Phase = { name: string; tick: number };

const PHASE_LABELS: Record<string, string> = {
  context: "收集上下文", planning: "规划情节", execution: "执行工具",
  writing: "准备写作", generating: "正在生成", evaluation: "评估质量",
  tension: "张力分析", committing: "保存场景", post_commit: "提交后处理",
  memory: "更新记忆", entity_generation: "生成实体",
};

export function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const runCount = useRef(0);

  const { data: status } = useQuery({
    queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id,
  });
  const { data: skillsData } = useQuery({
    queryKey: ["skills"], queryFn: listSkills,
  });

  const [notes, setNotes] = useState("");
  const [backend, setBackend] = useState("api");
  const [model, setModel] = useState("deepseek-chat");
  const [text, setText] = useState("");
  const [phase, setPhase] = useState("");
  const [result, setResult] = useState<TickResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [activeSkills, setActiveSkills] = useState<string[]>([]);

  const notesRef = useRef(notes);
  const backendRef = useRef(backend);
  const modelRef = useRef(model);
  notesRef.current = notes;
  backendRef.current = backend;
  modelRef.current = model;

  const { isDayMode, toggleTheme } = useTheme();
  const theme = buildTheme();

  const skillMut = useMutation({
    mutationFn: (skillIds: string[]) => applySkills({ project_path: id!, skill_ids: skillIds, mode: "reference" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["status", id] }),
  });

  const startSSE = useCallback((count: number) => {
    setRunning(true); setResult(null); setText(""); setPhase("");
    runCount.current = 0;

    const runOne = () => {
      const n = notesRef.current;
      const be = backendRef.current;
      const mo = modelRef.current;
      const params = new URLSearchParams();
      if (n) params.set("notes", n);
      if (be) params.set("llm_backend", be);
      if (mo) params.set("llm_model", mo);
      const qs = params.toString();
      const es = new EventSource(`/api/v1/project/${id}/tick/stream${qs ? "?" + qs : ""}`);
      esRef.current = es;

      es.addEventListener("phase", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setPhase(PHASE_LABELS[d.name] || d.name);
      });

      es.addEventListener("tick_complete", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        runCount.current++;
        if (d.text) setText(prev => prev + (prev ? "\n\n---\n\n" : "") + d.text);
        qc.invalidateQueries({ queryKey: ["status", id] });
        qc.invalidateQueries({ queryKey: ["scenes", id] });
        qc.invalidateQueries({ queryKey: ["read", id] });

        setResult({ success: true, tick: d.tick, scene_id: d.scene_id, scene_file: d.scene_file, word_count: d.word_count, actions_executed: 0 });
        es.close();

        if (runCount.current < count) {
          setTimeout(runOne, 500);
        } else {
          setRunning(false); setPhase("");
        }
      });

      es.addEventListener("tick_error", (e: MessageEvent) => {
        const d = JSON.parse(e.data);
        setText(prev => prev + `\n\n[错误] ${d.error}`);
        es.close();
        setRunning(false);
      });

      es.onerror = () => { es.close(); setRunning(false); };
    };

    runOne();
  }, [id, qc]);

  const handleTick = () => startSSE(1);
  const handleRun5 = () => {
    if (confirm("连续生成 5 幕？可以随时刷新页面中断。")) startSSE(5);
  };

  const stopAll = useCallback(() => {
    esRef.current?.close();
    setRunning(false);
    setPhase("");
  }, []);

  const handleSkillToggle = (skillId: string) => {
    setActiveSkills(prev => {
      const next = prev.includes(skillId) ? prev.filter(s => s !== skillId) : [...prev, skillId];
      if (next.length > 0) setTimeout(() => skillMut.mutate(next), 0);
      return next;
    });
  };

  const skills: SkillInfo[] = skillsData?.skills ?? [];

  // 页面加载时如果项目正在生成中，自动重连 SSE
  const [reconnected, setReconnected] = useState(false);
  useEffect(() => {
    if (status?.generating && !reconnected && !running) {
      setReconnected(true);
      startSSE(1);
    }
  }, [status?.generating]);

  return (
    <div className="flex gap-5 h-[calc(100vh-4rem)] animate-fade-in -m-8 p-6">
        <WritingControls
          status={status}
          result={result}
          notes={notes}
          backend={backend}
          model={model}
          streamMode={false}
          running={running}
          tickPending={false}
          runPending={false}
          theme={theme}
          skills={skills}
          activeSkills={activeSkills}
          skillPending={skillMut.isPending}
          onNotesChange={setNotes}
          onBackendChange={setBackend}
          onModelChange={setModel}
          onSkillToggle={handleSkillToggle}
          onTick={handleTick}
          onRun5={handleRun5}
          onStartStream={() => startSSE(1)}
          onStopStream={stopAll}
        />
        <WritingOutput
          text={text}
          result={result}
          running={running}
          streamMode={running}
          tickPending={false}
          isDayMode={isDayMode}
          theme={theme}
          onToggleTheme={toggleTheme}
          phase={phase}
        />
    </div>
  );
}
