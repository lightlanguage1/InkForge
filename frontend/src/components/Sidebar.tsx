import { NavLink, useParams } from "react-router-dom";
import { ThemeToggleBtn } from "./Layout";
import { useTheme } from "../ThemeContext";

const GROUPS = [
  {
    label: "核心",
    items: [
      { label: "概览", path: ".", icon: "◈" },
      { label: "写作", path: "writing", icon: "✦" },
    ],
  },
  {
    label: "实体",
    items: [
      { label: "角色", path: "characters", icon: "◉" },
      { label: "地点", path: "locations", icon: "◎" },
      { label: "场景", path: "scenes", icon: "▣" },
      { label: "线索", path: "loops", icon: "◇" },
      { label: "势力", path: "factions", icon: "⬡" },
    ],
  },
  {
    label: "分析",
    items: [
      { label: "目标", path: "goals", icon: "◯" },
      { label: "世界观", path: "lore", icon: "◈" },
    ],
  },
  {
    label: "管理",
    items: [
      { label: "节拍", path: "plot", icon: "▤" },
      { label: "存档", path: "checkpoints", icon: "▦" },
      { label: "技能", path: "skills", icon: "◆" },
      { label: "参考", path: "references", icon: "▥" },
      { label: "编译", path: "compile", icon: "▶" },
    ],
  },
];

const AVATAR_HUES = [
  "from-[#1a1235] to-[#0e0c22]",
  "from-[#0c1d35] to-[#080f22]",
  "from-[#0a2218] to-[#061510]",
  "from-[#2a1408] to-[#1e1005]",
  "from-[#280d1a] to-[#180810]",
];

function getAvatarGradient(name: string) {
  return AVATAR_HUES[(name.codePointAt(0) ?? 0) % AVATAR_HUES.length];
}

export function Sidebar({ projectName, tick }: { projectName: string; tick?: number }) {
  const { id } = useParams();
  const initials = (projectName || "?").slice(0, 2).toUpperCase();
  const avatarGrad = getAvatarGradient(projectName);
  const { isDayMode, toggleTheme: toggle } = useTheme();

  return (
    <aside
      className="w-56 flex flex-col select-none flex-shrink-0 transition-colors duration-300"
      style={{ background: "var(--bg-surface)", borderRight: "1px solid var(--border)" }}
    >
      {/* 项目头部 */}
      <div
        className="flex items-center gap-3 px-4 py-4 transition-colors duration-300"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div
          className={`w-8 h-8 rounded-lg bg-gradient-to-br ${avatarGrad} flex items-center justify-center text-xs font-bold flex-shrink-0`}
          style={{ color: "#f0ece2", border: "1px solid rgba(240,236,226,0.15)" }}
        >
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-[13px] truncate leading-tight transition-colors duration-300" style={{ color: "var(--text-1)" }}>
            {projectName}
          </h2>
          {tick !== undefined && (
            <p className="text-[11px] mt-0.5 font-mono tabular-nums transition-colors duration-300" style={{ color: "var(--text-3)" }}>
              第 {tick} 幕
            </p>
          )}
        </div>
        <ThemeToggleBtn isDayMode={isDayMode} onToggle={toggle} />
      </div>

      {/* 导航 */}
      <nav className="flex-1 overflow-auto px-2 py-3">
        {GROUPS.map((group) => (
          <div key={group.label} className="mb-5">
            <p
              className="px-3 mb-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] transition-colors duration-300"
              style={{ color: "var(--text-3)" }}
            >
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "."}
                  className={({ isActive }) =>
                    isActive
                      ? "flex items-center gap-2.5 py-1.5 text-[13px] rounded-md font-medium pr-3 pl-[10px] border-l-2 transition-colors duration-150"
                      : "flex items-center gap-2.5 py-1.5 text-[13px] rounded-md px-3 transition-all duration-150"
                  }
                  style={({ isActive }) =>
                    isActive
                      ? { borderLeftColor: "var(--accent)", backgroundColor: "rgba(200,151,90,0.1)", color: "var(--text-1)" }
                      : { color: "var(--text-3)" }
                  }
                  onMouseEnter={(e) => {
                    if (!e.currentTarget.getAttribute("aria-current")) {
                      e.currentTarget.style.backgroundColor = "var(--bg-raised)";
                      e.currentTarget.style.color = "var(--text-2)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!e.currentTarget.getAttribute("aria-current")) {
                      e.currentTarget.style.backgroundColor = "";
                      e.currentTarget.style.color = "var(--text-3)";
                    }
                  }}
                >
                  <span className="w-4 text-center text-xs leading-none flex-shrink-0">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-2 transition-colors duration-300" style={{ borderTop: "1px solid var(--border)" }}>
        <a
          href="/"
          className="flex items-center gap-2 px-3 py-1.5 text-[11px] rounded-md transition-colors duration-150"
          style={{ color: "var(--text-3)" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-2)"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-3)"; }}
        >
          <span>←</span>
          <span>返回项目列表</span>
        </a>
      </div>
    </aside>
  );
}
