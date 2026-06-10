import { useState, useRef, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getComments, readProject, ReadScene } from "../../api/community";
import { ChatColumn } from "../../components/community/ChatColumn";
import { ReadingChapter } from "../../components/reader/ReadingChapter";

type ReadMode = "scroll" | "page" | "auto";

export function CommunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ["communityRead", id],
    queryFn: () => readProject(id!), enabled: !!id,
  });
  const { data: comments, refetch: refetchComments } = useQuery({
    queryKey: ["comments", id],
    queryFn: () => getComments(id!), enabled: !!id,
  });
  const scenes = data?.scenes ?? [];
  const title = data?.title ?? "";
  const commentList = comments?.comments ?? [];
  const [showChat, setShowChat] = useState(false);
  const [readMode, setReadMode] = useState<ReadMode>(() => (localStorage.getItem("inkforge_readmode") as ReadMode) || "scroll");
  const [autoSpeed, setAutoSpeed] = useState(() => parseInt(localStorage.getItem("inkforge_autospeed") || "30", 10));
  const [fontSize, setFontSize] = useState(() => parseInt(localStorage.getItem("inkforge_fontsize") || "15", 10));
  const [curChapter, setCurChapter] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [showToc, setShowToc] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light" | "sepia" | "custom">(() => (localStorage.getItem("inkforge_readtheme") as any) || "dark");
  const [brightness, setBrightness] = useState(() => parseInt(localStorage.getItem("inkforge_brightness") || "100", 10));
  const [customBg, setCustomBg] = useState(() => localStorage.getItem("inkforge_custombg") || "#1a1a1a");

  const saveMode = (m: ReadMode) => { setReadMode(m); localStorage.setItem("inkforge_readmode", m); };
  const saveSpeed = (s: number) => { setAutoSpeed(s); localStorage.setItem("inkforge_autospeed", String(s)); };
  const saveFontSize = (s: number) => { setFontSize(s); localStorage.setItem("inkforge_fontsize", String(s)); };
  const goNext = () => { if (curChapter < scenes.length - 1) setCurChapter(c => c + 1); };
  const goPrev = () => { if (curChapter > 0) setCurChapter(c => c - 1); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") goNext();
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") goPrev();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [curChapter, scenes.length]);

  const currentScene = scenes[curChapter];

  return (
    <div className="h-screen flex flex-col" style={{ background: "var(--bg-base)" }}>
      <header className="flex-shrink-0 px-3 md:px-6 py-2 md:py-3 flex items-center gap-2 md:gap-4 flex-wrap"
        style={{ borderBottom: "1px solid var(--border)" }}>
        <button onClick={() => navigate(-1)}
          className="text-[10px] md:text-xs flex items-center gap-1 hover:opacity-70"
          style={{ color: "rgba(200,165,120,0.5)", background: "none", border: "none", cursor: "pointer" }}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          <span className="hidden sm:inline">返回</span>
        </button>
        <span className="text-xs md:text-sm font-medium truncate max-w-[120px] md:max-w-[200px]" style={{ color: "#d4c4a8", fontFamily: "'Cormorant Garamond', serif" }}>{title}</span>
        <span className="hidden sm:inline text-[10px] font-mono" style={{ color: "rgba(180,160,140,0.3)" }}>{scenes.length}章</span>
        <div className="flex-1" />
        <div className="flex items-center gap-1 md:gap-2">
          <button onClick={() => { const next = theme === "dark" ? "light" : theme === "light" ? "sepia" : "dark"; setTheme(next); localStorage.setItem("inkforge_readtheme", next); }}
            className="text-[10px] md:text-xs px-2 py-1 rounded-lg border-0 cursor-pointer transition-all"
            style={{ background: theme === "dark" ? "rgba(30,30,50,0.5)" : theme === "light" ? "rgba(255,255,240,0.5)" : "rgba(244,236,216,0.5)", color: theme === "dark" ? "#ccc" : theme === "light" ? "#333" : "#6a5a3a" }}>
            {theme === "dark" ? "🌙" : theme === "light" ? "☀️" : "📖"}
          </button>
          <button onClick={() => setShowToc(v => !v)}
            className="text-[10px] md:text-xs px-2 py-1 rounded-lg border-0 cursor-pointer"
            style={{ background: showToc ? "rgba(200,151,90,0.1)" : "transparent", color: showToc ? "var(--accent)" : "rgba(200,165,120,0.4)" }}>📑</button>
          <button onClick={() => setShowSettings(v => !v)}
            className="text-[10px] md:text-xs px-2 py-1 rounded-lg border-0 cursor-pointer"
            style={{ background: showSettings ? "rgba(200,151,90,0.1)" : "transparent", color: showSettings ? "var(--accent)" : "rgba(200,165,120,0.4)" }}>⚙</button>
          <button onClick={() => saveMode(readMode === "scroll" ? "page" : readMode === "page" ? "auto" : "scroll")}
            className="text-[10px] md:text-xs px-2 py-1 rounded-lg border-0 cursor-pointer"
            style={{ background: "rgba(200,151,90,0.06)", color: "rgba(200,165,120,0.5)" }}>
            {readMode === "scroll" ? "📜 滚动" : readMode === "page" ? "📖 翻页" : "⏱ 自动"}
          </button>
          <button onClick={() => setShowChat(!showChat)}
            className="lg:hidden text-xs px-2 py-1 rounded-full"
            style={{ background: showChat ? "rgba(200,151,90,0.12)" : "transparent", color: showChat ? "var(--accent)" : "rgba(200,165,120,0.4)" }}>💬</button>
        </div>
      </header>
      {showSettings && (
        <div className="flex-shrink-0 px-4 md:px-6 py-3 flex flex-wrap items-center gap-3 md:gap-5 text-[11px]"
          style={{ borderBottom: "1px solid rgba(200,151,90,0.04)", background: "rgba(10,8,16,0.3)" }}>
          <span style={{ color: "var(--text-3)" }}>模式</span>
          {(["scroll", "page", "auto"] as ReadMode[]).map(m => (
            <button key={m} onClick={() => saveMode(m)}
              className="border-0 cursor-pointer px-2.5 py-1 rounded-lg transition-all"
              style={{ background: readMode === m ? "rgba(200,151,90,0.12)" : "transparent", color: readMode === m ? "var(--accent)" : "rgba(180,160,140,0.4)" }}>
              {m === "scroll" ? "滚动" : m === "page" ? "翻页" : "自动"}
            </button>
          ))}
          <span className="mx-2" style={{ color: "rgba(180,160,140,0.15)" }}>|</span>
          {readMode === "auto" && (<>
            <span style={{ color: "rgba(180,160,140,0.4)" }}>速度</span>
            <input type="range" min="5" max="60" value={autoSpeed} onChange={e => saveSpeed(parseInt(e.target.value))} className="w-20 md:w-28" />
            <span style={{ color: "rgba(180,160,140,0.3)", fontFamily: "'JetBrains Mono', monospace" }}>{autoSpeed}s</span>
          </>)}
          <span className="mx-2" style={{ color: "rgba(180,160,140,0.15)" }}>|</span>
          <span style={{ color: "rgba(180,160,140,0.4)" }}>字号</span>
          <button onClick={() => saveFontSize(Math.max(13, fontSize - 1))} className="border-0 cursor-pointer px-1.5" style={{ background: "transparent", color: "rgba(180,160,140,0.4)" }}>A-</button>
          <span style={{ color: "rgba(200,165,120,0.6)", fontFamily: "'JetBrains Mono', monospace" }}>{fontSize}px</span>
          <button onClick={() => saveFontSize(Math.min(22, fontSize + 1))} className="border-0 cursor-pointer px-1.5" style={{ background: "transparent", color: "rgba(180,160,140,0.4)" }}>A+</button>
          <span className="mx-2" style={{ color: "rgba(180,160,140,0.15)" }}>|</span>
          <span style={{ color: "rgba(180,160,140,0.4)" }}>亮度</span>
          <input type="range" min="50" max="150" value={brightness}
            onChange={e => { const v = parseInt(e.target.value); setBrightness(v); localStorage.setItem("inkforge_brightness", String(v)); }} className="w-16 md:w-24" />
          <span style={{ color: "rgba(180,160,140,0.4)", fontFamily: "'JetBrains Mono', monospace" }}>{brightness}%</span>
          <span className="mx-2" style={{ color: "rgba(180,160,140,0.15)" }}>|</span>
          <span style={{ color: "rgba(180,160,140,0.4)" }}>背景</span>
          <input type="color" value={customBg}
            onChange={e => { setCustomBg(e.target.value); setTheme("custom"); localStorage.setItem("inkforge_custombg", e.target.value); localStorage.setItem("inkforge_readtheme", "custom"); }}
            className="w-6 h-6 rounded border cursor-pointer" style={{ background: "transparent" }} />
          <span className="mx-2" style={{ color: "rgba(180,160,140,0.15)" }}>|</span>
          <button onClick={goPrev} disabled={curChapter === 0} className="border-0 cursor-pointer disabled:opacity-20" style={{ background: "transparent", color: "rgba(180,160,140,0.4)" }}>◀</button>
          <select value={curChapter} onChange={e => setCurChapter(parseInt(e.target.value))}
            className="text-[11px] px-2 py-0.5 rounded outline-none border-0"
            style={{ background: "rgba(255,255,255,0.03)", color: "rgba(200,165,120,0.6)" }}>
            {scenes.map((s, i) => (<option key={i} value={i}>{s.title || `第${s.tick}章`}</option>))}
          </select>
          <button onClick={goNext} disabled={curChapter >= scenes.length - 1} className="border-0 cursor-pointer disabled:opacity-20" style={{ background: "transparent", color: "rgba(180,160,140,0.4)" }}>▶</button>
        </div>
      )}
      <div className="flex-1 flex min-h-0">
        {showToc && (
          <div className="w-56 md:w-64 flex-shrink-0 overflow-auto py-3" style={{ background: "var(--bg-surface)", borderRight: "1px solid var(--border)" }}>
            <h4 className="px-4 text-xs font-semibold mb-3" style={{ color: "var(--text-1)" }}>📑 目录</h4>
            {scenes.map((s, i) => (
              <button key={i} onClick={() => { setCurChapter(i); if (readMode === "scroll") setReadMode("page"); }}
                className="w-full text-left px-4 py-2 text-[11px] truncate border-0 cursor-pointer transition-all"
                style={{ background: i === curChapter ? "rgba(200,151,90,0.08)" : "transparent", color: i === curChapter ? "var(--accent)" : "var(--text-3)" }}>
                {s.title || `第 ${s.tick} 章`}
              </button>
            ))}
          </div>
        )}
        <div className={`flex-1 ${showChat ? 'hidden lg:block' : ''} ${readMode === "scroll" ? "overflow-auto" : "overflow-hidden"}`}
          style={{ background: theme === "light" ? "#f8f5f0" : theme === "sepia" ? "#f4ecd8" : theme === "custom" ? customBg : "#121212", filter: `brightness(${brightness / 100})`, transition: "background 0.3s ease, filter 0.3s ease" }}>
          {isLoading ? (
            <div className="flex items-center justify-center py-32"><span className="text-sm" style={{ color: theme === "light" ? "#999" : "rgba(200,165,120,0.4)" }}>加载中…</span></div>
          ) : scenes.length === 0 ? (
            <div className="text-center py-24"><div className="text-5xl mb-4 opacity-20">📜</div><p className="text-sm" style={{ color: theme === "light" ? "#999" : "rgba(200,165,120,0.4)" }}>暂无内容</p></div>
          ) : readMode === "scroll" ? (
            <ScrollReader scenes={scenes} commentList={commentList} projectId={id!} onCommented={refetchComments} fontSize={fontSize} onChapterChange={setCurChapter} theme={theme} />
          ) : (
            <PageReader scene={currentScene} commentList={commentList} projectId={id!} onCommented={refetchComments}
              curChapter={curChapter} totalChapters={scenes.length} fontSize={fontSize} onPrev={goPrev} onNext={goNext} readMode={readMode} autoSpeed={autoSpeed} theme={theme} />
          )}
        </div>
        <ChatColumn projectId={id} />
        {showChat && <div className="lg:hidden flex-1 flex flex-col"><ChatColumn projectId={id} /></div>}
      </div>
    </div>
  );
}

