import { useState, useRef } from "react";
import type { ProjectInfo } from "../types/project";
import { getCoverUrl, uploadCover, removeCover } from "../api/projects";
import { useGeneration } from "../GenerationContext";

/* Dark-tinted gradient configs — [bgGradient, accentColor, shadowColor] */
const CARD_CONFIGS: [string, string, string][] = [
  ["from-[#1a1235] to-[#0e0c22]", "#8b7fd4", "rgba(99,80,200,0.22)"],
  ["from-[#0c1d35] to-[#080f22]", "#5a96c8", "rgba(59,110,180,0.22)"],
  ["from-[#0a2218] to-[#061510]", "#4daa85", "rgba(29,150,100,0.22)"],
  ["from-[#2a1408] to-[#1a0c05]", "#c87a4a", "rgba(180,90,40,0.22)"],
  ["from-[#280d1a] to-[#180810]", "#c85a8a", "rgba(180,60,110,0.22)"],
  ["from-[#281e08] to-[#181205]", "#c8a04a", "rgba(200,140,40,0.22)"],
];

function resolveConfig(name: string): [string, string, string] {
  return CARD_CONFIGS[(name.codePointAt(0) ?? 0) % CARD_CONFIGS.length];
}

interface Props {
  project: ProjectInfo;
  onClick: () => void;
  onDelete: (projectId: string) => void;
  onCoverChange?: () => void;
}

export function ProjectCard({ project, onClick, onDelete, onCoverChange }: Props) {
  const name = project.novel_name || project.project_path.split(/[\\/]/).pop() || "?";
  const pid  = (project.project_path || "").split(/[\\/]/).pop() ?? "";
  const tick = project.current_tick ?? 0;
  const { generatingProjectId } = useGeneration();
  const isGenerating = generatingProjectId === pid;
  const [gradient, accentColor, shadow] = resolveConfig(name);
  const [hasCover, setHasCover] = useState(project.has_cover ?? false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const coverBust = useRef(Date.now());

  const coverUrl = hasCover && pid ? getCoverUrl(pid, coverBust.current) : null;

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (window.confirm(`确认删除项目「${name}」？\n\n此操作不可恢复，项目文件将被永久删除。`)) {
      onDelete(pid);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !pid) return;
    e.stopPropagation();
    setUploading(true);
    try {
      await uploadCover(pid, file);
      coverBust.current = Date.now();
      setHasCover(true);
      onCoverChange?.();
    } catch { /* silent */ }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  function handleCoverClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (hasCover) {
      // 点击已有封面 → 更换
      fileRef.current?.click();
    } else {
      // 无封面 → 选择上传
      fileRef.current?.click();
    }
  }

  return (
    <div className="relative group text-left w-full">
      <input ref={fileRef} type="file" accept="image/*" onChange={handleUpload} style={{ display: "none" }} />

      {/* Delete button */}
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full flex items-center justify-center
                   opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        style={{ background: "rgba(200,80,80,0.75)", color: "#fff", fontSize: "13px", lineHeight: 1, backdropFilter: "blur(4px)" }}
        title="删除项目">✕</button>

      {/* Cover change button */}
      <button
        onClick={handleCoverClick}
        className="absolute top-3 right-12 z-10 px-2 py-1 rounded-lg flex items-center gap-1
                   opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        style={{ background: "rgba(0,0,0,0.5)", color: "rgba(255,255,255,0.8)", fontSize: "11px", backdropFilter: "blur(4px)" }}
        title={hasCover ? "更换封面" : "设置封面"}>
        {uploading ? "…" : hasCover ? "🖼 换封面" : "🖼 加封面"}
      </button>

      <button className="text-left w-full" onClick={onClick}>
        <div
          className="rounded-2xl overflow-hidden hover:-translate-y-0.5 transition-all duration-300"
          style={{ boxShadow: `0 8px 32px ${shadow}, 0 1px 4px rgba(0,0,0,0.4)`, border: "1px solid rgba(240,236,226,0.06)" }}>
          {/* Cover image area */}
          <div className="relative w-full h-32 overflow-hidden"
            style={{ background: hasCover ? "#111" : `linear-gradient(135deg, var(--bg-surface), var(--bg-base))` }}>
            {hasCover && coverUrl ? (
              <img src={coverUrl} alt={name} className="w-full h-full object-cover"
                onError={() => setHasCover(false)} />
            ) : (
              <span className="absolute right-3 top-0 text-[96px] font-black leading-none select-none pointer-events-none"
                style={{ color: accentColor, opacity: 0.15 }}>{name[0]}</span>
            )}
            {uploading && (
              <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.5)" }}>
                <span className="text-xs" style={{ color: "var(--accent)" }}>上传中…</span>
              </div>
            )}
            {/* overlay gradient at bottom */}
            <div className="absolute inset-x-0 bottom-0 h-16 pointer-events-none"
              style={{ background: `linear-gradient(transparent, ${hasCover ? 'rgba(0,0,0,0.7)' : 'transparent'})` }} />
            {/* tick badge */}
            <span className="absolute top-3 left-3 text-[10px] font-medium rounded-full px-2.5 py-0.5 z-10 flex items-center gap-1.5"
              style={{ background: isGenerating ? "rgba(var(--accent-rgb, 99,80,200), 0.5)" : "rgba(0,0,0,0.45)", color: "rgba(240,236,226,0.85)", backdropFilter: "blur(4px)" }}>
              {isGenerating ? (
                <><span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--accent)" }} />生成中…</>
              ) : tick > 0 ? `第 ${tick} 幕` : "未开始"}
            </span>
          </div>

          <div className={`bg-gradient-to-br ${gradient} p-5`}>
            <h3 className="font-semibold text-[15px] leading-tight truncate text-parchment">{name}</h3>
            <p className="text-[11px] font-mono mt-0.5 truncate" style={{ color: "rgba(240,236,226,0.25)" }}>{pid}</p>
            {tick > 0 && (
              <p className="text-[10px] mt-3.5 tabular-nums font-mono" style={{ color: "rgba(240,236,226,0.25)" }}>
                已生成 {tick} 幕
              </p>
            )}
          </div>
        </div>
      </button>
    </div>
  );
}
