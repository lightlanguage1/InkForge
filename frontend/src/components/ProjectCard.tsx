import type { ProjectInfo } from "../types/project";

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
}

export function ProjectCard({ project, onClick, onDelete }: Props) {
  const name = project.novel_name || project.project_path.split(/[\\/]/).pop() || "?";
  const pid  = (project.project_path || "").split(/[\\/]/).pop() ?? "";
  const tick = project.current_tick ?? 0;
  const [gradient, accentColor, shadow] = resolveConfig(name);

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (window.confirm(`确认删除项目「${name}」？\n\n此操作不可恢复，项目文件将被永久删除。`)) {
      onDelete(pid);
    }
  }

  return (
    <div className="relative group text-left w-full">
      {/* Delete button — visible on card hover */}
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full flex items-center justify-center
                   opacity-0 group-hover:opacity-100 transition-opacity duration-150"
        style={{
          background: "rgba(200,80,80,0.75)",
          color: "#fff",
          fontSize: "13px",
          lineHeight: 1,
          backdropFilter: "blur(4px)",
        }}
        title="删除项目"
      >
        ✕
      </button>

      <button className="text-left w-full" onClick={onClick}>
        <div
          className={`bg-gradient-to-br ${gradient} rounded-2xl overflow-hidden hover:-translate-y-0.5 transition-all duration-300`}
          style={{
            boxShadow: `0 8px 32px ${shadow}, 0 1px 4px rgba(0,0,0,0.4)`,
            border: "1px solid rgba(240,236,226,0.06)",
          }}
        >
          <div className="relative p-5 pt-6 min-h-[188px] flex flex-col justify-between">
            {/* Large ghost initial */}
            <span
              className="absolute right-3 top-0 text-[96px] font-black leading-none select-none pointer-events-none"
              style={{ color: accentColor, opacity: 0.08 }}
            >
              {name[0]}
            </span>

            <div className="relative">
              <span
                className="inline-block text-[10px] font-medium rounded-full px-2.5 py-0.5"
                style={{ background: "rgba(240,236,226,0.08)", color: "rgba(240,236,226,0.5)" }}
              >
                {tick > 0 ? `第 ${tick} 幕` : "未开始"}
              </span>
            </div>

            <div className="relative mt-6">
              <h3 className="font-semibold text-[15px] leading-tight truncate text-parchment">{name}</h3>
              <p
                className="text-[11px] font-mono mt-0.5 truncate"
                style={{ color: "rgba(240,236,226,0.25)" }}
              >
                {pid}
              </p>
              {tick > 0 && (
                <p
                  className="text-[10px] mt-3.5 tabular-nums font-mono"
                  style={{ color: "rgba(240,236,226,0.25)" }}
                >
                  已生成 {tick} 幕
                </p>
              )}
            </div>
          </div>
        </div>
      </button>
    </div>
  );
}
