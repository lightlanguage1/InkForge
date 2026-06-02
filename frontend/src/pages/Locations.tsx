import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { getLocations, getLocation, updateLocation, deleteLocation } from "../api/entities";
import type { LocationItem } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

function LocationEditForm({ data, projectId, onClose }: { data: Record<string,unknown>; projectId: string; onClose: () => void }) {
  const locId = String(data.id ?? "");
  const [name, setName] = useState(String(data.name ?? ""));
  const [desc, setDesc] = useState(String(data.description ?? ""));
  const [atm, setAtm] = useState(String(data.atmosphere ?? ""));
  const [saving, setSaving] = useState(false);
  const handleSave = async () => {
    setSaving(true);
    await updateLocation(projectId, locId, { name, description: desc, atmosphere: atm });
    setSaving(false);
    onClose();
  };
  return (
    <div className="flex-1 rounded-xl p-5 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
      <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>编辑 {String(data.name ?? "")}</h3>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>名称</span>
        <input className="w-full mt-1 px-3 py-2 rounded-lg text-sm" style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={name} onChange={e => setName(e.target.value)} />
      </label>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>描述</span>
        <textarea className="w-full mt-1 px-3 py-2 rounded-lg text-sm" rows={3} style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={desc} onChange={e => setDesc(e.target.value)} />
      </label>
      <label className="block"><span className="text-xs" style={{ color: "var(--text-3)" }}>氛围</span>
        <input className="w-full mt-1 px-3 py-2 rounded-lg text-sm" style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} value={atm} onChange={e => setAtm(e.target.value)} />
      </label>
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving} className="px-4 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: "var(--accent)" }}>{saving ? "保存中..." : "保存"}</button>
        <button onClick={onClose} className="px-4 py-1.5 rounded-lg text-xs" style={{ color: "var(--text-2)", border: "1px solid var(--border)" }}>取消</button>
      </div>
    </div>
  );
}

export function LocationsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const { data: list, isLoading } = useQuery({ queryKey: ["locations", id], queryFn: () => getLocations(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["location", id, selected], queryFn: () => getLocation(id!, selected!), enabled: !!selected });

  const handleDelete = async (locId: string) => {
    if (!confirm("确定删除此地？")) return;
    await deleteLocation(id!, locId);
    if (selected === locId) setSelected(null);
    qc.invalidateQueries({ queryKey: ["locations", id] });
  };

  const columns = [
    { key: "name", header: "名称" },
    { key: "description", header: "描述" },
    { key: "atmosphere", header: "氛围" },
    { key: "__actions", header: "", render: (row: LocationItem) => (
      <button className="text-[11px] px-2 py-0.5 rounded" style={{ color: "#e8948c", border: "1px solid #e8948c33" }}
        onClick={(e) => { e.stopPropagation(); handleDelete(row.id); }}>删除</button>
    )},
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>地点管理 — 浏览故事中所有场景地点。点击左侧地点查看详情，右侧可编辑地点属性，也可直接删除。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="地点" columns={columns} data={list?.locations ?? []} loading={isLoading} onRowClick={(c: LocationItem) => { setSelected(c.id); setEditing(false); }} />
        {editing && detail ? (
          <LocationEditForm data={detail as unknown as Record<string,unknown>} projectId={id!} onClose={() => { setEditing(false); qc.invalidateQueries({queryKey:["locations",id]}); qc.invalidateQueries({queryKey:["location",id,selected]}); }} />
        ) : detail ? (
          <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={() => setSelected(null)} onEdit={() => setEditing(true)} title={detail.name} />
        ) : null}
      </div>
    </div>
  );
}
