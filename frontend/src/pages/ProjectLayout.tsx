import { useState } from "react";
import { Outlet, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Sidebar } from "../components/Sidebar";
import { Spinner } from "../components/ui/Spinner";
import { getStatus } from "../api/status";
import { resetAllHelps, hasDismissedHelps } from "../components/PageHelp";

export function ProjectLayout() {
  const { id } = useParams<{ id: string }>();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["status", id],
    queryFn: () => getStatus(id!),
    enabled: !!id,
  });

  if (isLoading) return (
    <div className="flex items-center justify-center h-screen" style={{ background: "var(--bg-base)" }}>
      <Spinner />
    </div>
  );
  if (!data) return (
    <div className="flex items-center justify-center h-screen text-sm" style={{ background: "var(--bg-base)", color: "var(--text-2)" }}>
      项目未找到
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-base)" }}>
      {/* Desktop sidebar — always visible on md+ */}
      <div className="hidden md:block flex-shrink-0">
        <Sidebar projectName={data.novel_name} tick={data.current_tick} />
      </div>

      {/* Mobile sidebar — overlay drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileMenuOpen(false)}
          />
          {/* Drawer */}
          <div className="relative z-10 animate-slide-in-left">
            <Sidebar
              projectName={data.novel_name}
              tick={data.current_tick}
              onNavigate={() => setMobileMenuOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-auto flex flex-col min-w-0 transition-colors duration-300" style={{ background: "var(--bg-base)" }}>
        {/* Mobile header bar */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="w-8 h-8 flex items-center justify-center rounded-lg"
            style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}
          >
            <svg width="18" height="14" viewBox="0 0 18 14" fill="none">
              <rect x="0" y="0" width="18" height="2" rx="1" fill="currentColor"/>
              <rect x="0" y="6" width="18" height="2" rx="1" fill="currentColor"/>
              <rect x="0" y="12" width="18" height="2" rx="1" fill="currentColor"/>
            </svg>
          </button>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-[13px] truncate" style={{ color: "var(--text-1)" }}>{data.novel_name}</h2>
            <p className="text-[11px] font-mono tabular-nums" style={{ color: "var(--text-3)" }}>第 {data.current_tick} 幕</p>
          </div>
          <button
            onClick={() => { if (hasDismissedHelps()) { resetAllHelps(); } else { resetAllHelps(); } }}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-xs font-bold transition-colors"
            style={{ color: "var(--text-3)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}
            title="重新显示所有功能提示"
          >?</button>
        </div>

        {/* Page content */}
        <div className="flex-1 overflow-auto p-4 md:p-8 animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
