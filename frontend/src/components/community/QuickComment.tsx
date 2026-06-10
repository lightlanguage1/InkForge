import { useState } from "react";
import { addComment } from "../../api/community";

export function QuickComment({ tick, paragraph, projectId, onSent, parentId, placeholder }: {
  tick: number; paragraph?: number; projectId: string; onSent: () => void;
  parentId?: number; placeholder?: string;
}) {
  const [txt, setTxt] = useState("");
  const send = async () => {
    if (!txt.trim()) return;
    try {
      await addComment(projectId, { content: txt, chapter_tick: tick, paragraph: paragraph, parent_id: parentId });
      setTxt(""); onSent();
    } catch { }
  };
  return (
    <div className="flex gap-2">
      <input value={txt} onChange={e => setTxt(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); send(); } }}
        placeholder={placeholder || "写评论…"}
        className="flex-1 text-[11px] px-3 py-2 rounded-lg outline-none"
        style={{ background: "rgba(10,8,16,0.4)", border: "1px solid rgba(200,151,90,0.08)", color: "#c0b090" }} />
      <button onClick={send}
        className="text-[11px] px-3 py-2 rounded-lg font-medium border-0 cursor-pointer"
        style={{ background: "var(--accent)", color: "var(--bg-base)" }}>发送</button>
    </div>
  );
}
