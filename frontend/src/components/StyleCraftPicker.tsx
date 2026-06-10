import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getStylePresets, getCraftPresets, getProjectStyleConfig,
  setProjectStyleConfig, createStyleTemplate, createCraftTemplate,
} from "../api/templates";
import type { WritingTemplate } from "../api/templates";

export function StyleCraftPicker({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const { data: presetsS } = useQuery({ queryKey: ["stylePresets"], queryFn: getStylePresets });
  const { data: presetsC } = useQuery({ queryKey: ["craftPresets"], queryFn: getCraftPresets });
  const { data: config } = useQuery({
    queryKey: ["styleConfig", projectId],
    queryFn: () => getProjectStyleConfig(projectId), enabled: !!projectId,
  });
  const [showCreate, setShowCreate] = useState<"style" | "craft" | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const stylePresets = presetsS?.templates ?? [];
  const craftPresets = presetsC?.templates ?? [];
  const currentStyle = config?.style_id ?? "";
  const currentCraft = config?.craft_id ?? "";

  const select = (type: string, id: string) => {
    if (type === "style") setProjectStyleConfig(projectId, id, currentCraft);
    else setProjectStyleConfig(projectId, currentStyle, id);
    qc.invalidateQueries({ queryKey: ["styleConfig", projectId] });
  };

  function group(label: string, icon: string, items: WritingTemplate[], current: string, type: string) {
    return (
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[11px] font-semibold" style={{ color: "var(--text-1)" }}>{icon} {label}</span>
          <button onClick={() => setShowCreate(type as any)}
            className="text-[10px] border-0 cursor-pointer px-2 py-0.5 rounded-full transition-all"
            style={{ background: "rgba(200,151,90,0.08)", color: "var(--text-3)" }}>
            ＋ 自定义
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button onClick={() => select(type, "")}
            className="text-[11px] px-3 py-1 rounded-full border-0 cursor-pointer transition-all"
            style={{
              background: current === "" ? "var(--accent)" : "var(--bg-surface)",
              color: current === "" ? "var(--bg-base)" : "var(--text-3)",
              border: current === "" ? "1px solid var(--accent)" : "1px solid var(--border)",
            }}>默认</button>
          {items.map(t => (
            <button key={t.id} onClick={() => select(type, t.id)}
              className="text-[11px] px-3 py-1 rounded-full border-0 cursor-pointer transition-all"
              style={{
                background: current === t.id ? "var(--accent)" : "var(--bg-surface)",
                color: current === t.id ? "var(--bg-base)" : "var(--text-3)",
                border: current === t.id ? "1px solid var(--accent)" : "1px solid var(--border)",
              }}>{t.name}</button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 rounded-xl overflow-hidden"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
      {/* header */}
      <div className="flex items-center justify-between px-4 py-2.5 cursor-pointer"
        style={{ borderBottom: collapsed ? "none" : "1px solid var(--border)" }}
        onClick={() => setCollapsed(v => !v)}>
        <span className="text-xs font-semibold" style={{ color: "var(--text-1)" }}>
          🎨 文风与写作方法
          {(currentStyle || currentCraft) && (
            <span className="ml-2 text-[10px] font-normal" style={{ color: "var(--accent)" }}>
              {currentStyle ? stylePresets.find(t => t.id === currentStyle)?.name || "自定义" : ""}
              {currentStyle && currentCraft ? " · " : ""}
              {currentCraft ? craftPresets.find(t => t.id === currentCraft)?.name || "自定义" : ""}
            </span>
          )}
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2"
          style={{ transform: collapsed ? "rotate(0deg)" : "rotate(180deg)", transition: "0.2s" }}>
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
      {/* body */}
      {!collapsed && (
        <div className="px-4 py-3">
          <div className="flex flex-col sm:flex-row gap-4">
            {group("文风", "", stylePresets, currentStyle, "style")}
            {group("写作方法", "", craftPresets, currentCraft, "craft")}
          </div>
        </div>
      )}
      {/* create modal */}
      {showCreate && (
        <CreateModal type={showCreate} onClose={() => setShowCreate(null)}
          onCreated={() => {
            qc.invalidateQueries({ queryKey: [showCreate === "style" ? "stylePresets" : "craftPresets"] });
            setShowCreate(null);
          }} />
      )}
    </div>
  );
}

function CreateModal({ type, onClose, onCreated }: {
  type: "style" | "craft"; onClose: () => void; onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [snippet, setSnippet] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!name.trim() || !snippet.trim()) return;
    setSaving(true);
    const fn = type === "style" ? createStyleTemplate : createCraftTemplate;
    await fn({ name, description: desc, prompt_snippet: snippet });
    setSaving(false); onCreated();
  };

  return (
    <div className="fixed inset-0 z-[20000] flex items-center justify-center" style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-[460px] max-w-[95vw] max-h-[80vh] overflow-auto rounded-2xl p-6"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", boxShadow: "0 24px 64px rgba(0,0,0,0.5)" }}>
        <h3 className="font-semibold mb-4" style={{ color: "var(--text-1)" }}>
          {type === "style" ? "🎨 新建文风模板" : "📐 新建写作方法模板"}
        </h3>
        <input value={name} onChange={e => setName(e.target.value)}
          placeholder="模板名称"
          className="w-full text-sm px-3 py-2 rounded-lg mb-3 outline-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
        <input value={desc} onChange={e => setDesc(e.target.value)}
          placeholder="简短描述"
          className="w-full text-sm px-3 py-2 rounded-lg mb-3 outline-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
        <textarea value={snippet} onChange={e => setSnippet(e.target.value)}
          placeholder="Prompt 文本（注入到 AI 写作指令中）"
          rows={8}
          className="w-full text-sm px-3 py-2 rounded-lg mb-4 outline-none resize-none"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-1)", fontFamily: "monospace" }} />
        <div className="flex gap-2 justify-end">
          <button onClick={onClose}
            className="text-sm px-4 py-2 rounded-lg border-0 cursor-pointer"
            style={{ background: "transparent", color: "var(--text-3)" }}>取消</button>
          <button onClick={save} disabled={saving || !name.trim() || !snippet.trim()}
            className="text-sm px-4 py-2 rounded-lg border-0 cursor-pointer font-medium disabled:opacity-30"
            style={{ background: "var(--accent)", color: "var(--bg-base)" }}>
            {saving ? "保存中…" : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}
