import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";

/* ═══════════════════════════════════════════════════════════
   MusicPlayer — 本地文件播放器
   用户选择本地音乐文件夹，浏览器直接读取播放。
   收藏存 localStorage，目录句柄存 IndexedDB。
   ═══════════════════════════════════════════════════════════ */

type Tab = "playlist" | "favorites";
type PlayMode = "sequential" | "shuffle" | "repeat-one" | "repeat-all";

interface LocalSong {
  id: string;
  fileName: string;
  title: string;
  artist: string;
  duration: number;
}

const AUDIO_EXTS = /\.(mp3|flac|wav|ogg|m4a|aac|wma|opus|webm)$/i;
const FAV_KEY = "mp_local_favorites";
const DB_NAME = "mp_dir_store";
const DB_VERSION = 1;
const STORE_NAME = "handles";

/* ── 文件名解析 ── */
function parseFileName(fileName: string): { title: string; artist: string } {
  const stem = fileName.replace(AUDIO_EXTS, "");
  // "歌手 - 歌名" 格式
  const dashIdx = stem.indexOf(" - ");
  if (dashIdx > 0) {
    return {
      artist: stem.slice(0, dashIdx).trim(),
      title: stem.slice(dashIdx + 3).trim(),
    };
  }
  // "歌手-歌名" (无空格)
  const tightDash = stem.indexOf("-");
  if (tightDash > 0 && tightDash < stem.length - 1) {
    return {
      artist: stem.slice(0, tightDash).trim(),
      title: stem.slice(tightDash + 1).trim(),
    };
  }
  return { title: stem.trim(), artist: "未知歌手" };
}

/* ── 简单 hash（文件名 → id） ── */
function hashStr(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  }
  return "L" + Math.abs(h).toString(36);
}

/* ── localStorage 收藏 ── */
function loadFavorites(): LocalSong[] {
  try { return JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); } catch { return []; }
}
function saveFavorites(songs: LocalSong[]): void {
  localStorage.setItem(FAV_KEY, JSON.stringify(songs));
}

/* ── IndexedDB 目录句柄持久化 ── */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => { req.result.createObjectStore(STORE_NAME); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function saveDirHandle(handle: FileSystemDirectoryHandle): Promise<void> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(handle, "dir");
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch { /* IndexedDB 不可用 */ }
}

async function loadDirHandle(): Promise<FileSystemDirectoryHandle | null> {
  try {
    const db = await openDB();
    const handle = await new Promise<any>((resolve) => {
      const req = db.transaction(STORE_NAME).objectStore(STORE_NAME).get("dir");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    });
    db.close();
    // 校验权限
    if (handle && typeof handle.queryPermission === "function") {
      const perm = await handle.queryPermission({ mode: "read" });
      if (perm === "granted") return handle;
      const reqPerm = await handle.requestPermission({ mode: "read" });
      if (reqPerm === "granted") return handle;
    }
    return null;
  } catch { return null; }
}

/* ── 检测 File System Access API ── */
function hasDirPicker(): boolean {
  return typeof window !== "undefined" && "showDirectoryPicker" in window;
}

