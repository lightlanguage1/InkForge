import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Layout } from "../components/Layout";
import { Spinner } from "../components/ui/Spinner";
import { ProjectCard } from "../components/ProjectCard";
import { NewProjectModal } from "../components/NewProjectModal";
import { listProjects, resume, createProject } from "../api/projects";
import { listSkills } from "../api/skills";
import type { CreateProjectReq } from "../types/project";

const FEATURE_ITEMS = [
  { icon: "◈", title: "涌现式叙事", desc: "AI 自主演化情节，每幕有机生长" },
  { icon: "◉", title: "实体追踪",   desc: "角色、地点、线索全自动管理" },
  { icon: "✦", title: "多模型支持", desc: "接入 DeepSeek、GPT、Claude 等" },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);

  const { data, isLoading, error } = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const { data: skillsData } = useQuery({ queryKey: ["skills"], queryFn: listSkills, enabled: showNew });

  const resumeMut = useMutation({
    mutationFn: resume,
    onSuccess: (res) => {
      const id = res.project_path.split(/[\\/]/).pop();
      navigate(`/project/${id}`);
    },
    onError: () => alert("未找到最近项目。"),
  });

  const createMut = useMutation({
    mutationFn: (form: CreateProjectReq) => createProject(form),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      const id = res.project_path.split(/[\\/]/).pop() ?? "";
      setShowNew(false);
      navigate(`/project/${id}`);
    },
  });

  const projects = data?.projects ?? [];
  const hasProjects = projects.length > 0;

  return (
    <Layout>
      <div className="min-h-full" style={{ background: "var(--bg-base)", transition: "background 0.3s ease" }}>
        <div className="max-w-5xl mx-auto px-8 py-14">

          {/* Top bar */}
          <div className="flex items-center justify-between mb-16">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: "var(--accent)" }}>
              StoryDaemon
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => resumeMut.mutate()}
                disabled={resumeMut.isPending}
                className="flex items-center gap-1.5 text-[13px] px-3 py-2 rounded-lg transition-all duration-150 disabled:opacity-30"
                style={{ color: "var(--text-2)", border: "1px solid var(--border)" }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.color = "var(--text-1)";
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--accent)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.color = "var(--text-2)";
                  (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                }}
              >
                {resumeMut.isPending
                  ? <span className="w-3.5 h-3.5 border-2 rounded-full animate-spin" style={{ borderColor: "rgba(200,151,90,0.3)", borderTopColor: "rgba(200,151,90,0.6)" }} />
                  : <span className="text-xs opacity-60">↗</span>
                }
                继续上次
              </button>
              <button
                onClick={() => setShowNew(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold transition-all duration-200 hover:-translate-y-px active:scale-[0.98]"
                style={{ background: "var(--accent)", color: "var(--bg-base)" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--accent-lit)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--accent)"; }}
              >
                ＋ 新建项目
              </button>
            </div>
          </div>

          {/* Loading */}
          {isLoading && <div className="flex justify-center py-24"><Spinner /></div>}

          {/* Error */}
          {error && (
            <div className="rounded-2xl p-5 flex items-start gap-3 mb-8" style={{ background: "rgba(180,90,40,0.1)", border: "1px solid rgba(180,90,40,0.25)" }}>
              <span className="text-lg mt-0.5" style={{ color: "#c87a4a" }}>⚠</span>
              <div>
                <p className="font-semibold text-sm" style={{ color: "#e0a07a" }}>无法连接后端服务</p>
                <p className="text-xs mt-1.5" style={{ color: "#9a6040" }}>
                  请先启动后端：
                  <code className="px-1.5 py-0.5 rounded font-mono text-[11px] ml-1" style={{ background: "rgba(180,90,40,0.2)", color: "#c87a4a" }}>
                    novel serve
                  </code>
                </p>
              </div>
            </div>
          )}

          {/* Empty hero */}
          {!isLoading && !error && !hasProjects && (
            <div className="animate-fade-in">
              <div className="mb-12">
                <h1 className="font-display font-bold leading-[1.02] select-none" style={{ fontSize: "clamp(52px, 7.5vw, 78px)", letterSpacing: "-0.025em" }}>
                  <span className="block" style={{ color: "var(--text-1)" }}>开始你的</span>
                  <span className="block italic" style={{ color: "var(--accent)" }}>创作之旅</span>
                </h1>
                <p className="text-[15px] leading-relaxed mt-5 max-w-xs" style={{ color: "var(--text-2)" }}>
                  创建第一个项目，AI 将为你构建角色、世界观，并逐幕生成完整的故事。
                </p>
                <button
                  onClick={() => setShowNew(true)}
                  className="mt-8 inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-[14px] transition-all duration-200 hover:-translate-y-0.5 active:scale-[0.98]"
                  style={{ background: "var(--accent)", color: "var(--bg-base)" }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--accent-lit)"; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "var(--accent)"; }}
                >
                  ＋ 创建第一个项目
                </button>
              </div>
              <div className="mt-14 space-y-3 max-w-xs">
                {FEATURE_ITEMS.map((f) => (
                  <div key={f.title} className="flex items-center gap-4 py-2">
                    <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-[13px]"
                      style={{ background: "rgba(200,151,90,0.1)", color: "var(--accent)" }}>
                      {f.icon}
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold" style={{ color: "var(--text-1)" }}>{f.title}</p>
                      <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-3)" }}>{f.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Projects grid */}
          {!isLoading && hasProjects && (
            <div className="animate-fade-in">
              <h1 className="font-semibold tracking-tight mb-8" style={{ fontSize: "22px", color: "var(--text-1)", letterSpacing: "-0.02em" }}>
                我的项目
                <span className="ml-3 font-mono text-base" style={{ color: "var(--text-3)" }}>{projects.length}</span>
              </h1>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {projects.map((p, idx) => (
                  <div
                    key={p.project_path}
                    className="animate-slide-up"
                    style={{ animationDelay: `${idx * 55}ms` }}
                  >
                    <ProjectCard
                      project={p}
                      onClick={() => navigate(`/project/${p.project_path.split(/[\\/]/).pop()}`)}
                    />
                  </div>
                ))}

                {/* Add new card */}
                <button className="group" onClick={() => setShowNew(true)}>
                  <div
                    className="rounded-2xl min-h-[188px] flex flex-col items-center justify-center gap-3 transition-all duration-200"
                    style={{ border: "1px dashed var(--dashed-border)", background: "transparent" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(200,151,90,0.35)"; (e.currentTarget as HTMLElement).style.background = "rgba(200,151,90,0.04)"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "var(--dashed-border)"; (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                  >
                    <div
                      className="w-10 h-10 rounded-full border-dashed border-2 flex items-center justify-center text-xl font-light transition-colors duration-200"
                      style={{ borderColor: "var(--dashed-border)", color: "var(--dashed-text)" }}
                    >
                      +
                    </div>
                    <p className="text-xs font-medium" style={{ color: "var(--dashed-text)" }}>新建项目</p>
                  </div>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <NewProjectModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onSubmit={(form) => createMut.mutate(form)}
        isLoading={createMut.isPending}
        skills={skillsData?.skills ?? []}
      />
    </Layout>
  );
}
