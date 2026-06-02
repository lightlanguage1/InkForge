import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Select } from "../components/ui/Select";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { getLore, updateLore, createLore, deleteLore } from "../api/status";
import type { LoreItem } from "../types/status";
import { PageHelp } from "../components/PageHelp";

const LABEL_STYLE: React.CSSProperties = {
  display: "block", fontSize: "11px", fontWeight: 600,
  color: "var(--text-3)", marginBottom: "4px", letterSpacing: "0.04em",
};
const BASE_INPUT: React.CSSProperties = {
  background: "var(--bg-raised)", border: "1px solid var(--border)",
  color: "var(--text-1)", borderRadius: "8px", padding: "8px 12px",
  fontSize: "13px", width: "100%", outline: "none",
};

const CATEGORIES = [
  { value: "组织与势力", label: "组织与势力" }, { value: "物品与道具", label: "物品与道具" },
  { value: "社会与规范", label: "社会与规范" }, { value: "物理规则", label: "物理规则" },
  { value: "生物与种族", label: "生物与种族" }, { value: "文化与习俗", label: "文化与习俗" },
  { value: "历史与传说", label: "历史与传说" }, { value: "地理与环境", label: "地理与环境" },
  { value: "政治与权力", label: "政治与权力" }, { value: "宗教与信仰", label: "宗教与信仰" },
  { value: "军事与战争", label: "军事与战争" }, { value: "经济与贸易", label: "经济与贸易" },
  { value: "魔法体系", label: "魔法体系" }, { value: "科技体系", label: "科技体系" },
  { value: "其他", label: "其他" },
];
const LORE_TYPES = [
  { value: "规则", label: "规则" }, { value: "事实", label: "事实" },
  { value: "限制", label: "限制" }, { value: "能力", label: "能力" },
  { value: "传统", label: "传统" }, { value: "事件", label: "事件" },
  { value: "禁忌", label: "禁忌" }, { value: "其他", label: "其他" },
];
const IMPORTANCES = [
  { value: "critical", label: "关键" }, { value: "important", label: "重要" },
  { value: "normal", label: "普通" }, { value: "minor", label: "次要" },
];
const IMP_COLOR: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", important: "warning", normal: "info", minor: "default" };

