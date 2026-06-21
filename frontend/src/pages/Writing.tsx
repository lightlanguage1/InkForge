import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { WritingControls } from "../components/WritingControls";
import { WritingOutput, buildTheme } from "../components/WritingOutput";
import { getStatus } from "../api/status";
import { listSkills } from "../api/skills";
import { resetProject } from "../api/entities";
import { runMultiple } from "../api/generation";
import { useTheme } from "../ThemeContext";
import { useGeneration } from "../GenerationContext";
import { PageHelp } from "../components/PageHelp";
import { ImportModal } from "../components/ImportModal";
import type { SkillInfo } from "../types/skill";

export function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { session, startSSE, stopAll, setGenerating } = useGeneration();
  const active = session?.projectId === id ? session : null;

  const batchMut = useMutation({
    mutationFn: (n: number) => runMultiple(id!, n),
    onMutate: () => { setGenerating(id!); },
    onSuccess: (data) => {
      setGenerating(null);
      qc.invalidateQueries({ queryKey: ["status", id] });
      qc.invalidateQueries({ queryKey: ["scenes", id] });
      qc.invalidateQueries({ queryKey: ["read", id] });
      qc.invalidateQueries({ queryKey: ["timeline", id] });
    },
    onError: () => { setGenerating(null); },
  });
  const running = active?.running ?? false;
  const text = active?.text ?? "";
  const phase = active?.phase ?? "";
  const result = active?.result ?? null;

  const { data: status } = useQuery({ queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id });
  const { data: skillsData } = useQuery({ queryKey: ["skills"], queryFn: listSkills });

  const [notes, setNotes] = useState("");
  const [backend, setBackend] = useState("api");
  const [model, setModel] = useState("deepseek-chat");
  const [showImport, setShowImport] = useState(false);
  const [qualityEnabled, setQualityEnabled] = useState(true);
  const [qualityThreshold, setQualityThreshold] = useState(95);

  const { isDayMode, toggleTheme } = useTheme();
  const theme = buildTheme();

  const handleTick = () => startSSE(id!, 1, { notes, backend, model, quality: qualityEnabled, quality_threshold: qualityThreshold });
  const handleRunN = (n: number) => batchMut.mutate(n);
  const handleFinale = () => {
    if (confirm("启动结尾完结模式？智能体将收束所有线索、完成人物弧线，写出故事结局。"))
      startSSE(id!, 1, { notes, backend, model, finale: true, quality: qualityEnabled, quality_threshold: qualityThreshold });
  };
  const skills: SkillInfo[] = skillsData?.skills ?? [];

  return (
    <div className="animate-fade-in">
      <PageHelp>写作工作台 — 控制 AI 生成新章节。左侧设置生成数量、添加指导笔记、切换模型，右侧查看生成过程和结果。点击「重置进度」清空所有场景从头开始。</PageHelp>

      <div className="flex items-center gap-3 mb-3">
        <span className="text-xs" style={{ color: "var(--text-3)" }}>不满意当前进度？可以清空场景重新开始 —</span>
        <button onClick={() => { setShowImport(true); }} disabled={running}
          className="text-xs px-3 py-1 rounded-lg font-medium transition-all border-0 cursor-pointer"
          style={{ background: "rgba(77,170,133,0.12)", color: "#4daa85", border: "1px solid rgba(77,170,133,0.35)" }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(77,170,133,0.22)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "rgba(77,170,133,0.12)"; }}>
          导入设定
        </button>
        <button onClick={() => {
          if (!confirm("确定重置项目进度？\n\n将删除所有场景章节和角色动态数据，保留故事基础设定和角色身份。\n此操作不可撤销。")) return;
          resetProject(id!).then(() => { qc.invalidateQueries(); alert("项目已重置，保留故事设定和角色。可以重新开始了。"); })
            .catch(err => alert(`重置失败: ${err?.message ?? err}`));
        }} disabled={running}
          className="text-xs px-3 py-1 rounded-lg font-medium transition-all border-0 cursor-pointer"
          style={{ background: "rgba(220,80,60,0.12)", color: "#e8948c", border: "1px solid rgba(220,80,60,0.35)" }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(220,80,60,0.22)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "rgba(220,80,60,0.12)"; }}>
          ⚠ 重置进度
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-4 md:gap-5 h-[calc(100vh-4rem)] md:-mx-8 mt-3 p-4 md:p-6"
        style={{ background: "var(--bg-base)" }}>
        <WritingControls
          status={status} result={result}
          notes={notes} backend={backend} model={model}
          streamMode={false} running={running || batchMut.isPending}
          tickPending={false} runPending={batchMut.isPending}
          theme={theme} skills={skills} activeSkills={[]} skillPending={false}
          qualityEnabled={qualityEnabled}
          qualityThreshold={qualityThreshold}
          onNotesChange={setNotes} onBackendChange={setBackend}
          onModelChange={setModel} onSkillToggle={() => {}}
          onQualityToggle={() => setQualityEnabled(v => !v)}
          onQualityThresholdChange={setQualityThreshold}
          onTick={handleTick} onRunN={handleRunN} onFinale={handleFinale}
          onStartStream={() => startSSE(id!, 1, { notes, backend, model, quality: qualityEnabled, quality_threshold: qualityThreshold })}
          onStopStream={stopAll}
        />
        {batchMut.data && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl shadow-2xl text-sm"
            style={{ background: "var(--accent)", color: "var(--bg-base)" }}>
            ✅ 连续生成完成：{batchMut.data.completed}/{batchMut.data.results.length} 幕
            （{batchMut.data.results.reduce((s: number, r: any) => s + (r.word_count || 0), 0).toLocaleString()} 字）
          </div>
        )}
        <WritingOutput
          text={text} result={result} running={running}
          streamMode={running} tickPending={false}
          isDayMode={isDayMode} theme={theme}
          onToggleTheme={toggleTheme} phase={phase}
        />
      </div>

      <ImportModal open={showImport} projectId={id!} onClose={() => setShowImport(false)} onImported={() => qc.invalidateQueries()} />
    </div>
  );
}
