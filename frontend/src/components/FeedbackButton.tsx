import { useState } from "react";
import { createPortal } from "react-dom";
import { submitFeedback } from "../api/feedback";

export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("建议");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit() {
    if (!title.trim() || !content.trim()) return;
    setSending(true);
    try {
      await submitFeedback(title, content, category);
      setDone(true);
      setTimeout(() => { setOpen(false); setDone(false); setTitle(""); setContent(""); setCategory("建议"); }, 1500);
    } catch { /* silent */ }
    setSending(false);
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed right-5 bottom-28 z-[9999] w-10 h-10 rounded-full flex items-center justify-center
                   shadow-lg hover:scale-110 transition-all duration-200 text-lg"
        style={{ background: "var(--accent)", color: "var(--bg-base)", border: "none", cursor: "pointer" }}
        title="反馈建议">
        💬
      </button>

      {/* Modal via portal */}
      {open && createPortal(
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          onClick={e => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div className="rounded-2xl w-full max-w-md overflow-hidden shadow-2xl"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            {/* header */}
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--border)" }}>
              <h3 className="font-semibold" style={{ fontSize: 15, color: "var(--text-1)" }}>
                {done ? "✅ 感谢反馈！" : "💬 反馈建议"}
              </h3>
              <button onClick={() => setOpen(false)}
                className="text-lg opacity-40 hover:opacity-70"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-3)" }}>✕</button>
            </div>

            {!done && (
              <>
                <div className="p-5 flex flex-col gap-3">
                  <div className="flex gap-2">
                    {["建议", "问题", "其他"].map(c => (
                      <button key={c} onClick={() => setCategory(c)}
                        className="text-[11px] px-3 py-1 rounded-full transition-all"
                        style={{
                          background: category === c ? "var(--accent)" : "transparent",
                          color: category === c ? "var(--bg-base)" : "var(--text-3)",
                          border: category === c ? "none" : "1px solid var(--border)",
                          cursor: "pointer",
                        }}>{c}</button>
                    ))}
                  </div>
                  <input value={title} onChange={e => setTitle(e.target.value)}
                    placeholder="一句话描述你的想法"
                    className="w-full text-[13px] px-3 py-2.5 rounded-xl outline-none"
                    style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)" }}
                    onFocus={e => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                    onBlur={e => { e.currentTarget.style.borderColor = "var(--border)"; }} />
                  <textarea value={content} onChange={e => setContent(e.target.value)}
                    placeholder="详细说明…"
                    rows={5}
                    className="w-full text-[13px] px-3 py-2.5 rounded-xl outline-none resize-none"
                    style={{ background: "var(--bg-raised)", border: "1px solid var(--border)", color: "var(--text-1)" }}
                    onFocus={e => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                    onBlur={e => { e.currentTarget.style.borderColor = "var(--border)"; }} />
                </div>
                <div className="px-5 pb-4">
                  <button onClick={handleSubmit} disabled={sending || !title.trim() || !content.trim()}
                    className="w-full py-2.5 rounded-xl text-[13px] font-medium transition-all"
                    style={{
                      background: (title.trim() && content.trim()) ? "var(--accent)" : "var(--border)",
                      color: (title.trim() && content.trim()) ? "var(--bg-base)" : "var(--text-3)",
                      cursor: (title.trim() && content.trim()) ? "pointer" : "default",
                      border: "none",
                    }}>
                    {sending ? "提交中…" : "提交反馈"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>, document.body)}
    </>
  );
}
