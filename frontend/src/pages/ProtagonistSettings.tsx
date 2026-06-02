import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Spinner } from "../components/ui/Spinner";
import { PageHelp } from "../components/PageHelp";
import { getCharacter, updateCharacter } from "../api/entities";
import { getGoals } from "../api/status";
import type { CharacterDetail } from "../types/entities";

// ── Field helpers ──────────────────────────────────────────────────────────
function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <label className="block text-xs font-semibold mb-1.5 tracking-wide" style={{ color: "var(--text-3)" }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  background: "var(--bg-raised)", border: "1px solid var(--border)",
  color: "var(--text-1)", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", width: "100%",
  outline: "none", transition: "border-color 0.2s",
};

function TagEditor({ tags, onChange, placeholder }: { tags: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [input, setInput] = useState("");

  const addTag = useCallback(() => {
    const t = input.trim();
    if (t && !tags.includes(t)) { onChange([...tags, t]); setInput(""); }
  }, [input, tags, onChange]);

  const removeTag = useCallback((idx: number) => {
    onChange(tags.filter((_, i) => i !== idx));
  }, [tags, onChange]);

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {tags.map((t, i) => (
          <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
            {t}
            <button type="button" onClick={() => removeTag(i)} className="hover:opacity-70" style={{ color: "var(--text-3)" }}>×</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
          placeholder={placeholder} style={inputStyle} className="flex-1" />
        <button type="button" onClick={addTag}
          className="text-xs px-3 py-1.5 rounded-lg transition-colors"
          style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
          添加
        </button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────
export function ProtagonistSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<null | { type: "success" | "error"; text: string }>(null);

  // 1. Get protagonist_id from goals
  const { data: goalsData, isLoading: goalsLoading } = useQuery({
    queryKey: ["goals", id],
    queryFn: () => getGoals(id!),
    enabled: !!id,
  });

  const protagonistId = goalsData?.protagonist_id ?? null;

  // 2. Load full character detail
  const { data: charData, isLoading: charLoading } = useQuery({
    queryKey: ["character", id, protagonistId],
    queryFn: () => getCharacter(id!, protagonistId!),
    enabled: !!protagonistId,
  });

  // 3. Local form state
  const [form, setForm] = useState<Partial<CharacterDetail>>({});

  useEffect(() => {
    if (charData) setForm({ ...charData });
  }, [charData]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const isLoading = goalsLoading || charLoading;

  // ── Save ──
  const handleSave = useCallback(async () => {
    if (!id || !protagonistId) return;
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {};
      const editable = new Set([
        "first_name", "family_name", "title", "nicknames",
        "role", "description", "backstory", "status",
      ]);
      for (const key of editable) {
        if (key in form) patch[key] = (form as any)[key];
      }
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

      await updateCharacter(id, protagonistId, patch);
      setToast({ type: "success", text: "主角设定已保存" });
      queryClient.invalidateQueries({ queryKey: ["character", id, protagonistId] });
      queryClient.invalidateQueries({ queryKey: ["goals", id] });
    } catch (e: any) {
      const detail = e?.status ? `HTTP ${e.status}: ${e.message}` : (e?.message ?? String(e));
      console.error("ProtagonistSettings save failed", { projectId: id, charId: protagonistId, error: e });
      setToast({ type: "error", text: `保存失败: ${detail}` });
    } finally {
      setSaving(false);
    }
  }, [id, protagonistId, form, queryClient]);

  // ── Render ──
  if (isLoading) return <div className="flex justify-center py-24"><Spinner /></div>;
  if (!protagonistId) return <p className="text-sm py-24 text-center" style={{ color: "var(--text-2)" }}>暂无主角信息，先生成一些章节</p>;

  const p = form.personality ?? ({} as any);
  const pt = form.physical_traits ?? ({} as any);
  const cs = form.current_state ?? ({} as any);

  return (
    <div className="max-w-2xl mx-auto pb-20">
      <PageHelp>主角设定 — 直接编辑主角的各项属性。修改任意字段后点击右上角「保存设定」即可生效，后续 AI 生成将使用新设定。</PageHelp>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-lg font-bold" style={{ color: "var(--text-1)" }}>主角设定</h1>
          <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>修改后点击保存，生成时将使用这些设定</p>
        </div>
        <button onClick={handleSave} disabled={saving}
          className="text-sm px-5 py-2 rounded-lg font-medium transition-all duration-200 disabled:opacity-40"
          style={{ background: "#c8975a", color: "#0e0c09" }}>
          {saving ? "保存中…" : "保存设定"}
        </button>
      </div>

      {/* ── Section: Basic Info ── */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-1)" }}>基本信息</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FieldRow label="姓 (family_name)">
            <input style={inputStyle} value={form.family_name ?? ""}
              onChange={e => setForm(f => ({ ...f, family_name: e.target.value }))} />
          </FieldRow>
          <FieldRow label="名 (first_name)">
            <input style={inputStyle} value={form.first_name ?? ""}
              onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} />
          </FieldRow>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FieldRow label="称号 (title)">
            <input style={inputStyle} value={form.title ?? ""} placeholder="如：剑仙、魔女"
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
          </FieldRow>
          <FieldRow label="角色定位 (role)">
            <input style={inputStyle} value={form.role ?? ""} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
              list="protag-role-suggestions" placeholder="如：主角、迷宫守护者" />
            <datalist id="protag-role-suggestions">
              <option value="主角" /><option value="反派" /><option value="配角" /><option value="次要" />
              <option value="导师" /><option value="盟友" /><option value="对手" /><option value="中立" />
            </datalist>
          </FieldRow>
        </div>
        <FieldRow label="昵称 (nicknames)">
          <TagEditor tags={form.nicknames ?? []} onChange={v => setForm(f => ({ ...f, nicknames: v }))} placeholder="输入昵称后按回车添加" />
        </FieldRow>
        <FieldRow label="状态">
          <select style={inputStyle} value={(form as any).status ?? "active"}
            onChange={e => setForm(f => ({ ...f, status: e.target.value } as any))}>
            <option value="active">活跃</option>
            <option value="sidelined">暂离</option>
            <option value="departed">离场</option>
            <option value="deceased">已故</option>
            <option value="returning">回归</option>
          </select>
        </FieldRow>
      </div>

      {/* ── Section: Description & Backstory ── */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-1)" }}>描述与背景</h2>
        <FieldRow label="角色描述 (description)">
          <textarea style={{ ...inputStyle, minHeight: 80, resize: "vertical" }} value={form.description ?? ""}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
        </FieldRow>
        <FieldRow label="背景故事 (backstory)">
          <textarea style={{ ...inputStyle, minHeight: 100, resize: "vertical" }} value={form.backstory ?? ""}
            onChange={e => setForm(f => ({ ...f, backstory: e.target.value }))} />
        </FieldRow>
      </div>

      {/* ── Section: Personality ── */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-1)" }}>性格</h2>
        <FieldRow label="核心特质 (core_traits)">
          <TagEditor tags={p.core_traits ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, core_traits: v } }))} placeholder="如：勇敢、固执" />
        </FieldRow>
        <FieldRow label="恐惧 (fears)">
          <TagEditor tags={p.fears ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, fears: v } }))} placeholder="如：被抛弃、黑暗" />
        </FieldRow>
        <FieldRow label="欲望 (desires)">
          <TagEditor tags={p.desires ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, desires: v } }))} placeholder="如：复仇、被认可" />
        </FieldRow>
        <FieldRow label="缺陷 (flaws)">
          <TagEditor tags={p.flaws ?? []} onChange={v => setForm(f => ({ ...f, personality: { ...p, flaws: v } }))} placeholder="如：傲慢、冲动" />
        </FieldRow>
      </div>

      {/* ── Section: Physical Traits ── */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-1)" }}>外貌</h2>
        <FieldRow label="年龄 (age)">
          <input type="number" style={inputStyle} value={pt.age ?? ""}
            onChange={e => setForm(f => ({ ...f, physical_traits: { ...pt, age: e.target.value ? parseInt(e.target.value) : null } }))} />
        </FieldRow>
        <FieldRow label="外貌描述 (appearance)">
          <textarea style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} value={pt.appearance ?? ""}
            onChange={e => setForm(f => ({ ...f, physical_traits: { ...pt, appearance: e.target.value } }))} />
        </FieldRow>
        <FieldRow label="特征 (distinctive_features)">
          <TagEditor tags={pt.distinctive_features ?? []} onChange={v => setForm(f => ({ ...f, physical_traits: { ...pt, distinctive_features: v } }))} placeholder="如：左眼有疤、银发" />
        </FieldRow>
      </div>

      {/* ── Section: Current State ── */}
      <div className="rounded-xl p-6 mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text-1)" }}>当前状态</h2>
        <FieldRow label="情绪状态 (emotional_state)">
          <input style={inputStyle} value={cs.emotional_state ?? ""}
            onChange={e => setForm(f => ({ ...f, current_state: { ...cs, emotional_state: e.target.value } }))} />
        </FieldRow>
        <FieldRow label="当前目标 (goals)">
          <TagEditor tags={cs.goals ?? []} onChange={v => setForm(f => ({ ...f, current_state: { ...cs, goals: v } }))} placeholder="如：找到神秘玉牌" />
        </FieldRow>
        <FieldRow label="信念 (beliefs)">
          <TagEditor tags={cs.beliefs ?? []} onChange={v => setForm(f => ({ ...f, current_state: { ...cs, beliefs: v } }))} placeholder="如：力量即是正义" />
        </FieldRow>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm shadow-lg"
          style={{
            color: "#fff", backdropFilter: "blur(8px)",
            background: toast.type === "success" ? "rgba(34,120,60,0.92)" : "rgba(180,40,40,0.92)",
          }}>
          {toast.text}
        </div>
      )}
    </div>
  );
}