export function MusicPlayer() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("playlist");
  const [playlist, setPlaylist] = useState<LocalSong[]>([]);
  const [favorites, setFavorites] = useState<LocalSong[]>(() => loadFavorites());
  const [dirName, setDirName] = useState("");
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<LocalSong | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const [playIndex, setPlayIndex] = useState(-1);
  const [mode, setMode] = useState<PlayMode>("sequential");

  /* ── refs（避免 stale closure） ── */
  const playlistRef = useRef<LocalSong[]>([]);
  const playIndexRef = useRef(-1);
  const modeRef = useRef<PlayMode>("sequential");
  const currentRef = useRef<LocalSong | null>(null);
  const fileHandlesRef = useRef<Map<string, FileSystemFileHandle>>(new Map());
  const dirHandleRef = useRef<FileSystemDirectoryHandle | null>(null);
  useEffect(() => { playlistRef.current = playlist; }, [playlist]);
  useEffect(() => { playIndexRef.current = playIndex; }, [playIndex]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { currentRef.current = current; }, [current]);

  /* ── 可拖拽迷你播放器 ── */
  const miniRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 });
  const [miniPos, setMiniPos] = useState<{ x: number; y: number } | null>(() => {
    try { return JSON.parse(localStorage.getItem("mp_mini_pos") || "null"); } catch { return null; }
  });

  /* ── 节拍分析 ── */
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const [beat, setBeat] = useState(0);
  const [duration, setDuration] = useState(0);
  const [position, setPosition] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const onTrackEndRef = useRef<() => void>(() => {});
  const panelRef = useRef<HTMLDivElement | null>(null);
  const tickRef = useRef(0);
  const blobUrlRef = useRef<string | null>(null);

  /* ── 洗牌队列 ── */
  const shuffleOrderRef = useRef<number[]>([]);
  const shufflePosRef = useRef(-1);

  /* ── audio 元素 ── */
  function audio(): HTMLAudioElement {
    if (!audioRef.current) {
      const a = new Audio();
      a.volume = 0.72; a.preload = "auto";
      a.addEventListener("timeupdate", () => setPosition(a.currentTime));
      a.addEventListener("loadedmetadata", () => setDuration(a.duration || 0));
      a.addEventListener("error", () => { setError(a.error ? `code ${a.error.code}` : "无法播放"); setPlaying(false); });
      a.addEventListener("ended", () => onTrackEnd());
      a.addEventListener("play", () => { setPlaying(true); setError(""); });
      a.addEventListener("pause", () => { if (!a.ended) setPlaying(false); });
      audioRef.current = a;
    }
    return audioRef.current;
  }

  /* ── onTrackEnd ── */
  onTrackEndRef.current = () => {
    setPlaying(false); setPosition(0);
    const m = modeRef.current;
    const pl = playlistRef.current;
    const idx = playIndexRef.current;
    if (m === "repeat-one") { audio().currentTime = 0; audio().play().catch(() => {}); return; }
    if (pl.length === 0) return;
    if (m === "shuffle") { playShuffleNext(); return; }
    const next = idx + 1;
    playAtIndex(next >= pl.length ? 0 : next);
  };
  function onTrackEnd() { onTrackEndRef.current(); }

  /* ── 洗牌 ── */
  function buildShuffle(listLen: number, startIdx: number) {
    const order = Array.from({ length: listLen }, (_, i) => i).filter(i => i !== startIdx);
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    shuffleOrderRef.current = [startIdx, ...order];
    shufflePosRef.current = 0;
  }

  function playShuffleNext() {
    const order = shuffleOrderRef.current;
    let pos = shufflePosRef.current + 1;
    if (pos >= order.length) {
      const currentIdx = order[0];
      const newOrder = Array.from({ length: order.length }, (_, i) => i).filter(i => i !== currentIdx);
      for (let i = newOrder.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [newOrder[i], newOrder[j]] = [newOrder[j], newOrder[i]];
      }
      shuffleOrderRef.current = [currentIdx, ...newOrder];
      pos = 1;
    }
    shufflePosRef.current = pos;
    playAtIndex(order[pos]);
  }

  function playShufflePrev() {
    const pos = shufflePosRef.current - 1;
    if (pos < 0) return;
    shufflePosRef.current = pos;
    playAtIndex(shuffleOrderRef.current[pos]);
  }

  /* ── 播放 ── */
  async function playSong(song: LocalSong, sourceList?: LocalSong[]) {
    const a = audio(); setError(""); setPosition(0); setDuration(0);
    audioCtxRef.current?.resume().catch(() => {});

    // 释放旧 blob URL
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null; }

    const handle = fileHandlesRef.current.get(song.id);
    if (handle) {
      try {
        const file = await handle.getFile();
        const url = URL.createObjectURL(file);
        blobUrlRef.current = url;
        a.src = url;
      } catch {
        setError("无法读取文件"); return;
      }
    } else {
      setError("文件句柄丢失，请重新选择文件夹"); return;
    }

    a.play().then(() => setPlaying(true)).catch(e => setError(e.message || "无法播放"));
    setCurrent(song);
    if (sourceList && sourceList.length > 0) {
      setPlaylist(sourceList);
      const idx = sourceList.findIndex(s => s.id === song.id);
      if (mode === "shuffle") buildShuffle(sourceList.length, idx >= 0 ? idx : 0);
      setPlayIndex(idx >= 0 ? idx : 0);
    } else {
      setPlaylist(p => {
        const idx = p.findIndex(s => s.id === song.id);
        if (idx >= 0) { setPlayIndex(idx); return p; }
        setPlayIndex(p.length);
        return [...p, song];
      });
    }
  }

  function playAtIndex(i: number) {
    if (i < 0 || i >= playlistRef.current.length) return;
    playSong(playlistRef.current[i], playlistRef.current);
  }

  /* ── 选择文件夹 ── */
  async function selectFolder() {
    setError("");
    if (hasDirPicker()) {
      try {
        const handle = await window.showDirectoryPicker({ mode: "read" });
        await scanDir(handle);
        await saveDirHandle(handle);
        dirHandleRef.current = handle;
      } catch (e: any) {
        if (e.name !== "AbortError") setError("无法访问文件夹");
      }
    } else {
      // 移动端 fallback：触发隐藏的 file input
      document.getElementById("mp_file_input")?.click();
    }
  }

  async function scanDir(handle: FileSystemDirectoryHandle) {
    setLoading(true);
    fileHandlesRef.current.clear();
    const songs: LocalSong[] = [];
    setDirName(handle.name);

    for await (const [name, entry] of (handle as any).entries()) {
      if (entry.kind === "file" && AUDIO_EXTS.test(name)) {
        const fileHandle = entry as FileSystemFileHandle;
        const { title, artist } = parseFileName(name);
        const song: LocalSong = {
          id: hashStr(name),
          fileName: name,
          title,
          artist,
          duration: 0,
        };
        songs.push(song);
        fileHandlesRef.current.set(song.id, fileHandle);
      }
    }
    // 递归扫描一层子目录
    for await (const [name, entry] of (handle as any).entries()) {
      if (entry.kind === "directory") {
        try {
          for await (const [subName, subEntry] of (entry as any).entries()) {
            if (subEntry.kind === "file" && AUDIO_EXTS.test(subName)) {
              const fileHandle = subEntry as FileSystemFileHandle;
              const { title, artist } = parseFileName(subName);
              const song: LocalSong = {
                id: hashStr(subName),
                fileName: `${name}/${subName}`,
                title,
                artist,
                duration: 0,
              };
              songs.push(song);
              fileHandlesRef.current.set(song.id, fileHandle);
            }
          }
        } catch { /* 跳过无权限子目录 */ }
      }
    }
    songs.sort((a, b) => a.fileName.localeCompare(b.fileName));
    setPlaylist(songs);
    setLoading(false);
  }

  /* ── 多文件 fallback（移动端） ── */
  async function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setLoading(true);
    fileHandlesRef.current.clear();
    const songs: LocalSong[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (!AUDIO_EXTS.test(f.name)) continue;
      const { title, artist } = parseFileName(f.name);
      const song: LocalSong = {
        id: hashStr(f.name + f.size),
        fileName: f.name,
        title,
        artist,
        duration: 0,
      };
      songs.push(song);
      // 用临时 URL 存储文件引用
      const url = URL.createObjectURL(f);
      fileHandlesRef.current.set(song.id, { getFile: async () => f } as any);
    }
    songs.sort((a, b) => a.fileName.localeCompare(b.fileName));
    setPlaylist(songs);
    setDirName(`${files.length} 个文件`);
    setLoading(false);
    e.target.value = ""; // 允许重复选择同一批文件
  }

  /* ── 启动时恢复目录 ── */
  useEffect(() => {
    loadDirHandle().then(handle => {
      if (handle) {
        dirHandleRef.current = handle;
        scanDir(handle);
      }
    });
  }, []);

  /* ── 收藏 ── */
  const isFav = useCallback((id: string) => favorites.some(s => s.id === id), [favorites]);

  function toggleFavorite(song: LocalSong, e?: React.MouseEvent) {
    e?.stopPropagation();
    setFavorites(p => {
      if (p.some(s => s.id === song.id)) {
        const next = p.filter(s => s.id !== song.id);
        saveFavorites(next);
        return next;
      }
      const next = [{ ...song, duration: 0 }, ...p];
      saveFavorites(next);
      return next;
    });
  }

  /* ── 播放控制 ── */
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
      const lowSum = data.slice(0, 16).reduce((s, v) => s + v, 0) / 16;
      setBeat(Math.min(1, lowSum / 180));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  /* ── 拖拽 ── */
  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      const d = dragRef.current;
      if (!d.dragging) return;
      const p = "touches" in e ? e.touches[0] : e;
      const nx = d.origX + (p.clientX - d.startX);
      const ny = d.origY + (p.clientY - d.startY);
      setMiniPos({ x: Math.max(0, Math.min(nx, window.innerWidth - 52)), y: Math.max(0, Math.min(ny, window.innerHeight - 52)) });
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
    e.stopPropagation(); e.preventDefault();
    const p = "touches" in e ? e.touches[0] : e;
    const pos = miniPos || { x: window.innerWidth - 56, y: window.innerHeight - 56 };
    dragRef.current = { dragging: true, startX: p.clientX, startY: p.clientY, origX: pos.x, origY: pos.y };
  }

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

  /* ── helpers ── */
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

  /* ── 歌曲行 ── */
  function renderSongRow(s: LocalSong, isCurrent: boolean, sourceList?: LocalSong[]) {
    return (
      <button key={s.id} onClick={() => playSong(s, sourceList)}
        className="w-full flex items-center text-left border-0 cursor-pointer rounded-xl transition-all duration-200"
        style={{ gap: 12, padding: "10px 12px", background: isCurrent ? "rgba(200,150,62,0.06)" : "transparent" }}
        onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = $.surface; }}
        onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.background = "transparent"; }}>
        <div className="flex-shrink-0 rounded-lg overflow-hidden flex items-center justify-center" style={{ width: 42, height: 42, background: "rgba(200,150,62,0.08)", color: $.amber, fontSize: 17 }}>♪</div>
        <div className="flex-1 min-w-0">
          <p className="truncate" style={{ fontSize: 13, fontWeight: isCurrent ? 500 : 400, color: isCurrent ? $.amber : $.fg }}>{s.title}</p>
          <p className="text-[11px] truncate" style={{ color: $.sub }}>{s.artist}{s.fileName !== `${s.artist} - ${s.title}` && s.artist !== "未知歌手" ? "" : s.fileName.includes(" - ") ? "" : ` · ${s.fileName}`}</p>
        </div>
        <div className="flex-shrink-0 flex items-center" style={{ gap: 8 }}>
          {s.duration > 0 && <span className="text-[11px]" style={{ color: $.sub, fontFamily: "'JetBrains Mono', monospace" }}>{fmt(s.duration)}</span>}
          <span onClick={(e) => toggleFavorite(s, e)}
            className="cursor-pointer transition-all text-base hover:scale-125"
            style={{ color: isFav(s.id) ? "#e8816e" : $.sub, opacity: isFav(s.id) ? 1 : 0.3 }}>
            {isFav(s.id) ? "♥" : "♡"}
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
      {/* ═══════════════════════════════ 隐藏文件输入（移动端 fallback） ═══ */}
      <input type="file" id="mp_file_input" multiple accept="audio/*"
        onChange={handleFiles} style={{ display: "none" }} />

      {/* ═══════════════════════════════ 迷你球 ═══ */}
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
              {playing && (
                <span className="absolute inset-0 rounded-full"
                  style={{ background: "radial-gradient(circle, rgba(200,150,62,0.35) 0%, transparent 70%)", animation: "mpThump 0.6s ease-out infinite" }} />
              )}
            </div>
          );
        })()
      )}

      {/* ═══════════════════════════════ 面板 ═══ */}
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
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>

          {/* tabs + 选择文件夹 */}
          <div className="flex-shrink-0 relative z-10 flex items-center px-5 pt-3 pb-1" style={{ gap: 4 }}>
            {(["playlist", "favorites"] as Tab[]).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className="border-0 cursor-pointer rounded-lg px-3.5 py-1.5 text-[12px] font-medium transition-all"
                style={{ background: tab === t ? "rgba(200,150,62,0.1)" : "transparent", color: tab === t ? $.amber : $.sub }}>
                {t === "playlist" ? "播放列表" : "收藏"}
              </button>
            ))}
            <div className="flex-1" />
            <button onClick={selectFolder} disabled={loading}
              className="border-0 cursor-pointer rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all hover:scale-105"
              style={{ background: $.amber, color: $.deep, opacity: loading ? 0.5 : 1 }}>
              {loading ? "扫描中…" : "📁 选择文件夹"}
            </button>
            <button onClick={() => {
              const modes: PlayMode[] = ["sequential", "shuffle", "repeat-all", "repeat-one"];
              const i = modes.indexOf(mode);
              const next = modes[(i + 1) % modes.length];
              setMode(next);
              if (next === "shuffle" && playlist.length > 0) {
                buildShuffle(playlist.length, playIndex >= 0 ? playIndex : 0);
              }
            }}
              className="border-0 cursor-pointer rounded-lg px-2 py-1.5 text-[14px] transition-all"
              style={{ background: mode !== "sequential" ? "rgba(200,150,62,0.1)" : "transparent", color: mode !== "sequential" ? $.amber : $.sub }}
              title={mode === "shuffle" ? "随机播放" : mode === "repeat-one" ? "单曲循环" : mode === "repeat-all" ? "列表循环" : "顺序播放"}>
              {modeIcon()}
            </button>
          </div>

          {/* 文件夹名 */}
          {dirName && tab === "playlist" && (
            <div className="px-5 pt-1 pb-1 flex-shrink-0 relative z-10">
              <p className="text-[11px] truncate" style={{ color: $.sub }}>📂 {dirName} · {playlist.length} 首</p>
            </div>
          )}

          {/* 列表 */}
          <div className="flex-1 overflow-auto px-3 py-1 relative z-10" style={{ scrollBehavior: "smooth" }}>
            {tab === "playlist" && playlist.map(s => renderSongRow(s, current?.id === s.id, playlist))}
            {tab === "favorites" && favorites.map(s => renderSongRow(s, current?.id === s.id, favorites))}

            {!loading && (
              <div className="flex flex-col items-center justify-center py-20" style={{ gap: 4 }}>
                <span style={{ fontSize: 32, opacity: 0.15 }}>♪</span>
                <p className="text-[12px]" style={{ color: $.sub }}>
                  {tab === "playlist" && (playlist.length === 0 ? (hasDirPicker() ? "点击 📁 选择音乐文件夹" : "点击 📁 选择音频文件") : "")}
                  {tab === "favorites" && (favorites.length === 0 ? "播放列表中点 ♡ 收藏歌曲" : "")}
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
                <button onClick={() => {
                  if (mode === "shuffle") { playShufflePrev(); return; }
                  playAtIndex(playIndex - 1);
                }} disabled={mode === "shuffle" ? shufflePosRef.current <= 0 : (playIndex <= 0 && mode !== "repeat-all")}
                  className="border-0 cursor-pointer flex items-center justify-center transition-opacity"
                  style={{ width: 28, height: 28, background: "transparent", opacity: (playIndex <= 0 && mode !== "repeat-all") ? 0.2 : 0.5 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2"><polygon points="19,5 9,12 19,19" /><line x1="5" y1="5" x2="5" y2="19" /></svg>
                </button>
                <button onClick={togglePlay}
                  className="flex-shrink-0 border-0 cursor-pointer rounded-full flex items-center justify-center transition-all duration-300 relative"
                  style={{ width: 44, height: 44, background: `radial-gradient(circle at 40% 40%, ${$.amber}, #8b6914)`,
                    boxShadow: playing ? `0 0 20px rgba(200,150,62,0.5), 0 0 50px rgba(200,150,62,0.08)` : "0 2px 8px rgba(0,0,0,0.3)" }}>
                  {playing && <span className="absolute inset-0 rounded-full" style={{ background: `radial-gradient(circle, rgba(200,150,62,0.5) 0%, transparent 70%)`, animation: "mpTubeGlow 2.5s ease-in-out infinite" }} />}
                  <span className="relative z-10">
                    {playing ?
                      <svg width="15" height="15" viewBox="0 0 24 24" fill={$.deep}><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg> :
                      <svg width="15" height="15" viewBox="0 0 24 24" fill={$.deep}><polygon points="6,3 20,12 6,21" /></svg>}
                  </span>
                </button>
                <button onClick={() => {
                  if (mode === "shuffle" && playlist.length > 0) { playShuffleNext(); return; }
                  const ni = playIndex + 1;
                  playAtIndex(ni >= playlist.length ? 0 : ni);
                }} disabled={mode === "shuffle" ? false : (playIndex >= playlist.length - 1 && mode !== "repeat-all")}
                  className="border-0 cursor-pointer flex items-center justify-center transition-opacity"
                  style={{ width: 28, height: 28, background: "transparent", opacity: (playIndex >= playlist.length - 1 && mode !== "repeat-all" && mode !== "shuffle") ? 0.2 : 0.5 }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={$.sub} strokeWidth="2"><polygon points="5,5 15,12 5,19" /><line x1="19" y1="5" x2="19" y2="19" /></svg>
                </button>
                <div className="flex-1 min-w-0 ml-1">
                  <p className="truncate" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: 14, fontWeight: 600, letterSpacing: "0.03em", color: $.fg, lineHeight: 1.2 }}>{current.title}</p>
                  <p className="text-[11px] truncate" style={{ color: $.sub }}>{current.artist}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: $.sub, fontFamily: "'JetBrains Mono', monospace" }}>{fmt(position)} / {duration > 0 ? fmt(duration) : "?"}</p>
                </div>
                <button onClick={(e) => toggleFavorite(current, e)}
                  className="border-0 cursor-pointer text-lg transition-all hover:scale-125 flex-shrink-0"
                  style={{ background: "transparent", color: isFav(current.id) ? "#e8816e" : $.sub, opacity: isFav(current.id) ? 1 : 0.4 }}>
                  {isFav(current.id) ? "♥" : "♡"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* keyframes */}
      <style>{`
        @keyframes mpPanelIn { from { opacity:0; transform:translateY(12px) scale(0.96); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes mpBreath { 0%,100% { transform: scale(1); } 50% { transform: scale(1.03); } }
        @keyframes mpVinyl { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes mpThump { 0% { opacity: 0.5; transform: scale(0.85); } 100% { opacity: 0; transform: scale(1.25); } }
        @keyframes mpTubeGlow { 0%,100% { opacity: 0.3; } 50% { opacity: 0.6; } }
        @keyframes mpBar1 { 0%,100% { height: 5px; } 50% { height: 13px; } }
        @keyframes mpBar2 { 0%,100% { height: 11px; } 50% { height: 4px; } }
        @keyframes mpBar3 { 0%,100% { height: 3px; } 50% { height: 10px; } }
      `}</style>
    </>, document.body
  );
}
