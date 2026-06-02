import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { WritingControls } from "../components/WritingControls";
import { WritingOutput, buildTheme } from "../components/WritingOutput";
import { getStatus } from "../api/status";
import { listSkills } from "../api/skills";
import { useTheme } from "../ThemeContext";
import { useGeneration } from "../GenerationContext";
import { PageHelp } from "../components/PageHelp";
import type { SkillInfo } from "../types/skill";

export function WritingPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { session, startSSE, stopAll } = useGeneration();
  // Only use session state when it belongs to this project
  const active = session?.projectId === id ? session : null;
  const running = active?.running ?? false;
  const text = active?.text ?? "";
  const phase = active?.phase ?? "";
  const result = active?.result ?? null;

  const { data: status } = useQuery({
    queryKey: ["status", id], queryFn: () => getStatus(id!), enabled: !!id,
  });
  const { data: skillsData } = useQuery({ queryKey: ["skills"], queryFn: listSkills });

  // Page-local UI state only — survives navigation irrelevance
  const [notes, setNotes] = useState("");
  const [backend, setBackend] = useState("api");
  const [model, setModel] = useState("deepseek-chat");

  const { isDayMode, toggleTheme } = useTheme();
  const theme = buildTheme();

  const handleTick = () => startSSE(id!, 1, { notes, backend, model });
  const handleRunN = (n: number) => startSSE(id!, n, { notes, backend, model });
  const handleFinale = () => {
    if (confirm("启动结尾完结模式？智能体将收束所有线索、完成人物弧线，写出故事结局。"))
      startSSE(id!, 1, { notes, backend, model, finale: true });
  };

  const skills: SkillInfo[] = skillsData?.skills ?? [];

  return (
    <div className="animate-fade-in">
      <PageHelp>写作工作台 — 控制 AI 生成新章节。左侧设置生成数量、添加指导笔记、切换模型，右侧查看生成过程和结果。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-5 h-[calc(100vh-4rem)] md:-m-8 mt-3 p-4 md:p-6">
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
        activeSkills={[]}
        skillPending={false}
        onNotesChange={setNotes}
        onBackendChange={setBackend}
        onModelChange={setModel}
        onSkillToggle={() => {}}
        onTick={handleTick}
        onRunN={handleRunN}
        onFinale={handleFinale}
        onStartStream={() => startSSE(id!, 1, { notes, backend, model })}
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
    </div>
  );
}
