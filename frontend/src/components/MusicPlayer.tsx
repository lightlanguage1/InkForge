import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  searchMusic, getRandomSongs, getFavorites,
  addFavorite, removeFavorite, getStreamUrl, Song,
} from "../api/music";

/* ═══════════════════════════════════════════════════════════
   MusicPlayer — Analog Hi-Fi
   搜索 · 收藏 · 随机发现 · 播放模式（顺序/随机/单曲循环）
   ═══════════════════════════════════════════════════════════ */

type Tab = "search" | "favorites" | "discover";
type PlayMode = "sequential" | "shuffle" | "repeat-one" | "repeat-all";

export function MusicPlayer() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("search");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Song[]>([]);
  const [discoverResults, setDiscoverResults] = useState<Song[]>([]);
  const [searching, setSearching] = useState(false);
  const [current, setCurrent] = useState<Song | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [playlist, setPlaylist] = useState<Song[]>([]);
  const [playIndex, setPlayIndex] = useState(-1);
  const [mode, setMode] = useState<PlayMode>("sequential");
  const [shuffleOrder, setShuffleOrder] = useState<number[]>([]);
  const [shufflePos, setShufflePos] = useState(-1);
  const [favorites, setFavorites] = useState<Song[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const shuffleOrderRef = useRef<number[]>([]);
  const shufflePosRef = useRef(-1);
  // refs for onTrackEnd（避免 stale closure）
  const playlistRef = useRef<Song[]>([]);
  const playIndexRef = useRef(-1);
  const modeRef = useRef<PlayMode>("sequential");
  const currentRef = useRef<Song | null>(null);
  useEffect(() => { playlistRef.current = playlist; }, [playlist]);
  useEffect(() => { playIndexRef.current = playIndex; }, [playIndex]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { currentRef.current = current; }, [current]);
  /* ── 可拖拽迷你播放器 ── */
  const miniRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 });
  const [miniPos, setMiniPos] = useState<{ x: number; y: number } | null>(() => {
    try { const v = JSON.parse(localStorage.getItem("mp_mini_pos") || "null"); return v; } catch { return null; }
  });
  /* ── 节拍分析 ── */
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const [beat, setBeat] = useState(0);
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const onTrackEndRef = useRef<() => void>(() => {});
  const inputRef = useRef<HTMLInputElement | null>(null);
  const tickRef = useRef(0);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const favLoadedRef = useRef(false);

  /* ── audio ── */
  function audio(): HTMLAudioElement {
    if (!audioRef.current) {
      const a = new Audio();
      a.volume = 0.72; a.preload = "auto";
      a.addEventListener("timeupdate", () => setPosition(a.currentTime));
      a.addEventListener("loadedmetadata", () => setDuration(a.duration || 0));
      a.addEventListener("error", () => { setError(a.error ? `code ${a.error.code}` : "err"); setPlaying(false); });
      a.addEventListener("ended", () => onTrackEnd());
      a.addEventListener("play", () => { setPlaying(true); setError(""); });
      a.addEventListener("pause", () => { if (!a.ended) setPlaying(false); });
      audioRef.current = a;
    }
    return audioRef.current;
  }

  /* ── 预洗牌队列（网易云逻辑）── */
  function buildShuffleOrder(listLen: number, startIdx: number) {
    const order = Array.from({ length: listLen }, (_, i) => i).filter(i => i !== startIdx);
    // Fisher-Yates 洗牌
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    // 当前播放的排在第一位，其余随机排列
    const result = [startIdx, ...order];
    shuffleOrderRef.current = result;
    shufflePosRef.current = 0;
    setShuffleOrder(result);
    setShufflePos(0);
  }

  function getShuffleNext(): number {
    const order = shuffleOrderRef.current;
    let pos = shufflePosRef.current + 1;
    // 播完一圈 → 重新洗牌
    if (pos >= order.length) {
      const currentIdx = order[0];
      const listLen = order.length;
      const newOrder = Array.from({ length: listLen }, (_, i) => i).filter(i => i !== currentIdx);
      for (let i = newOrder.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [newOrder[i], newOrder[j]] = [newOrder[j], newOrder[i]];
      }
      newOrder.unshift(currentIdx);
      shuffleOrderRef.current = newOrder;
      setShuffleOrder(newOrder);
      pos = 1;
    }
    shufflePosRef.current = pos;
    setShufflePos(pos);
    return order[pos];
  }

  function getShufflePrev(): number {
    const pos = shufflePosRef.current - 1;
    if (pos < 0) return -1; // 没有上一首了
    shufflePosRef.current = pos;
    setShufflePos(pos);
    return shuffleOrderRef.current[pos];
  }

  /* ── track ended → auto next ── */
  // 保持 ref 指向最新 onTrackEnd
  onTrackEndRef.current = onTrackEndReal;
  function onTrackEnd() { onTrackEndRef.current(); }
  function onTrackEndReal() {
    setPlaying(false); setPosition(0);
    const m = modeRef.current;
    const pl = playlistRef.current;
    const idx = playIndexRef.current;
    if (m === "repeat-one") { audio().currentTime = 0; audio().play().catch(() => {}); return; }
    if (pl.length === 0) return;
    if (m === "shuffle") {
      playSongAtIndex(getShuffleNext());
      return;
    }
    // 顺序模式：自动下一首，到底就循环
    const next = idx + 1;
    playSongAtIndex(next >= pl.length ? 0 : next);
  }

  /* ── discover / random ── */
  async function loadDiscover() {
    setSearching(true);
    try { const r = await getRandomSongs(); setDiscoverResults(r.results || []); }
    catch { setDiscoverResults([]); }
    setSearching(false);
  }

  async function playRandom() {
    setSearching(true); setError("");
    try {
      const r = await getRandomSongs(30);
      const songs = r.results || [];
      setDiscoverResults(songs);
      setTab("discover");
      if (songs.length > 0) {
        setMode("shuffle");
        // 构建洗牌队列
        buildShuffleOrder(songs.length, 0);
        playSong(songs[0], songs);
      }
    } catch { /* silent */ }
    setSearching(false);
  }

  /* ── progress tick ── */
  useEffect(() => {
    if (!playing) return;
    const a = audio();
    const tick = () => { setPosition(a.currentTime); tickRef.current = requestAnimationFrame(tick); };
    tickRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(tickRef.current);
  }, [playing]);

  /* ── Web Audio 节拍分析 ── */
  useEffect(() => {
    const a = audio();
    if (!audioCtxRef.current) {
      try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const src = ctx.createMediaElementSource(a);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.7;
        src.connect(analyser);
        analyser.connect(ctx.destination);
        audioCtxRef.current = ctx;
        analyserRef.current = analyser;
      } catch { /* Web Audio not supported */ }
    }
    // 每次有用户交互就尝试恢复 AudioContext
    const resume = () => { audioCtxRef.current?.resume().catch(() => {}); };
    document.addEventListener("click", resume);
    document.addEventListener("touchstart", resume);
    return () => {
      document.removeEventListener("click", resume);
      document.removeEventListener("touchstart", resume);
    };
  }, []);

  useEffect(() => {
    if (!analyserRef.current || !playing) return;
    const analyser = analyserRef.current;
    const data = new Uint8Array(analyser.frequencyBinCount);
    let raf = 0;
    const tick = () => {
      analyser.getByteFrequencyData(data);
      // 取低频段平均值作为节拍强度
      const lowSum = data.slice(0, 16).reduce((s, v) => s + v, 0) / 16;
      setBeat(Math.min(1, lowSum / 180));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  /* ── 拖拽（全局监听） ── */
  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      const d = dragRef.current;
      if (!d.dragging) return;
      const p = "touches" in e ? e.touches[0] : e;
      const nx = d.origX + (p.clientX - d.startX);
      const ny = d.origY + (p.clientY - d.startY);
      // 限制在屏幕内
      const clampedX = Math.max(0, Math.min(nx, window.innerWidth - 52));
      const clampedY = Math.max(0, Math.min(ny, window.innerHeight - 52));
      setMiniPos({ x: clampedX, y: clampedY });
    };
    const onUp = () => {
      if (dragRef.current.dragging) {
        dragRef.current.dragging = false;
        setMiniPos(p => { if (p) localStorage.setItem("mp_mini_pos", JSON.stringify(p)); return p; });
      }
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("touchend", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("touchmove", onMove);
      document.removeEventListener("touchend", onUp);
    };
  }, []);

  function startDrag(e: React.MouseEvent | React.TouchEvent) {
    e.stopPropagation();
    e.preventDefault();
    const p = "touches" in e ? e.touches[0] : e;
    const pos = miniPos || { x: window.innerWidth - 56, y: window.innerHeight - 56 };
    dragRef.current = { dragging: true, startX: p.clientX, startY: p.clientY, origX: pos.x, origY: pos.y };
  }

  /* ── open panel → focus + load favorites ── */
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 250);
      if (!favLoadedRef.current) { loadFavorites(); favLoadedRef.current = true; }
    }
  }, [open]);

  /* ── click outside ── */
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false); };
    const t = setTimeout(() => document.addEventListener("mousedown", onDown), 0);
    return () => { clearTimeout(t); document.removeEventListener("mousedown", onDown); };
  }, [open]);

  /* ── keyboard ── */
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key !== " " || !current) return;
      if (/(input|textarea)/i.test((e.target as HTMLElement)?.tagName || "")) return;
      e.preventDefault();
      audio().paused ? audio().play().catch(() => {}) : audio().pause();
    };
    window.addEventListener("keydown", on); return () => window.removeEventListener("keydown", on);
  }, [current]);

  /* ── favorites ── */
  async function loadFavorites() {
    try {
      const r = await getFavorites();
      setFavorites(r.results || []);
      setFavoriteIds(new Set((r.results || []).map(s => s.id)));
    } catch { /* silent */ }
  }
  async function toggleFavorite(song: Song, e?: React.MouseEvent) {
    e?.stopPropagation();
    const fid = song.id;
    try {
      if (favoriteIds.has(fid)) {
        await removeFavorite(fid);
        setFavoriteIds(p => { const n = new Set(p); n.delete(fid); return n; });
        setFavorites(p => p.filter(s => s.id !== fid));
      } else {
        await addFavorite(song);
        setFavoriteIds(p => new Set(p).add(fid));
        setFavorites(p => { if (p.find(s => s.id === fid)) return p; return [song, ...p]; });
      }
    } catch { /* silent */ }
  }

  /* ── actions ── */
  const doSearch = useCallback(async () => {
    const q = query.trim(); if (!q) return;
    setSearching(true); setError("");
    try { const r = await searchMusic(q); setResults(r.results || []); }
    catch { setResults([]); }
    setSearching(false);
  }, [query]);

  const playSong = useCallback((song: Song, sourceList?: Song[]) => {
    const a = audio(); setError(""); setPosition(0); setDuration(0);
    audioCtxRef.current?.resume().catch(() => {});
    a.src = getStreamUrl(song.mid, song.title, song.artist);
    a.play().then(() => setPlaying(true)).catch(e => setError(e.message || "无法播放"));
    setCurrent(song);
    // 网易云逻辑：有 sourceList（搜索结果等）→ 替换整个队列，否则保留现有队列只更新位置
    if (sourceList && sourceList.length > 0) {
      setPlaylist(sourceList);
      const idx = sourceList.findIndex(s => s.mid === song.mid);
      buildShuffleOrder(sourceList.length, idx >= 0 ? idx : 0);
      setPlayIndex(idx >= 0 ? idx : 0);
    } else {
      setPlaylist(p => {
        const idx = p.findIndex(s => s.mid === song.mid);
        if (idx >= 0) { setPlayIndex(idx); return p; }
        setPlayIndex(p.length);
        return [...p, song];
      });
    }
  }, []);

  function playSongAtIndex(i: number) {
    if (i < 0 || i >= playlist.length) return;
    const song = playlist[i];
    setPlayIndex(i);
    setCurrent(song);
    const a = audio(); setError(""); setPosition(0); setDuration(0);
    a.src = getStreamUrl(song.mid, song.title, song.artist);
    a.play().then(() => setPlaying(true)).catch(e => setError(e.message || "无法播放"));
  }

  const togglePlay = useCallback(() => {
    if (!current) return;
    audioCtxRef.current?.resume().catch(() => {});
    const a = audio();
    if (playing) a.pause();
    else a.play().then(() => setPlaying(true)).catch(e => setError(e.message));
  }, [current, playing]);

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const d = duration || audio().duration || 0; if (!d) return;
    const r = e.currentTarget.getBoundingClientRect();
    audio().currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * d;
  }, [duration]);

  const fmt = (s: number) => {
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };
  const pct = ((duration || current?.duration || 0) > 0 ? (position / (duration || current?.duration || 1)) * 100 : 0);

  function modeIcon(): string {
    if (mode === "shuffle") return "⇄";
    if (mode === "repeat-one") return "↻¹";
    if (mode === "repeat-all") return "↻";
    return "→";
  }

  /* ── design tokens ── */
  const $ = {
    amber: "#c8963e", deep: "#0d0b12", panel: "#13101a",
    surface: "rgba(255,255,255,0.025)", line: "rgba(255,255,255,0.04)",
    fg: "rgba(232,226,212,1)", sub: "rgba(158,150,138,1)",
  };

  function renderSongRow(s: Song, isCurrent: boolean, sourceList?: Song[]) {
    return (
      <button key={s.mid} onClick={() => playSong(s, sourceList)}
        className="w-full flex items-center text-left border-0 cursor-pointer rounded-xl transition-all duration-200"
        style={{ gap: 12, padding: "10px 12px", background: isCurrent ? "rgba(200,150,62,0.06)" : "transparent" }}
        onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = $.surface; }}
        onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.background = "transparent"; }}>
        <div className="flex-shrink-0 rounded-lg overflow-hidden" style={{ width: 42, height: 42 }}>
          {s.artwork ? (
            <img src={s.artwork} className="w-full h-full object-cover bg-black/20" onError={e => { e.currentTarget.style.display = "none"; }} />
          ) : (
            <div className="w-full h-full flex items-center justify-center" style={{ background: "rgba(200,150,62,0.08)", color: $.amber, fontSize: 17 }}>♪</div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="truncate" style={{ fontSize: 13, fontWeight: isCurrent ? 500 : 400, color: isCurrent ? $.amber : $.fg, fontFamily: "'DM Sans', sans-serif" }}>{s.title}</p>
          <p className="text-[11px] truncate" style={{ color: $.sub }}>{s.artist}</p>
        </div>
        <div className="flex-shrink-0 flex items-center" style={{ gap: 8 }}>
          {s.duration > 0 && <span className="text-[11px]" style={{ color: $.sub, fontFamily: "'JetBrains Mono', monospace" }}>{fmt(s.duration)}</span>}
          {/* heart */}
          <span onClick={(e) => toggleFavorite(s, e)}
            className="cursor-pointer transition-all text-base hover:scale-125"
            style={{ color: favoriteIds.has(s.id) ? "#e8816e" : $.sub, opacity: favoriteIds.has(s.id) ? 1 : 0.3 }}>
            {favoriteIds.has(s.id) ? "♥" : "♡"}
          </span>
          {isCurrent && playing && (
            <span className="flex items-end" style={{ gap: 1.5, height: 11 }}>
              <span style={{ width: 2, height: 5, background: $.amber, borderRadius: 1, animation: "mpBar1 0.6s ease-in-out infinite" }} />
              <span style={{ width: 2, height: 11, background: $.amber, borderRadius: 1, animation: "mpBar2 0.5s ease-in-out infinite" }} />
              <span style={{ width: 2, height: 3, background: $.amber, borderRadius: 1, animation: "mpBar3 0.55s ease-in-out infinite" }} />
            </span>
          )}
        </div>
      </button>
    );
  }

  return createPortal(
    <>
      {/* ═══════════════════════════════════════════ 统一入口球（可拖拽） ═══ */}
      {/* ═══════════════════════════════════════════ 统一入口球（可拖拽） ═══ */}
      {!open && (
        (() => {
          const pos = miniPos || { x: window.innerWidth - 56, y: window.innerHeight - 56 };
          const hasMusic = !!current;
          const scaleVal = hasMusic ? (1 + beat * 0.04) : 1;
          const glowIntensity = hasMusic ? (0.12 + beat * 0.35) : 0;
          const glowRadius = hasMusic ? (10 + beat * 8) : 0;
          return (
            <div
              ref={miniRef}
              onMouseDown={startDrag}
              onTouchStart={startDrag}
              onClick={() => { if (!dragRef.current.dragging) setOpen(true); }}
              className="fixed flex items-center justify-center select-none"
              title="拖拽移动 · 点击打开播放器"
              style={{
                left: pos.x, top: pos.y, zIndex: 99999,
                width: 46, height: 46, borderRadius: "50%",
                cursor: "grab",
                transform: `scale(${scaleVal})`,
                background: hasMusic
                  ? `radial-gradient(circle at 35% 35%, ${$.amber}, #8b6914)`
                  : `radial-gradient(circle at 40% 40%, rgba(40,32,28,0.9), rgba(18,14,22,0.96))`,
                boxShadow: hasMusic
                  ? `0 0 ${glowRadius}px rgba(200,150,62,${glowIntensity}), 0 3px 16px rgba(0,0,0,0.35), inset 0 -1px 3px rgba(0,0,0,0.15)`
                  : `0 2px 12px rgba(0,0,0,0.5), 0 0 0 0.5px rgba(255,255,255,0.04)`,
                backdropFilter: "blur(8px)",
                transition: "transform 0.2s cubic-bezier(0.25,0.1,0.25,1), box-shadow 0.2s cubic-bezier(0.25,0.1,0.25,1)",
                animation: hasMusic && playing ? "mpBreath 3s ease-in-out infinite" : "none",
              }}>
              {/* 封面 — 黑胶旋转 */}
              {hasMusic && current.artwork && (
                <div className="absolute inset-1 rounded-full overflow-hidden"
                  style={{ animation: playing ? "mpVinyl 6s linear infinite" : "none" }}>
                  <img src={current.artwork} className="w-full h-full object-cover opacity-70"
                    onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                </div>
              )}
              {/* 图标 — 固定 ♪ */}
              {hasMusic && playing ? (
                <span className="relative z-10 text-sm"
                  style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.4))" }}>♪</span>
              ) : hasMusic ? (
                <span className="relative z-10 text-sm" style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,0.3))" }}>♪</span>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
                </svg>
              )}
              {/* 扬声器振膜脉冲 */}
              {playing && (
                <span className="absolute inset-0 rounded-full"
                  style={{
                    background: "radial-gradient(circle, rgba(200,150,62,0.35) 0%, transparent 70%)",
                    animation: "mpThump 0.6s ease-out infinite",
                  }} />
              )}
            </div>
          );
        })()
      )}


      {/* ═══════════════════════════════════════════ PANEL ═══ */}
      {open && (
        <div ref={panelRef} className="fixed flex flex-col overflow-hidden"
          style={{ right: 20, bottom: 76, zIndex: 99998, width: 380, maxWidth: "calc(100vw - 24px)", maxHeight: "min(560px, calc(100vh - 120px))", borderRadius: 20,
            background: `linear-gradient(175deg, ${$.panel} 0%, ${$.deep} 100%)`, border: "0.5px solid rgba(200,150,62,0.06)",
            boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 0 0 0.5px rgba(200,150,62,0.04), 0 0 120px rgba(0,0,0,0.3)",
            animation: "mpPanelIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)" }}>

          {/* grain overlay */}
          <div className="absolute inset-0 pointer-events-none opacity-[0.03]"
            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")` }} />

          {/* header */}
          <div className="flex items-center justify-between px-5 py-4 flex-shrink-0 relative z-10" style={{ borderBottom: `0.5px solid ${$.line}` }}>
            <h2 style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 17, fontWeight: 600, letterSpacing: "0.04em", color: $.fg }}>Listening</h2>
            <button onClick={() => setOpen(false)}
              className="border-0 cursor-pointer rounded-full flex items-center justify-center transition-all opacity-30 hover:opacity-70"
              style={{ width: 28, height: 28, background: "transparent", color: $.sub }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>

          {/* tabs */}
          <div className="flex-shrink-0 relative z-10 flex px-5 pt-3 pb-1" style={{ gap: 4 }}>
            {(["search", "favorites", "discover"] as Tab[]).map(t => (
              <button key={t} onClick={() => { setTab(t); if (t === "discover") loadDiscover(); if (t === "favorites") loadFavorites(); }}
                className="border-0 cursor-pointer rounded-lg px-3.5 py-1.5 text-[12px] font-medium transition-all"
                style={{ background: tab === t ? "rgba(200,150,62,0.1)" : "transparent", color: tab === t ? $.amber : $.sub }}>
                {t === "search" ? "搜索" : t === "favorites" ? "收藏" : "发现"}
              </button>
            ))}
            {/* random play button */}
            <div className="flex-1" />
            <button onClick={playRandom}
              className="border-0 cursor-pointer rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all hover:scale-105"
              style={{ background: $.amber, color: $.deep }}>
              🎲 随机播放
            </button>
            {/* mode toggle */}
            <button onClick={() => {
              const modes: PlayMode[] = ["sequential", "shuffle", "repeat-all", "repeat-one"];
              const i = modes.indexOf(mode);
              const next = modes[(i + 1) % modes.length];
              setMode(next);
              // 切换到随机模式时生成洗牌队列
              if (next === "shuffle" && playlist.length > 0) {
                buildShuffleOrder(playlist.length, playIndex >= 0 ? playIndex : 0);
              }
            }}
              className="border-0 cursor-pointer rounded-lg px-2 py-1.5 text-[14px] transition-all"
              style={{ background: mode !== "sequential" ? "rgba(200,150,62,0.1)" : "transparent", color: mode !== "sequential" ? $.amber : $.sub }}
              title={mode === "shuffle" ? "随机播放" : mode === "repeat-one" ? "单曲循环" : mode === "repeat-all" ? "列表循环" : "顺序播放"}>
              {modeIcon()}
            </button>
          </div>

          {/* search bar (search tab only) */}
          {tab === "search" && (
            <div className="px-5 py-3 flex-shrink-0 relative z-10">
              <div className="flex gap-2.5">
                <input ref={inputRef} value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter") doSearch(); }}
                  placeholder="曲目或艺术家…"
                  className="flex-1 text-[13px] px-4 py-2.5 rounded-xl outline-none transition-all duration-300"
                  style={{ background: $.surface, border: `0.5px solid ${$.line}`, color: $.fg, fontFamily: "'DM Sans', sans-serif" }}
                  onFocus={e => { e.currentTarget.style.borderColor = "rgba(200,150,62,0.2)"; e.currentTarget.style.background = "rgba(255,255,255,0.04)"; }}
                  onBlur={e => { e.currentTarget.style.borderColor = $.line; e.currentTarget.style.background = $.surface; }} />
                <button onClick={doSearch} disabled={searching}
                  className="border-0 cursor-pointer rounded-xl text-[13px] font-medium px-5 py-2.5 transition-all duration-300"
                  style={{ background: $.amber, color: $.deep, opacity: searching ? 0.4 : 1 }}>{searching ? "…" : "搜索"}</button>
              </div>
            </div>
          )}

          {/* tab content */}
          <div className="flex-1 overflow-auto px-3 py-1 relative z-10" style={{ scrollBehavior: "smooth" }}>
            {tab === "search" && results.map(s => renderSongRow(s, current?.mid === s.mid, results))}
            {tab === "favorites" && favorites.map(s => renderSongRow(s, current?.mid === s.mid, favorites))}
            {tab === "discover" && discoverResults.map(s => renderSongRow(s, current?.mid === s.mid, discoverResults))}

            {!searching && (
              <div className="flex flex-col items-center justify-center py-20" style={{ gap: 4 }}>
                <span style={{ fontSize: 32, opacity: 0.15 }}>♪</span>
                <p className="text-[12px]" style={{ color: $.sub }}>
                  {tab === "search" && (query ? "没有找到" : "搜一首歌开始")}
                  {tab === "favorites" && (favorites.length === 0 ? "还没有收藏" : "")}
                  {tab === "discover" && (discoverResults.length === 0 ? (searching ? "加载中…" : "点击发现获取随机推荐") : "")}
                </p>
              </div>
            )}
          </div>

          {/* now-playing footer */}
          {current && (
            <div className="flex-shrink-0 relative z-10 px-5 py-4" style={{ borderTop: `0.5px solid ${$.line}` }}>
              {error && <p className="text-[11px] mb-2" style={{ color: "#e8816e" }}>{error}</p>}
              {/* progress */}
              <div className="h-[3px] rounded-full mb-3.5 cursor-pointer group relative" style={{ background: $.line }} onClick={seek}>
                <div className="h-full rounded-full transition-all duration-300 relative"
                  style={{ background: `linear-gradient(90deg, ${$.amber}, rgba(200,150,62,0.4))`, width: `${pct}%` }}>
                  <div className="absolute -right-[6px] -top-[4px] w-[11px] h-[11px] rounded-full opacity-0 group-hover:opacity-100 transition-all duration-200"
                    style={{ background: $.amber, boxShadow: `0 0 8px rgba(200,150,62,0.5)` }} />
                </div>
              </div>
              {/* controls */}
              <div className="flex items-center" style={{ gap: 10 }}>
                {/* prev */}
                <button onClick={() => {
                  if (mode === "shuffle") {
                    const prevIdx = getShufflePrev();
                    if (prevIdx >= 0) playSongAtIndex(prevIdx);
                    return;
                  }
                  playSongAtIndex(playIndex - 1);
                }} disabled={mode === "shuffle" ? shufflePos <= 0 : (playIndex <= 0 && mode !== "repeat-all")}
                  className="border-0 cursor-pointer flex items-center justify-center transition-opacity"
                  style={{ width: 28, height: 28, background: "transparent", opacity: (playIndex <= 0 && mode !== "repeat-all") ? 0.2 : 0.5 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2"><polygon points="19,5 9,12 19,19"/><line x1="5" y1="5" x2="5" y2="19"/></svg>
                </button>
                {/* play/pause */}
                <button onClick={togglePlay}
                  className="flex-shrink-0 border-0 cursor-pointer rounded-full flex items-center justify-center transition-all duration-300 relative"
                  style={{ width: 44, height: 44, background: `radial-gradient(circle at 40% 40%, ${$.amber}, #8b6914)`,
                    boxShadow: playing ? `0 0 20px rgba(200,150,62,0.5), 0 0 50px rgba(200,150,62,0.08)` : "0 2px 8px rgba(0,0,0,0.3)" }}>
                  {playing && <span className="absolute inset-0 rounded-full" style={{ background: `radial-gradient(circle, rgba(200,150,62,0.5) 0%, transparent 70%)`, animation: "mpTubeGlow 2.5s ease-in-out infinite" }} />}
                  <span className="relative z-10">
                    {playing ?
                      <svg width="15" height="15" viewBox="0 0 24 24" fill={$.deep}><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> :
                      <svg width="15" height="15" viewBox="0 0 24 24" fill={$.deep}><polygon points="6,3 20,12 6,21"/></svg>}
                  </span>
                </button>
                {/* next */}
                <button onClick={() => {
                  if (mode === "shuffle" && playlist.length > 0) {
                    playSongAtIndex(getShuffleNext());
                    return;
                  }
                  const ni = playIndex + 1;
                  playSongAtIndex(ni >= playlist.length ? 0 : ni);
                }} disabled={mode === "shuffle" ? false : (playIndex >= playlist.length - 1 && mode !== "repeat-all")}
                  className="border-0 cursor-pointer flex items-center justify-center transition-opacity"
                  style={{ width: 28, height: 28, background: "transparent", opacity: (playIndex >= playlist.length - 1 && mode !== "repeat-all" && mode !== "shuffle") ? 0.2 : 0.5 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2"><polygon points="5,5 15,12 5,19"/><line x1="19" y1="5" x2="19" y2="19"/></svg>
                </button>
                {/* metadata */}
                <div className="flex-1 min-w-0 ml-1">
                  <p className="truncate" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 14, fontWeight: 600, letterSpacing: "0.03em", color: $.fg, lineHeight: 1.2 }}>{current.title}</p>
                  <p className="text-[11px] truncate" style={{ color: $.sub }}>{current.artist}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: $.sub, fontFamily: "'JetBrains Mono', monospace" }}>{fmt(position)} / {duration > 0 ? fmt(duration) : fmt(current.duration)}</p>
                </div>
                {/* heart */}
                <button onClick={(e) => toggleFavorite(current, e)}
                  className="border-0 cursor-pointer text-lg transition-all hover:scale-125 flex-shrink-0"
                  style={{ background: "transparent", color: favoriteIds.has(current.id) ? "#e8816e" : $.sub, opacity: favoriteIds.has(current.id) ? 1 : 0.4 }}>
                  {favoriteIds.has(current.id) ? "♥" : "♡"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* keyframes */}
      <style>{`
        @keyframes mpPanelIn { from { opacity:0; transform:translateY(12px) scale(0.96); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes mpBreath {
          0%,100% { transform: scale(1); }
          50% { transform: scale(1.03); }
        }
        @keyframes mpVinyl {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes mpThump {
          0% { opacity: 0.5; transform: scale(0.85); }
          100% { opacity: 0; transform: scale(1.25); }
        }
        @keyframes mpTubeGlow {
          0%,100% { opacity: 0.3; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </>, document.body
  );

}
