import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { compile } from "../api/compile";

function splitScenes(md: string): { title: string; body: string[] }[] {
  return md.split(/(?=^#{1,3}\s)/m).map(scene => {
    const lines = scene.trim().split("\n");
    const title = (lines[0] || "").replace(/^#{1,3}\s+/, "");
    const body = lines.slice(1).join("\n").trim().split("\n\n").filter(Boolean).map(p => p.trim());
    return { title, body };
  }).filter(s => s.body.length > 0 || s.title);
}

export function ReadPage() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["read", id],
    queryFn: () => compile(id!, { format: "markdown" }),
    enabled: !!id,
  });

  useEffect(() => { setPage(0); }, [id]);

  const goPrev = useCallback(() => setPage(p => Math.max(0, p - 1)), []);
  const goNext = useCallback(() => { if (data) setPage(p => Math.min(scenes.length - 1, p + 1)); }, [data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goPrev, goNext]);

  if (isLoading) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (!data?.content) return <p className="text-sm py-24 text-center" style={{ color: "var(--text-2)" }}>暂无内容，先生成一些章节</p>;

  const scenes = splitScenes(data.content);
  const s = scenes[page];
  if (!s) return null;

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "Georgia, 'Noto Serif SC', 'Source Han Serif SC', serif" }}>
      {/* page area */}
      <div className="flex-1 flex items-center justify-center px-8 overflow-auto">
        <div className="max-w-xl w-full">
          {s.title && (
            <h2 className="text-xl font-bold mb-8 text-center tracking-wide"
              style={{ color: "var(--accent)", letterSpacing: "0.06em" }}>
              {s.title}
            </h2>
          )}
          {s.body.map((para, j) => (
            <p key={j} className="mb-5 leading-loose text-justify"
              style={{ color: "var(--text-1)", fontSize: "1.05rem", lineHeight: 2, textIndent: "2em" }}>
              {para}
            </p>
          ))}
        </div>
      </div>

      {/* navigation bar */}
      <div className="flex items-center justify-between px-6 py-4 flex-shrink-0"
        style={{ borderTop: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <button onClick={goPrev} disabled={page === 0}
          className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-20"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
          ← 上一章
        </button>

        <span className="text-sm tabular-nums" style={{ color: "var(--text-3)" }}>
          {page + 1} / {scenes.length}
        </span>

        <button onClick={goNext} disabled={page >= scenes.length - 1}
          className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-20"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
          下一章 →
        </button>
      </div>
    </div>
  );
}
