import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { getActiveAnnouncements, Announcement } from "../api/announcements";

const LS_KEY = "inkforge_dismissed_anns";

export function AnnouncementBanner() {
  const [anns, setAnns] = useState<Announcement[]>([]);
  const [dismissed, setDismissed] = useState<Set<number>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(LS_KEY) || "[]")); }
    catch { return new Set(); }
  });
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    getActiveAnnouncements(3)
      .then(r => setAnns(r.announcements || []))
      .catch(() => {});
  }, []);

  const visible = anns.filter(a => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  function dismissOne(id: number) {
    const next = new Set(dismissed).add(id);
    setDismissed(next);
    localStorage.setItem(LS_KEY, JSON.stringify([...next]));
  }

  function dismissAll() {
    const ids = new Set(anns.map(a => a.id));
    setDismissed(ids);
    localStorage.setItem(LS_KEY, JSON.stringify([...ids]));
  }

  const $ = {
    amber: "rgba(220,170,80,1)",
    deep: "rgba(8,6,12,1)",
    bg: "rgba(16,12,22,0.94)",
    border: "rgba(200,150,62,0.08)",
    fg: "rgba(235,228,210,1)",
    sub: "rgba(160,152,140,1)",
    tagBg: "rgba(200,150,62,0.08)",
  };

  return createPortal(
    <div className="fixed top-4 left-1/2 z-[99999] transition-all duration-500"
      style={{
        transform: `translateX(-50%)`,
        maxWidth: "min(520px, calc(100vw - 32px))",
        width: "100%",
        opacity: collapsed ? 0.92 : 1,
      }}>
      {/* header */}
      <div className="flex items-center justify-between px-4 py-2.5 rounded-t-2xl"
        style={{
          background: `linear-gradient(135deg, rgba(18,12,26,0.98), ${$.deep})`,
          backdropFilter: "blur(20px)",
          border: `0.5px solid ${$.border}`,
          borderBottom: collapsed ? `0.5px solid ${$.border}` : "none",
          borderRadius: collapsed ? 16 : "16px 16px 0 0",
          cursor: "pointer",
        }}
        onClick={() => setCollapsed(v => !v)}>
        <div className="flex items-center gap-2.5">
          <span className="text-sm" style={{ color: $.amber }}>📢</span>
          <span className="text-[12px] font-medium tracking-wide" style={{ color: $.fg, fontFamily: "'DM Sans', sans-serif" }}>
            更新公告
          </span>
          {!collapsed && <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: $.tagBg, color: $.sub }}>{visible.length} 条</span>}
        </div>
        <div className="flex items-center gap-1">
          {!collapsed && (
            <button onClick={e => { e.stopPropagation(); dismissAll(); }}
              className="text-[10px] border-0 cursor-pointer px-2 py-1 rounded-lg transition-all hover:bg-white/5"
              style={{ background: "transparent", color: $.sub }}>
              全部关闭
            </button>
          )}
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2"
            style={{ transform: collapsed ? "rotate(0deg)" : "rotate(180deg)", transition: "transform 0.3s" }}>
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      </div>

      {/* body */}
      {!collapsed && (
        <div className="rounded-b-2xl overflow-hidden"
          style={{
            background: `linear-gradient(180deg, rgba(14,10,20,0.98), ${$.deep})`,
            backdropFilter: "blur(20px)",
            border: `0.5px solid ${$.border}`,
            borderTop: "none",
            boxShadow: "0 16px 48px rgba(0,0,0,0.5), 0 0 0 0.5px rgba(200,150,62,0.03)",
            animation: "annSlideIn 0.35s ease-out",
          }}>
          {visible.map((a, i) => (
            <div key={a.id}
              className="flex items-start px-4 py-3 transition-all"
              style={{
                gap: 10,
                borderBottom: i < visible.length - 1 ? `0.5px solid ${$.border}` : "none",
              }}>
              {/* tag */}
              <span className="flex-shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full mt-0.5"
                style={{ background: a.tag === "修复" ? "rgba(232,129,110,0.1)" : a.tag === "计划" ? "rgba(130,180,220,0.1)" : $.tagBg,
                         color: a.tag === "修复" ? "#e8816e" : a.tag === "计划" ? "#82b4dc" : $.amber }}>
                {a.tag}
              </span>
              {/* content */}
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium" style={{ color: $.fg, fontFamily: "'DM Sans', sans-serif" }}>
                  {a.title}
                </p>
                {a.content && (
                  <p className="text-[11px] mt-0.5 leading-relaxed" style={{ color: $.sub }}>
                    {a.content}
                  </p>
                )}
                <p className="text-[9px] mt-1" style={{ color: "rgba(160,152,140,0.5)", fontFamily: "'JetBrains Mono', monospace" }}>
                  {a.created_at?.slice(0, 10)}
                </p>
              </div>
              {/* dismiss */}
              <button onClick={() => dismissOne(a.id)}
                className="flex-shrink-0 border-0 cursor-pointer rounded-full flex items-center justify-center
                           opacity-30 hover:opacity-70 transition-all mt-1"
                style={{ width: 20, height: 20, background: "transparent" }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      <style>{`
        @keyframes annSlideIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>,
    document.body
  );
}
