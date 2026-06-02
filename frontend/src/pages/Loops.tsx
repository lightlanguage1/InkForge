import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { Badge } from "../components/ui/Badge";
import { getLoops, updateLoop, deleteLoop } from "../api/entities";
import { PageHelp } from "../components/PageHelp";
import type { LoopItem } from "../types/entities";

function LoopEditForm({ data, projectId, onClose }: { data: Record<string,unknown>; projectId: string; onClose: () => void }) {
  const loopId = String(data.id ?? "");
  const [desc, setDesc] = useState(String(data.description ?? ""));
  const [status, setStatus] = useState(String(data.status ?? "open"));
  const [importance, setImportance] = useState(String(data.importance ?? "medium"));
  const [saving, setSaving] = useState(false);
  const handleSave = async () => {
    setSaving(true);
    await updateLoop(projectId, loopId, { description: desc, status, importance });
    setSaving(false);
    onClose();
  };
  return (
    <div className="flex-1 rounded-xl p-5 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
      <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>编辑线索 {String(data.id ?? "")}</h3>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>描述</span>
        <textarea className="w-full mt-1 px-3 py-2 rounded-lg text-sm" rows={3} style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={desc} onChange={e => setDesc(e.target.value)} />
      </label>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>状态</span>
        <select className="w-full mt-1 px-3 py-2 rounded-lg text-sm" style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={status} onChange={e => setStatus(e.target.value)}>
          <option value="open">open</option><option value="resolved">resolved</option><option value="abandoned">abandoned</option>
        </select>
      </label>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>重要性</span>
        <select className="w-full mt-1 px-3 py-2 rounded-lg text-sm" style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={importance} onChange={e => setImportance(e.target.value)}>
          <option value="critical">critical</option><option value="high">high</option><option value="medium">medium</option><option value="low">low</option>
        </select>
      </label>
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving} className="px-4 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>{saving ? "保存中..." : "保存"}</button>
        <button onClick={onClose} className="px-4 py-1.5 rounded-lg text-xs" style={{ color: "var(--text-2)", border: "1px solid var(--border)" }}>取消</button>
      </div>
    </div>
  );
}

export function LoopsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["loops", id], queryFn: () => getLoops(id!), enabled: !!id });

  const selectedData = selected ? data?.loops?.find((l: LoopItem) => l.id === selected) : null;

  const handleDelete = async (loopId: string) => {
    if (!confirm("确定删除此线索？")) return;
    await deleteLoop(id!, loopId);
    if (selected === loopId) setSelected(null);
    qc.invalidateQueries({ queryKey: ["loops", id] });
  };

  const columns = [
    { key: "id", header: "ID" },
    { key: "description", header: "描述" },
    { key: "importance", header: "重要性", render: (l: LoopItem) => {
      const v = l.importance ?? "medium";
      const color: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", high: "warning", medium: "info", low: "default" };
      return <Badge variant={color[v] || "default"}>{v}</Badge>;
    }},
    { key: "status", header: "状态", render: (l: LoopItem) => <Badge variant={l.status === "open" ? "warning" : "success"}>{l.status}</Badge> },
    { key: "__actions", header: "", render: (row: LoopItem) => (
      <button className="text-[11px] px-2 py-0.5 rounded" style={{ color: "#e8948c", border: "1px solid #e8948c33" }}
        onClick={(e) => { e.stopPropagation(); handleDelete(row.id); }}>删除</button>
    )},
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>故事线索 — 追踪已开启和已解决的剧情线索。点击线索查看详情，可编辑状态和重要性，也可直接删除。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="开放线索" columns={columns} data={data?.loops ?? []} loading={isLoading} onRowClick={(c: LoopItem) => { setSelected(c.id); setEditing(false); }} />
        {editing && selectedData ? (
          <LoopEditForm data={selectedData as unknown as Record<string,unknown>} projectId={id!} onClose={() => { setEditing(false); qc.invalidateQueries({queryKey:["loops",id]}); }} />
        ) : selectedData ? (
          <EntityDetail data={selectedData as unknown as Record<string,unknown>} onClose={() => setSelected(null)} onEdit={() => setEditing(true)} title={selectedData.description?.slice(0, 30) || selectedData.id} />
        ) : null}
      </div>
    </div>
  );
}
