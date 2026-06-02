import { useState, useEffect, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Modal } from "./ui/Modal";
import { updateCharacter } from "../api/entities";
import type { CharacterDetail } from "../types/entities";

const inputStyle: React.CSSProperties = {
  background: "var(--bg-raised)", border: "1px solid var(--border)",
  color: "var(--text-1)", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", width: "100%", outline: "none",
};
function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block mb-3">
      <span className="block text-xs font-semibold mb-1.5 tracking-wide" style={{ color: "var(--text-3)" }}>{label}</span>
      {children}
    </label>
  );
}
function TagEditor({ tags, onChange, placeholder }: { tags: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [input, setInput] = useState("");
  const addTag = useCallback(() => {
    const t = input.trim();
    if (t && !tags.includes(t)) { onChange([...tags, t]); setInput(""); }
  }, [input, tags, onChange]);
  const removeTag = useCallback((idx: number) => { onChange(tags.filter((_, i) => i !== idx)); }, [tags, onChange]);
  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {tags.map((t, i) => (
          <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
            {t} <button type="button" onClick={() => removeTag(i)} className="hover:opacity-70" style={{ color: "var(--text-3)" }}>×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
          placeholder={placeholder} style={inputStyle} className="flex-1" />
        <button type="button" onClick={addTag}
          className="text-xs px-3 py-1.5 rounded-lg transition-colors"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>添加</button>
      </div>
    </div>
  );
}

interface Props {
  open: boolean;
  projectId: string;
  character: CharacterDetail | null;
  onClose: () => void;
}

export function CharacterEditModal({ open, projectId, character, onClose }: Props) {
  const qc = useQueryClient();
  const [form, setForm] = useState<Partial<CharacterDetail>>({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<null | { type: "success" | "error"; text: string }>(null);

  useEffect(() => {
    if (character) setForm({ ...character });
  }, [character]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const handleSave = useCallback(async () => {
    if (!projectId || !character) return;
    setSaving(true);
    try {
      // Only send fields the user can actually edit (avoid sending huge data back)
      const patch: Record<string, unknown> = {};
      const editable = new Set([
        "first_name", "family_name", "title", "nicknames",
        "role", "description", "backstory", "status",
      ]);
      for (const key of editable) {
        if (key in form) patch[key] = (form as any)[key];
      }
      // Nested objects — only send what the form shows
      if (form.personality) {
        patch["personality"] = {
          core_traits: form.personality.core_traits,
          fears: form.personality.fears,
          desires: form.personality.desires,
          flaws: form.personality.flaws,
        };
      }
      if (form.physical_traits) {
        patch["physical_traits"] = {
          age: form.physical_traits.age,
          appearance: form.physical_traits.appearance,
          distinctive_features: form.physical_traits.distinctive_features,
        };
      }
      if (form.current_state) {
        patch["current_state"] = {
          emotional_state: form.current_state.emotional_state,
          goals: form.current_state.goals,
          beliefs: form.current_state.beliefs,
          emotion: form.current_state.emotion ? {
            dominant: form.current_state.emotion.dominant,
            valence: form.current_state.emotion.valence,
            arousal: form.current_state.emotion.arousal,
            intensity: form.current_state.emotion.intensity,
          } : undefined,
        };
      }
      console.log("CharacterEdit save patch size:", JSON.stringify(patch).length, "bytes");
      await updateCharacter(projectId, character.id, patch);
      setToast({ type: "success", text: "角色已保存，名称变更已在全局场景中替换" });
      qc.invalidateQueries({ queryKey: ["characters", projectId] });
      qc.invalidateQueries({ queryKey: ["character", projectId, character.id] });
      qc.invalidateQueries({ queryKey: ["read", projectId] });
      onClose();
    } catch (e: any) {
      const detail = e?.status ? `HTTP ${e.status}: ${e.message}` : (e?.message ?? String(e));
      console.error("CharacterEdit save failed", { projectId, charId: character?.id, error: e });
      setToast({ type: "error", text: `保存失败: ${detail}` });
    } finally { setSaving(false); }
  }, [projectId, character, form, qc, onClose]);

  const p = (form.personality ?? {}) as any;
  const pt = (form.physical_traits ?? {}) as any;
  const cs = (form.current_state ?? {}) as any;

  return (
    <Modal open={open} title={`编辑角色：${character?.family_name ?? ""}${character?.first_name ?? ""}`} onClose={onClose} wide>
      <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
        {/* Basic Info */}
        <div className="rounded-xl p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-1)" }}>基本信息</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldRow label="姓 (family_name)"><input style={inputStyle} value={form.family_name ?? ""} onChange={e => setForm(f => ({ ...f, family_name: e.target.value }))} /></FieldRow>
            <FieldRow label="名 (first_name)"><input style={inputStyle} value={form.first_name ?? ""} onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} /></FieldRow>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FieldRow label="称号"><input style={inputStyle} value={form.title ?? ""} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} /></FieldRow>
            <FieldRow label="角色定位">
              <input style={inputStyle} value={form.role ?? ""} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                list="role-suggestions" placeholder="如：迷宫守护者、导师、路人" />
              <datalist id="role-suggestions">
                <option value="主角" /><option value="反派" /><option value="配角" /><option value="次要" />
                <option value="导师" /><option value="盟友" /><option value="对手" /><option value="中立" />
              </datalist>
            </FieldRow>
          </div>
          <FieldRow label="昵称"><TagEditor tags={form.nicknames ?? []} onChange={v => setForm(f => ({ ...f, nicknames: v }))} placeholder="输入昵称" /></FieldRow>
          <FieldRow label="状态">
            <select style={inputStyle} value={(form as any).status ?? "active"} onChange={e => setForm(f => ({ ...f, status: e.target.value } as any))}>
              <option value="active">活跃</option><option value="sidelined">暂离</option><option value="departed">离场</option><option value="deceased">已故</option><option value="returning">回归</option>
            </select>
          </FieldRow>
        </div>

        {/* Description */}
        <div className="rounded-xl p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-1)" }}>描述与背景</h3>
          <FieldRow label="角色描述"><textarea style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} value={form.description ?? ""} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></FieldRow>
          <FieldRow label="背景故事"><textarea style={{ ...inputStyle, minHeight: 80, resize: "vertical" }} value={form.backstory ?? ""} onChange={e => setForm(f => ({ ...f, backstory: e.target.value }))} /></FieldRow>
        </div>

        {/* Personality */}
        <div className="rounded-xl p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-1)" }}>性格</h3>
          <FieldRow label="核心特质"><TagEditor tags={p.core_traits ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, core_traits: v } }))} placeholder="如：勇敢、固执" /></FieldRow>
          <FieldRow label="恐惧"><TagEditor tags={p.fears ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, fears: v } }))} placeholder="如：被抛弃" /></FieldRow>
          <FieldRow label="欲望"><TagEditor tags={p.desires ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, desires: v } }))} placeholder="如：复仇" /></FieldRow>
          <FieldRow label="缺陷"><TagEditor tags={p.flaws ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, flaws: v } }))} placeholder="如：傲慢" /></FieldRow>
        </div>

        {/* Physical */}
        <div className="rounded-xl p-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-1)" }}>外貌</h3>
          <FieldRow label="年龄"><input type="number" style={inputStyle} value={pt.age ?? ""} onChange={e => setForm(f => ({ ...f, physical_traits: { ...pt, age: e.target.value ? parseInt(e.target.value) : null } }))} /></FieldRow>
          <FieldRow label="外貌描述"><textarea style={{ ...inputStyle, minHeight: 50, resize: "vertical" }} value={pt.appearance ?? ""} onChange={e => setForm(f => ({ ...f, physical_traits: { ...pt, appearance: e.target.value } }))} /></FieldRow>
          <FieldRow label="特征"><TagEditor tags={pt.distinctive_features ?? []} onChange={v => setForm(f => ({ ...f, physical_traits: { ...pt, distinctive_features: v } }))} placeholder="如：左眼有疤" /></FieldRow>
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-3 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
          <button onClick={onClose} disabled={saving} className="text-sm px-4 py-2 rounded-lg" style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>取消</button>
          <button onClick={handleSave} disabled={saving} className="text-sm px-5 py-2 rounded-lg font-medium disabled:opacity-40" style={{ background: "#c8975a", color: "#0e0c09" }}>
            {saving ? "保存中…" : "保存并全局替换"}
          </button>
        </div>
      </div>
      {toast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm shadow-lg"
          style={{ color: "#fff", backdropFilter: "blur(8px)", background: toast.type === "success" ? "rgba(34,120,60,0.92)" : "rgba(180,40,40,0.92)" }}>
          {toast.text}
        </div>
      )}
    </Modal>
  );
}
