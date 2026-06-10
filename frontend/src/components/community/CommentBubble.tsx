import { useState } from "react";
import { editComment, deleteComment } from "../../api/community";

export function CommentBubble({ comment, onUpdated }: { comment: any; onUpdated: () => void }) {
  const [editing, setEditing] = useState(false);
  const [txt, setTxt] = useState(comment.content);
  const myId = localStorage.getItem("inkforge_user_id") || "";

  const save = async () => {
    if (!txt.trim()) return;
    try { await editComment(comment.id, txt); setEditing(false); onUpdated(); } catch { }
  };
  const del = async () => {
    if (!confirm("删除这条评论？")) return;
    try { await deleteComment(comment.id); onUpdated(); } catch { }
  };

  return (
    <div className="py-1.5 group/comment">
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] font-medium" style={{ color: "#c8a878" }}>
          @{comment.display_name || comment.user_id?.slice(0, 8)}
        </span>
        <span className="text-[9px] font-mono opacity-40" style={{ color: "rgba(180,160,140,0.3)" }}>
          {comment.created_at?.replace("T", " ").slice(5, 16)}
        </span>
      </div>
      {editing ? (
        <div className="flex gap-2 mt-1">
          <input value={txt} onChange={e => setTxt(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
            className="flex-1 text-[11px] px-2 py-1 rounded outline-none"
            style={{ background: "rgba(10,8,16,0.4)", border: "1px solid rgba(200,151,90,0.15)", color: "#c0b090" }} />
          <button onClick={save} className="text-[10px] px-2 py-1 rounded border-0 cursor-pointer"
            style={{ background: "var(--accent)", color: "var(--bg-base)" }}>保存</button>
        </div>
      ) : (
        <p className="text-[11px] leading-relaxed" style={{ color: "#b0a080" }}>{comment.content}</p>
      )}
      {myId === comment.user_id && !editing && (
        <div className="flex gap-3 mt-0.5 opacity-0 group-hover/comment:opacity-100 transition-opacity">
          <button onClick={() => { setTxt(comment.content); setEditing(true); }}
            className="text-[9px] border-0 cursor-pointer" style={{ background: "transparent", color: "rgba(180,160,140,0.3)" }}>编辑</button>
          <button onClick={del}
            className="text-[9px] border-0 cursor-pointer" style={{ background: "transparent", color: "rgba(220,120,100,0.3)" }}>删除</button>
        </div>
      )}
    </div>
  );
}
