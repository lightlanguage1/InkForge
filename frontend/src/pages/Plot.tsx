import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { getPlotStatus, generateBeats, updateBeat, deleteBeat, clearBeats } from "../api/plot";
import type { BeatInfo } from "../types/plot";
import { PageHelp } from "../components/PageHelp";

const STATUS_CN: Record<string, { label: string; variant: "default" | "success" | "warning" | "info" }> = {
  pending:     { label: "待执行", variant: "default" },
  in_progress: { label: "进行中", variant: "warning" },
  completed:   { label: "已完成", variant: "success" },
  skipped:     { label: "已跳过", variant: "default" },
};
const STATUSES = ["pending", "in_progress", "completed", "skipped"];

const inputStyle: React.CSSProperties = {
  background: "var(--bg-raised)", border: "1px solid var(--border)",
  color: "var(--text-1)", borderRadius: "8px", padding: "8px 12px", fontSize: "13px", width: "100%", outline: "none",
};

export function PlotPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const [editing, setEditing] = useState<BeatInfo | null>(null);
  const [editForm, setEditForm] = useState({ description: "", characters_involved: "", location: "", tension_target: "", status: "pending" });
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<null | { type: "success" | "error"; text: string }>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["plot", id], queryFn: () => getPlotStatus(id!), enabled: !!id,
  });

  const genMut = useMutation({ mutationFn: () => generateBeats(id!), onSuccess: () => qc.invalidateQueries({ queryKey: ["plot", id] }) });
  const clearMut = useMutation({ mutationFn: () => clearBeats(id!), onSuccess: () => qc.invalidateQueries({ queryKey: ["plot", id] }) });

  const openEdit = useCallback((b: BeatInfo) => {
    setEditing(b);
    setEditForm({
      description: b.description,
      characters_involved: (b.characters_involved || []).join("、"),
      location: b.location || "",
      tension_target: b.tension_target != null ? String(b.tension_target) : "",
      status: b.status,
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!id || !editing || saving) return;
    setSaving(true);
    try {
      const patch: Record<string, unknown> = {
        description: editForm.description,
        characters_involved: editForm.characters_involved.split(/[,，、]/).map(s => s.trim()).filter(Boolean),
        location: editForm.location || null,
        tension_target: editForm.tension_target ? parseInt(editForm.tension_target) : null,
        status: editForm.status,
      };
      await updateBeat(id, editing.id, patch);
      setToast({ type: "success", text: "节拍已更新" });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["plot", id] });
    } catch (e: any) { setToast({ type: "error", text: `保存失败: ${e?.message ?? e}` }); }
    finally { setSaving(false); }
  }, [id, editing, editForm, saving, qc]);

  const handleDelete = useCallback(async () => {
    if (!id || !editing || saving) return;
    if (!confirm(`确定删除节拍「${editing.description.slice(0, 50)}…」？`)) return;
    setSaving(true);
    try {
      await deleteBeat(id, editing.id);
      setToast({ type: "success", text: "节拍已删除" });
      setEditing(null);
      qc.invalidateQueries({ queryKey: ["plot", id] });
    } catch (e: any) { setToast({ type: "error", text: `删除失败: ${e?.message ?? e}` }); }
    finally { setSaving(false); }
  }, [id, editing, saving, qc]);

  if (toast) setTimeout(() => setToast(null), 3500);
  if (isLoading) return <Spinner />;
  if (!data) return <p className="text-sm" style={{ color: "var(--text-2)" }}>无法加载情节节拍</p>;

  const stats = [
    { label: "总计", value: data.total_beats },
    { label: "待执行", value: data.pending },
    { label: "进行中", value: data.in_progress },
    { label: "已完成", value: data.completed },
  ];

  return (
    <div className="space-y-6">
      <PageHelp>情节节拍 — 管理故事大纲和节奏控制。每个节拍可编辑或删除，点击节拍右侧按钮操作。节拍是 AI 写作时的剧情指引。</PageHelp>
      <div className="flex items-center justify-between">
        <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>情节节拍</h1>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => { if (confirm("确认清空所有节拍？")) clearMut.mutate(); }} loading={clearMut.isPending}>清空</Button>
          <Button onClick={() => genMut.mutate()} loading={genMut.isPending}>生成节拍</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(s => (
          <Card key={s.label} className="p-4 text-center">
            <p className="text-2xl font-bold tabular-nums" style={{ color: "var(--text-1)" }}>{s.value}</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>{s.label}</p>
          </Card>
        ))}
      </div>

      {data.current_arc && (
        <Card className="p-4">
          <p className="text-sm" style={{ color: "var(--text-2)" }}>
            当前弧线：<span style={{ color: "var(--text-1)" }}>{data.current_arc}</span>
            {data.arc_progress != null && `（${Math.round(data.arc_progress * 100)}%）`}
          </p>
        </Card>
      )}

      {(data?.beats?.length ?? 0) > 0 && (
        <div>
          <h3 className="font-semibold text-sm mb-3" style={{ color: "var(--text-1)" }}>节拍列表</h3>
          <div className="space-y-2">
            {(data?.beats ?? []).map(b => {
              const s = STATUS_CN[b.status] || { label: b.status, variant: "default" as const };
              return (
                <Card key={b.id} className="p-3 group">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0" onClick={() => openEdit(b)} style={{ cursor: "pointer" }}>
                      <p className="text-sm leading-relaxed" style={{ color: "var(--text-1)" }}>{b.description}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1.5">
                        <span className="text-[11px]" style={{ color: "var(--text-3)" }}>{b.id}</span>
                        {b.characters_involved.length > 0 && <span className="text-[11px]" style={{ color: "var(--text-2)" }}>角色：{b.characters_involved.join("、")}</span>}
                        {b.location && <span className="text-[11px]" style={{ color: "var(--text-2)" }}>地点：{b.location}</span>}
                        {b.tension_target != null && <span className="text-[11px]" style={{ color: "var(--text-2)" }}>目标张力：{b.tension_target}/10</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <Badge variant={s.variant}>{s.label}</Badge>
                      <button onClick={(e) => { e.stopPropagation(); openEdit(b); }}
                        className="text-[11px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ color: "var(--text-3)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}
                      >✎</button>
                      <button onClick={(e) => { e.stopPropagation(); if (confirm(`删除「${b.description.slice(0, 30)}…」？`)) { deleteBeat(id!, b.id).then(() => qc.invalidateQueries({ queryKey: ["plot", id] })).catch(() => {}); } }}
                        className="text-[11px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ color: "#e88c8c", background: "var(--bg-raised)", border: "1px solid rgba(200,80,80,0.3)" }}
                      >🗑</button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {data.missing_prerequisites?.length > 0 && (
        <div className="p-4 rounded-xl" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderLeft: "3px solid var(--accent)" }}>
          <p className="text-sm font-semibold mb-2" style={{ color: "var(--text-1)" }}>缺失前置条件</p>
          {data.missing_prerequisites.map((m, i) => (
            <p key={i} className="text-xs" style={{ color: "var(--text-2)" }}>{m.beat_id} ← 需要 {m.prerequisite}</p>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      <Modal open={!!editing} title="编辑节拍" onClose={() => setEditing(null)}>
        <div className="p-5 space-y-4">
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>描述</span>
            <textarea style={{ ...inputStyle, minHeight: 80, resize: "vertical" }} value={editForm.description}
              onChange={e => setEditForm(f => ({ ...f, description: e.target.value }))} />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>角色（顿号分隔）</span>
              <input style={inputStyle} value={editForm.characters_involved}
                onChange={e => setEditForm(f => ({ ...f, characters_involved: e.target.value }))} />
            </label>
            <label className="block">
              <span className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>地点</span>
              <input style={inputStyle} value={editForm.location}
                onChange={e => setEditForm(f => ({ ...f, location: e.target.value }))} />
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>目标张力 (0-10)</span>
              <input style={inputStyle} type="number" min={0} max={10} value={editForm.tension_target}
                onChange={e => setEditForm(f => ({ ...f, tension_target: e.target.value }))} />
            </label>
            <label className="block">
              <span className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>状态</span>
              <select style={inputStyle} value={editForm.status}
                onChange={e => setEditForm(f => ({ ...f, status: e.target.value }))}>
                {STATUSES.map(s => <option key={s} value={s}>{STATUS_CN[s]?.label || s}</option>)}
              </select>
            </label>
          </div>
          <div className="flex justify-between pt-2" style={{ borderTop: "1px solid var(--border)" }}>
            <Button variant="danger" size="sm" onClick={handleDelete} disabled={saving}>删除</Button>
            <div className="flex gap-2">
              <button onClick={() => setEditing(null)} disabled={saving} className="text-sm px-4 py-2 rounded-lg"
                style={{ color: "var(--text-2)", background: "var(--bg-raised)", border: "1px solid var(--border)" }}>取消</button>
              <button onClick={handleSave} disabled={saving || !editForm.description.trim()} className="text-sm px-4 py-2 rounded-lg font-medium disabled:opacity-40"
                style={{ background: "#c8975a", color: "#0e0c09" }}>{saving ? "保存中…" : "保存"}</button>
            </div>
          </div>
        </div>
      </Modal>

      {toast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-xl text-sm shadow-lg"
          style={{ color: "#fff", backdropFilter: "blur(8px)", background: toast.type === "success" ? "rgba(34,120,60,0.92)" : "rgba(180,40,40,0.92)" }}>
          {toast.text}
        </div>
      )}
    </div>
  );
}
