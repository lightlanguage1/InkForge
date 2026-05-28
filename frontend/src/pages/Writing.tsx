import { useState, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WritingControls } from "../components/WritingControls";
import { WritingOutput, buildTheme } from "../components/WritingOutput";
import { getStatus } from "../api/status";
import { runTick, runMultiple } from "../api/generation";
import { useTheme } from "../ThemeContext";
import type { TickResponse } from "../types/generation";

export function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["status", id],
    queryFn: () => getStatus(id!),
    enabled: !!id,
  });

  const [notes,      setNotes]      = useState("");
  const [backend,    setBackend]    = useState("api");
  const [model,      setModel]      = useState("deepseek-chat");
  const [text,       setText]       = useState("");
  const [result,     setResult]     = useState<TickResponse | null>(null);
  const [running,    setRunning]    = useState(false);
  const [streamMode, setStreamMode] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const { isDayMode, toggleTheme } = useTheme();
  const theme = buildTheme();

  const tickMut = useMutation({
    mutationFn: () => runTick(id!, { notes, llm_backend: backend, llm_model: model }),
    onSuccess: (data) => {
      setResult(data);
      setRunning(false);
      qc.invalidateQueries({ queryKey: ["status", id] });
      qc.invalidateQueries({ queryKey: ["scenes", id] });
    },
    onError: () => setRunning(false),
  });

  const runMut = useMutation({
    mutationFn: () => runMultiple(id!, 5),
    onSuccess: (data) => {
      const wc = data.results.reduce((s, r) => s + r.word_count, 0);
      setResult({ success: true, tick: 0, scene_id: "", scene_file: "", word_count: wc, actions_executed: data.completed });
      setRunning(false);
      qc.invalidateQueries({ queryKey: ["status", id] });
    },
    onError: () => setRunning(false),
  });

  const handleTick = () => { setRunning(true); setResult(null); setText(""); tickMut.mutate(); };
  const handleRun5 = () => {
    if (confirm("连续生成 5 幕？中途无法中断。")) { setRunning(true); runMut.mutate(); }
  };

  const startStream = useCallback(() => {
    setStreamMode(true); setText(""); setResult(null); setRunning(true);
    const es = new EventSource("/api/v1/project/" + id + "/tick/stream");
    esRef.current = es;
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.text) setText((p) => p + d.text);
        if (d.done) { es.close(); setRunning(false); qc.invalidateQueries({ queryKey: ["status", id] }); }
      } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); setRunning(false); };
  }, [id, qc]);

  const stopStream = useCallback(() => { esRef.current?.close(); setRunning(false); }, []);

  return (
    <div className="flex gap-5 h-[calc(100vh-4rem)] animate-fade-in -m-8 p-6">
        <WritingControls
          status={status}
          result={result}
          notes={notes}
          backend={backend}
          model={model}
          streamMode={streamMode}
          running={running}
          tickPending={tickMut.isPending}
          runPending={runMut.isPending}
          theme={theme}
          onNotesChange={setNotes}
          onBackendChange={setBackend}
          onModelChange={setModel}
          onTick={handleTick}
          onRun5={handleRun5}
          onStartStream={startStream}
          onStopStream={stopStream}
        />
        <WritingOutput
          text={text}
          result={result}
          running={running}
          streamMode={streamMode}
          tickPending={tickMut.isPending}
          isDayMode={isDayMode}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
    </div>
  );
}

