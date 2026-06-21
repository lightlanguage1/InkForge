import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listPosts } from "../../api/community";
import { getCoverUrl } from "../../api/projects";
import { Spinner } from "../../components/ui/Spinner";
import { ChatColumn } from "../../components/community/ChatColumn";

export function CommunityPage() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["communityPosts"], queryFn: listPosts });
  const posts = data?.posts ?? [];
  const tabs = ["发现", "最新", "热门"] as const;
  const [tab, setTab] = useState<string>("发现");
  const [showChat, setShowChat] = useState(false);

  return (
    <div className="h-screen flex flex-col" style={{ background: "var(--bg-base)" }}>
      <header className="flex-shrink-0 px-4 md:px-6 py-3 md:py-4 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-5">
          <button onClick={() => navigate(-1)}
            className="text-xs flex items-center gap-1.5 hover:opacity-70"
            style={{ color: "var(--text-3)", background: "none", border: "none", cursor: "pointer" }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            返回
          </button>
          <h1 className="font-semibold text-lg" style={{ color: "var(--text-1)" }}>社区</h1>
        </div>
        <div className="flex items-center gap-1">
          {tabs.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="text-xs px-3 md:px-4 py-1.5 rounded-full transition-all"
              style={{
                background: tab === t ? "var(--accent)" : "transparent",
                color: tab === t ? "var(--bg-base)" : "var(--text-3)",
                fontWeight: tab === t ? 600 : 400,
              }}>{t}</button>
          ))}
          <button onClick={() => setShowChat(!showChat)}
            className="lg:hidden text-xs px-3 py-1.5 rounded-full transition-all"
            style={{ background: showChat ? "rgba(200,151,90,0.1)" : "transparent", color: showChat ? "var(--accent)" : "var(--text-3)" }}>
            💬
          </button>
        </div>
      </header>
      <div className="flex-1 flex min-h-0">
        <div className={`flex-1 flex flex-col overflow-hidden ${showChat ? 'hidden lg:flex' : 'flex'}`}>
          <div className="flex-1 overflow-auto p-4 md:p-6">
            {isLoading ? (
              <div className="flex justify-center py-32"><Spinner /></div>
            ) : posts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="text-6xl mb-6 opacity-30">🖋️</div>
                <h2 className="font-semibold mb-3" style={{ fontSize: "1.25rem", color: "#c8a878" }}>静待墨香</h2>
                <p className="text-sm leading-relaxed max-w-xs" style={{ color: "rgba(200,165,120,0.45)" }}>
                  还没有作品发布到沙龙。<br />
                  在你的项目概览页开启<span style={{ color: "var(--accent)" }}>「发布到社区」</span>，<br />
                  你的故事将在这里绽放。
                </p>
                <button onClick={() => navigate(-1)}
                  className="mt-6 text-xs px-5 py-2 rounded-lg font-medium"
                  style={{ background: "var(--accent)", color: "var(--bg-base)", cursor: "pointer" }}>
                  返回上一页
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
                {posts.map((p: any) => (
                  <article
                    key={p.project_id}
                    onClick={() => navigate(`/community/${p.project_id}`)}
                    className="rounded-xl overflow-hidden cursor-pointer hover:-translate-y-0.5 transition-all duration-200 group"
                    style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                    {/* Cover */}
                    <div className="relative w-full h-36 overflow-hidden" style={{ background: "var(--bg-raised)" }}>
                      {p.has_cover ? (
                        <img src={getCoverUrl(p.project_id)} alt={p.novel_name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <span className="text-5xl font-black select-none opacity-10" style={{ color: "var(--accent)" }}>
                            {(p.novel_name || "?")[0]}
                          </span>
                        </div>
                      )}
                      <div className="absolute inset-x-0 bottom-0 h-12 pointer-events-none"
                        style={{ background: "linear-gradient(transparent, var(--bg-surface))" }} />
                    </div>
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] px-2 py-0.5 rounded-full"
                          style={{ background: "rgba(200,151,90,0.1)", color: "var(--accent)" }}>
                          {p.genre || "未分类"}
                        </span>
                        <span className="text-[10px]" style={{ color: "var(--text-3)" }}>{p.scene_count} 幕</span>
                      </div>
                      <h3 className="font-semibold text-sm mb-1 truncate" style={{ color: "var(--text-1)" }}>{p.novel_name}</h3>
                      <p className="text-xs" style={{ color: "var(--text-3)" }}>@{p.display_name || p.user_id?.slice(0, 8)}</p>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
          <div className="flex-shrink-0 px-6 py-2 flex items-center justify-between"
            style={{ borderTop: "1px solid rgba(200,151,90,0.06)" }}>
            <span className="text-[10px] font-mono" style={{ color: "rgba(180,160,140,0.3)" }}>
              {posts.length} 部作品 · {posts.reduce((s: number, p: any) => s + p.scene_count, 0)} 幕
            </span>
            <span className="text-[10px]" style={{ color: "rgba(180,160,140,0.25)" }}>InkForge 文学沙龙</span>
          </div>
        </div>
        <ChatColumn />
        {showChat && <div className="lg:hidden flex-1 flex flex-col"><ChatColumn /></div>}
      </div>
    </div>
  );
}
