import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { compile } from "../api/compile";

function splitScenes(md: string): { title: string; body: string[] }[] {
  // Only split at chapter markers like "## 第 N 幕"; scene content may contain
  // sub-headings which must not create extra blank pages.
  const parts = md.split(/^(?=## 第\s*\d)/m);
  return parts
    .map(part => {
      const lines = part.trim().split("\n");
      const firstLine = lines[0] || "";
      if (!firstLine.startsWith("## ")) return null;
      const title = firstLine.replace(/^##\s+/, "");
      const bodyText = lines.slice(1).join("\n")
        .replace(/^---$/gm, "")
        .replace(/^#{1,6}\s+.+$/gm, "")
        .trim();
      const body = bodyText.split("\n\n").filter(Boolean).map(p => p.trim()).filter(Boolean);
      return { title, body };
    })
    .filter((s): s is { title: string; body: string[] } => s !== null && s.body.length > 0);
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
      <div className="flex-1 overflow-auto px-8">
        <div className="max-w-xl w-full mx-auto py-10">
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