function ScrollReader({ scenes, commentList, projectId, onCommented, fontSize, onChapterChange, theme }: {
  scenes: ReadScene[]; commentList: any[]; projectId: string; onCommented: () => void;
  fontSize: number; onChapterChange: (n: number) => void; theme: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = containerRef.current; if (!el) return;
    const onScroll = () => {
      const chapters = el.querySelectorAll("[data-chapter]"); let closest = 0; let minDist = Infinity;
      chapters.forEach(ch => { const rect = ch.getBoundingClientRect(); const dist = Math.abs(rect.top - 100); if (dist < minDist) { minDist = dist; closest = parseInt(ch.getAttribute("data-chapter") || "0"); } });
      onChapterChange(closest);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <div ref={containerRef} className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto px-3 md:px-8 py-6 md:py-8">
        {scenes.map(s => (
          <div key={s.tick} data-chapter={s.tick}>
            <ReadingChapter scene={s} fontSize={fontSize} theme={theme}
              comments={commentList.filter((c: any) => c.chapter_tick === s.tick)}
              projectId={projectId} onCommented={onCommented} />
          </div>
        ))}
      </div>
    </div>
  );
}

function PageReader({ scene, commentList, projectId, onCommented, curChapter, totalChapters, fontSize, onPrev, onNext, readMode, autoSpeed, theme }: {
  scene: ReadScene; commentList: any[]; projectId: string; onCommented: () => void;
  curChapter: number; totalChapters: number; fontSize: number;
  onPrev: () => void; onNext: () => void; readMode: ReadMode; autoSpeed: number; theme: string;
}) {
  const touchRef = useRef({ x: 0, y: 0 });
  const autoRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (readMode !== "auto") { if (autoRef.current) clearInterval(autoRef.current); return; }
    autoRef.current = setInterval(() => onNext(), autoSpeed * 1000);
    return () => { if (autoRef.current) clearInterval(autoRef.current); };
  }, [readMode, autoSpeed, curChapter, totalChapters]);
  const onTouchStart = (e: React.TouchEvent) => { touchRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }; };
  const onTouchEnd = (e: React.TouchEvent) => { const dx = e.changedTouches[0].clientX - touchRef.current.x; const dy = e.changedTouches[0].clientY - touchRef.current.y; if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) { if (dx < 0) onNext(); else onPrev(); } };
  const pageComments = commentList.filter((c: any) => c.chapter_tick === scene.tick);
  return (
    <div className="h-full flex flex-col" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
      <div className="flex-1 overflow-auto px-3 md:px-8 py-6 md:py-10">
        <div className="max-w-3xl mx-auto">
          <ReadingChapter scene={scene} fontSize={fontSize} theme={theme} comments={pageComments} projectId={projectId} onCommented={onCommented} />
        </div>
      </div>
      <div className="flex-shrink-0 flex items-center justify-center gap-3 md:gap-6 py-3 px-4"
        style={{ borderTop: "1px solid rgba(200,151,90,0.06)", background: "rgba(10,8,16,0.4)" }}>
        <button onClick={onPrev} disabled={curChapter === 0} className="border-0 cursor-pointer px-3 md:px-5 py-2 rounded-xl text-xs md:text-sm font-medium transition-all disabled:opacity-20"
          style={{ background: "rgba(255,255,255,0.03)", color: "rgba(200,165,120,0.6)" }}>上一章</button>
        <span className="text-[10px] md:text-xs" style={{ color: "rgba(180,160,140,0.3)", fontFamily: "'JetBrains Mono', monospace" }}>{curChapter + 1} / {totalChapters}</span>
        <button onClick={onNext} disabled={curChapter >= totalChapters - 1} className="border-0 cursor-pointer px-3 md:px-5 py-2 rounded-xl text-xs md:text-sm font-medium transition-all disabled:opacity-20"
          style={{ background: readMode === "auto" ? "rgba(200,151,90,0.1)" : "rgba(255,255,255,0.03)", color: readMode === "auto" ? "var(--accent)" : "rgba(200,165,120,0.6)" }}>下一章</button>
        {readMode === "auto" && <span className="text-[10px] animate-pulse" style={{ color: "var(--accent)" }}>⏱ {autoSpeed}s</span>}
      </div>
    </div>
  );
}
