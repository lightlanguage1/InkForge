import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getChatMessages, postChatMessage, getOnlineCount } from "../../api/community";

export function ChatColumn({ projectId }: { projectId?: string }) {
  const { data, refetch } = useQuery({
    queryKey: ["chat", projectId || "_global"],
    queryFn: () => getChatMessages(projectId, 0),
    refetchInterval: 15000,
  });
  const { data: onlineData } = useQuery({
    queryKey: ["online"],
    queryFn: getOnlineCount,
    refetchInterval: 30000,
  });
  const messages = data?.messages ?? [];
  const onlineCount = onlineData?.online ?? 0;
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const channelName = projectId ? "频道聊天" : "沙龙茶话会";
  const subtitle = projectId ? "本作品专属聊天频道" : `${onlineCount} 人在线 · 15 秒刷新`;

  return (
    <div className="hidden lg:flex w-80 flex-shrink-0 flex-col"
      style={{ background: "var(--bg-surface)", borderLeft: "1px solid var(--border)" }}>
      <div className="p-4" style={{ borderBottom: "1px solid rgba(200,151,90,0.08)" }}>
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-semibold text-sm flex items-center gap-2" style={{ color: "#d4c4a8" }}>
            💬 {channelName}
          </h3>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: onlineCount > 0 ? "#4daa85" : "#666" }} />
            <span className="text-[10px] font-mono" style={{ color: "var(--text-3)" }}>{onlineCount} 在线</span>
          </span>
        </div>
        <p className="text-[10px]" style={{ color: "rgba(180,160,140,0.25)" }}>{subtitle}</p>
      </div>
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="text-3xl mb-3 opacity-20">🍵</div>
            <p className="text-xs leading-relaxed" style={{ color: "rgba(180,160,140,0.3)" }}>
              茶已备好，静候第一位茶客<br />写下第一句问候吧
            </p>
          </div>
        )}
        {messages.map((m: any) => (
          <div key={m.id} className="group">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[11px] font-semibold" style={{ color: "#c8a878" }}>
                @{m.display_name || m.user_id?.slice(0, 8)}
              </span>
              <span className="text-[9px] font-mono opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: "rgba(180,160,140,0.2)" }}>
                {m.created_at?.slice(11, 16)}
              </span>
            </div>
            <p className="text-xs leading-relaxed mt-0.5" style={{ color: "#b0a080" }}>{m.message}</p>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSent={refetch} projectId={projectId} />
    </div>
  );
}

function ChatInput({ onSent, projectId }: { onSent: () => void; projectId?: string }) {
  const [txt, setTxt] = useState("");
  const send = async () => {
    if (!txt.trim() || txt.length > 2000) return;
    try { await postChatMessage(txt, projectId); setTxt(""); onSent(); } catch { }
  };
  return (
    <div className="p-3" style={{ borderTop: "1px solid rgba(200,151,90,0.08)" }}>
      <textarea value={txt} onChange={e => setTxt(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        placeholder="参与讨论… (Enter 发送)"
        rows={2}
        className="w-full text-xs px-3 py-2.5 rounded-lg outline-none resize-none transition-all focus:ring-1"
        style={{ background: "rgba(10,8,16,0.5)", border: "1px solid rgba(200,151,90,0.1)", color: "#c0b090" }} />
      <div className="flex justify-between items-center mt-2">
        <span className="text-[10px]" style={{ color: "rgba(180,160,140,0.2)" }}>{txt.length}/2000</span>
        <button onClick={send}
          className="text-xs px-5 py-1.5 rounded-full font-medium transition-opacity disabled:opacity-30"
          style={{ background: "var(--accent)", color: "var(--bg-base)" }}
          disabled={!txt.trim()}>发送</button>
      </div>
    </div>
  );
}
