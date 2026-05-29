import { type ReactNode } from "react";
import { useTheme } from "../ThemeContext";

export function Layout({ children }: { children: ReactNode }) {
  const { isDayMode, toggleTheme: toggle } = useTheme();

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <header
        className="h-14 flex items-center px-6 sticky top-0 z-40"
        style={{
          background: "var(--header-bg)",
          borderBottom: "1px solid var(--border)",
          backdropFilter: "blur(16px)",
          transition: "background 0.3s ease",
        }}
      >
        <a href="/" className="flex items-center gap-2.5 group">
          <span
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold flex-shrink-0"
            style={{ background: "linear-gradient(135deg, #c8975a 0%, #e5ad6a 100%)", color: "#0e0c09" }}
          >
            S
          </span>
          <span
            className="font-semibold text-sm transition-colors duration-150"
            style={{ color: "var(--text-1)" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--accent)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "var(--text-1)"; }}
          >
            InkForge
          </span>
        </a>

        <div className="ml-auto flex items-center gap-3">
          <span
            className="hidden sm:flex items-center text-[11px] font-medium rounded-full px-3 py-1"
            style={{
              color: "var(--text-3)",
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              transition: "background 0.3s ease, color 0.3s ease",
            }}
          >
            LLM 小说生成工作台
          </span>

          {/* 日间 / 夜间切换 */}
          <ThemeToggleBtn isDayMode={isDayMode} onToggle={toggle} />
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

/* ── 复用的切换按钮（深色背景通用）─── */
export function ThemeToggleBtn({ isDayMode, onToggle }: { isDayMode: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium transition-all duration-200"
      style={isDayMode ? {
        background: "var(--bg-raised)",
        border: "1px solid var(--border)",
        color: "var(--text-1)",
      } : {
        background: "rgba(200,151,90,0.15)",
        border: "1px solid rgba(200,151,90,0.35)",
        color: "#c8975a",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.opacity = "0.8";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.opacity = "1";
      }}
    >
      <span style={{ fontSize: "14px", lineHeight: 1 }}>{isDayMode ? "☀" : "◐"}</span>
      {isDayMode ? "日间" : "夜间"}
    </button>
  );
}
