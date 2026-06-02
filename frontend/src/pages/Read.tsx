import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { Modal } from "../components/ui/Modal";
import { compile } from "../api/compile";
import { getScenes, deleteScene, rewriteScene } from "../api/entities";
import { useGeneration } from "../GenerationContext";
import { PageHelp } from "../components/PageHelp";

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
  const [confirmAction, setConfirmAction] = useState<null | { type: "delete" | "rewrite"; sceneId: string; sceneTitle: string }>(null);
  const [processing, setProcessing] = useState(false);
  const [toast, setToast] = useState<null | { type: "success" | "error"; text: string }>(null);
  const queryClient = useQueryClient();
  const { startSSE, session } = useGeneration();
  const isGenerating = session?.running ?? false;

  const { data, isLoading } = useQuery({
    queryKey: ["read", id],
    queryFn: () => compile(id!, { format: "markdown" }),
    enabled: !!id,
  });

  const { data: scenesData } = useQuery({
    queryKey: ["scenes", id],
    queryFn: () => getScenes(id!),
    enabled: !!id,
  });

  useEffect(() => { setPage(0); }, [id]);

  const scenes = data?.content ? splitScenes(data.content) : [];
  const sceneList = scenesData?.scenes ?? [];
  const currentSceneMeta = sceneList[page];
  // Only the latest chapter can be rewritten or deleted
  const isLatest = scenes.length > 0 && page === scenes.length - 1;

  const goPrev = useCallback(() => setPage(p => Math.max(0, p - 1)), []);
  const goNext = useCallback(() => { if (scenes.length > 0) setPage(p => Math.min(scenes.length - 1, p + 1)); }, [scenes.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goPrev, goNext]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  const handleDelete = useCallback(async () => {
    if (!confirmAction || !id || processing) return;
    setProcessing(true);
    setConfirmAction(null);
    try {
      await deleteScene(id, confirmAction.sceneId);
      setToast({ type: "success", text: `已删除「${confirmAction.sceneTitle}」` });
      queryClient.invalidateQueries({ queryKey: ["read", id] });
      queryClient.invalidateQueries({ queryKey: ["scenes", id] });
      setPage(p => Math.max(0, p - 1));
    } catch (e: any) {
      setToast({ type: "error", text: `删除失败: ${e?.message ?? e}` });
    } finally {
      setProcessing(false);
    }
  }, [confirmAction, id, processing, queryClient]);

  const handleRewrite = useCallback(async () => {
    if (!confirmAction || !id || processing) return;
    setProcessing(true);
    setConfirmAction(null);
    try {
      await rewriteScene(id, confirmAction.sceneId);
      queryClient.invalidateQueries({ queryKey: ["read", id] });
      queryClient.invalidateQueries({ queryKey: ["scenes", id] });
      setToast({ type: "success", text: `已回滚「${confirmAction.sceneTitle}」，正在重新生成…` });
      // Auto-trigger regeneration for this chapter
      startSSE(id, 1, {});
    } catch (e: any) {
      setToast({ type: "error", text: `重写失败: ${e?.message ?? e}` });
    } finally {
      setProcessing(false);
    }
  }, [confirmAction, id, processing, queryClient, startSSE]);

  if (isLoading) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (!data?.content) return <p className="text-sm py-24 text-center" style={{ color: "var(--text-2)" }}>暂无内容，先生成一些章节</p>;

  const s = scenes[page];
  if (!s) return null;

  return (
    <div className="h-full flex flex-col" style={{ fontFamily: "Georgia, 'Noto Serif SC', 'Source Han Serif SC', serif" }}>
      <PageHelp>阅读模式 — 翻页阅读已生成的章节。使用 ← → 方向键翻页。翻到最新章可点击「重写」或「删除」按钮管理场景。</PageHelp>
      {/* page area */}
      <div className="flex-1 overflow-auto px-4 md:px-8">
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
      <div className="flex items-center justify-between px-3 md:px-6 py-3 md:py-4 flex-shrink-0 gap-2 flex-wrap"
        style={{ borderTop: "1px solid var(--border)", background: "var(--bg-surface)" }}>
        <button onClick={goPrev} disabled={page === 0}
          className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-20"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
          ← 上一章
        </button>

        <div className="flex items-center gap-3">
          <span className="text-sm tabular-nums" style={{ color: "var(--text-3)" }}>
            {page + 1} / {scenes.length}
          </span>

          {/* Only show on latest chapter; disable during generation */}
          {currentSceneMeta && isLatest && (
            <>
              <button
                onClick={() => setConfirmAction({ type: "rewrite", sceneId: "S" + currentSceneMeta.number, sceneTitle: s.title })}
                disabled={processing || isGenerating}
                className="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-30"
                style={{ color: "var(--text-3)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}
                title={isGenerating ? "生成中，请等待完成" : "回滚到最新幕，重新生成"}>
                🔄 重写
              </button>
              <button
                onClick={() => setConfirmAction({ type: "delete", sceneId: "S" + currentSceneMeta.number, sceneTitle: s.title })}
                disabled={processing || isGenerating}
                className="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-30"
                style={{ color: "#e88c8c", background: "var(--bg-raised)", border: "1px solid rgba(200,80,80,0.3)" }}
                title={isGenerating ? "生成中，请等待完成" : "永久删除最新幕"}>
                🗑 删除
              </button>
            </>
          )}
        </div>

        <button onClick={goNext} disabled={page >= scenes.length - 1}
          className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-20"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
          下一章 →
        </button>
      </div>

      {/* Confirmation Modal */}
      <Modal
        open={!!confirmAction}
        title={confirmAction?.type === "delete" ? "确认删除" : "确认重写"}
        onClose={() => { if (!processing) setConfirmAction(null); }}
      >
        <div className="p-6">
          <p className="text-sm mb-2" style={{ color: "var(--text-2)" }}>
            {confirmAction?.type === "delete"
              ? "永久删除此场景（包括正文、元数据和计划）。此操作不可撤销。"
              : "回滚到最新幕，删除最新幕内容。备份已自动保存，将立即重新生成。"}
          </p>
          <p className="text-sm font-semibold mb-6" style={{ color: "var(--text-1)" }}>
            「{confirmAction?.sceneTitle}」
          </p>
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setConfirmAction(null)}
              disabled={processing}
              className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-30"
              style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
              取消
            </button>
            <button
              onClick={confirmAction?.type === "delete" ? handleDelete : handleRewrite}
              disabled={processing}
              className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-30"
              style={{
                color: "#fff",
                background: confirmAction?.type === "delete" ? "#b91c1c" : "#c8975a",
                border: "1px solid transparent",
              }}>
              {processing ? "处理中…" : confirmAction?.type === "delete" ? "确认删除" : "确认重写"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm shadow-lg animate-fade-in"
          style={{
            color: "#fff",
            background: toast.type === "success" ? "rgba(34,120,60,0.92)" : "rgba(180,40,40,0.92)",
            backdropFilter: "blur(8px)",
          }}>
          {toast.text}
        </div>
      )}
    </div>
  );
}