export function LorePage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [category, setCategory] = useState("");
  const [loreType, setLoreType] = useState("");
  const [importance, setImportance] = useState("");

  // ── Edit modal state ──
  const [editing, setEditing] = useState<LoreItem | null>(null);
  const [editForm, setEditForm] = useState({
    content: "", category: "", lore_type: "rule", importance: "normal", tags: "" as string,
  });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<null | { type: "success" | "error"; text: string }>(null);

  // ── New lore modal state ──
  const [showNew, setShowNew] = useState(false);

  const params: Record<string, string> = {};
  if (category) params.category = category;
  if (loreType) params.lore_type = loreType;
  if (importance) params.importance = importance;

  const { data, isLoading } = useQuery({
    queryKey: ["lore", id, params],
    queryFn: () => getLore(id!, params),
    enabled: !!id,
  });

  // ── Open edit modal ──
  const openEdit = useCallback((item: LoreItem) => {
    setEditing(item);
    setEditForm({
      content: item.content || "",
      category: item.category || "",
      lore_type: item.type || "rule",
      importance: item.importance || "normal",
      tags: (item.tags || []).join(", "),
    });
  }, []);

  // ── Open new modal ──
  const openNew = useCallback(() => {
    setEditing(null);
    setEditForm({ content: "", category: "other", lore_type: "rule", importance: "normal", tags: "" });
    setShowNew(true);
  }, []);

  const closeModal = useCallback(() => {
    if (!saving) { setEditing(null); setShowNew(false); }
  }, [saving]);

  // ── Save (edit or create) ──
  const handleSave = useCallback(async () => {
    if (!id || saving) return;
    const tags = editForm.tags.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    const patch = {
      content: editForm.content,
      category: editForm.category,
      lore_type: editForm.lore_type,
      importance: editForm.importance,
      tags,
    };
    setSaving(true);
    try {
      if (editing) {
        await updateLore(id, editing.id, patch);
        setToast({ type: "success", text: "世界观条目已更新" });
      } else {
        await createLore(id, { ...patch, lore_type: patch.lore_type, tags: patch.tags || [] } as any);
        setToast({ type: "success", text: "新世界观条目已创建" });
      }
      setEditing(null); setShowNew(false);
      qc.invalidateQueries({ queryKey: ["lore", id] });
    } catch (e: any) {
      setToast({ type: "error", text: `保存失败: ${e?.message ?? e}` });
    } finally {
      setSaving(false);
    }
  }, [id, saving, editing, editForm, qc]);

  // ── Delete ──
  const handleDelete = useCallback(async () => {
    if (!id || !editing || saving) return;
    if (!confirm(`确定删除世界观条目「${editing.content.slice(0, 40)}…」？`)) return;
    setSaving(true);
    try {
      await deleteLore(id, editing.id);
      setToast({ type: "success", text: "已删除" });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["lore", id] });
    } catch (e: any) {
      setToast({ type: "error", text: `删除失败: ${e?.message ?? e}` });
    } finally {
      setSaving(false);
    }
  }, [id, editing, saving, qc]);

  // Auto-dismiss toast
  if (toast) setTimeout(() => setToast(null), 3500);

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <PageHelp>世界观设定 — 浏览、编辑、添加故事世界观规则。点击任意卡片可编辑内容，右上角按钮添加新条目。修改后立即生效。</PageHelp>
        <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--text-1)" }}>世界观</h1>
        <Button variant="primary" size="sm" onClick={openNew}>＋ 添加世界观</Button>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <Select label="类别" value={category} onChange={setCategory}
          options={[{ value: "", label: "全部" }, ...CATEGORIES]} />
        <Select label="类型" value={loreType} onChange={setLoreType}
          options={[{ value: "", label: "全部" }, ...LORE_TYPES]} />
        <Select label="重要性" value={importance} onChange={setImportance}
          options={[{ value: "", label: "全部" }, ...IMPORTANCES]} />
      </div>

      {isLoading ? <Spinner /> : (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: "var(--text-3)" }}>共 {data?.total_count ?? 0} 条</p>
          {(data?.lore ?? []).map((l: LoreItem) => (
            <Card key={l.id} className="p-4 cursor-pointer hover:brightness-105 transition-all duration-150" onClick={() => openEdit(l)}>
              <div className="flex flex-wrap items-start gap-2 mb-1">
                <Badge variant={IMP_COLOR[l.importance] || "default"}>{l.importance}</Badge>
                <Badge variant="default">{l.type}</Badge>
                <span className="text-xs" style={{ color: "var(--text-3)" }}>
                  {l.category} · {l.source_scene || `tick ${l.tick}`}
                </span>
              </div>
              <p className="text-sm" style={{ color: "var(--text-2)" }}>{l.content}</p>
              {l.tags?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {l.tags.map((t, i) => (
                    <span key={i} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--bg-raised)", color: "var(--text-3)", border: "1px solid var(--border)" }}>{t}</span>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* ── Edit / New Modal ── */}
      <Modal open={!!editing || showNew} title={editing ? "编辑世界观" : "添加世界观"} onClose={closeModal}>
        <div className="p-5 space-y-4">
          <label style={LABEL_STYLE}>
            内容 <span style={{ color: "var(--accent)" }}>*</span>
            <textarea style={{ ...BASE_INPUT, minHeight: "80px", resize: "vertical" }} value={editForm.content}
              onChange={e => setEditForm(f => ({ ...f, content: e.target.value }))} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label style={LABEL_STYLE}>
              类别
              <select style={BASE_INPUT} value={editForm.category}
                onChange={e => setEditForm(f => ({ ...f, category: e.target.value }))}>
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </label>
            <label style={LABEL_STYLE}>
              类型
              <select style={BASE_INPUT} value={editForm.lore_type}
                onChange={e => setEditForm(f => ({ ...f, lore_type: e.target.value }))}>
                {LORE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label style={LABEL_STYLE}>
              重要性
              <select style={BASE_INPUT} value={editForm.importance}
                onChange={e => setEditForm(f => ({ ...f, importance: e.target.value }))}>
                {IMPORTANCES.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
              </select>
            </label>
            <label style={LABEL_STYLE}>
              标签 (逗号分隔)
              <input style={BASE_INPUT} value={editForm.tags}
                onChange={e => setEditForm(f => ({ ...f, tags: e.target.value }))}
                placeholder="如: 修仙, 飞升" />
            </label>
          </div>
          <div className="flex justify-between pt-2" style={{ borderTop: "1px solid var(--border)" }}>
            {editing ? (
              <Button variant="danger" size="sm" onClick={handleDelete} disabled={saving}>删除</Button>
            ) : <div />}
            <div className="flex gap-2">
              <button onClick={closeModal} disabled={saving}
                className="text-sm px-4 py-2 rounded-lg transition-colors"
                style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>
                取消
              </button>
              <button onClick={handleSave} disabled={saving || !editForm.content.trim()}
                className="text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-40"
                style={{ background: "#c8975a", color: "#0e0c09", border: "1px solid transparent" }}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm shadow-lg"
          style={{ color: "#fff", backdropFilter: "blur(8px)",
            background: toast.type === "success" ? "rgba(34,120,60,0.92)" : "rgba(180,40,40,0.92)", }}>
          {toast.text}
        </div>
      )}
    </div>
  );
}
