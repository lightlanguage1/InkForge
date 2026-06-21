import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { Badge } from "../components/ui/Badge";
import { getFactions, getFaction, updateFaction, deleteFaction, getCharacters } from "../api/entities";
import type { FactionItem, FactionDetail } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

const STANCE_LABELS: Record<string, string> = {
  friendly: "友好", neutral: "中立", hostile: "敌对",
  exploitative: "利用", unknown: "未知",
};

export function FactionsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const { data: list, isLoading } = useQuery({ queryKey: ["factions", id], queryFn: () => getFactions(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["faction", id, selected], queryFn: () => getFaction(id!, selected!), enabled: !!selected });
  const { data: charsData } = useQuery({ queryKey: ["characters", id], queryFn: () => getCharacters(id!), enabled: !!id });

  // Build character name map for stance display
  const charNames = (charsData?.characters ?? []).reduce((acc, c) => { acc[c.id] = c.name; return acc; }, {} as Record<string, string>);

  const handleDelete = (f: FactionItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!id || !confirm(`删除势力「${f.name}」？`)) return;
    deleteFaction(id, f.id).then(() => {
      qc.invalidateQueries({ queryKey: ["factions", id] });
      if (selected === f.id) setSelected(null);
    }).catch(err => alert(`删除失败: ${err?.message ?? err}`));
  };

  const startEdit = () => {
    if (!detail) return;
    setEditForm({
      name: detail.name || "",
      org_type: detail.org_type || "",
      summary: detail.summary || "",
      importance: detail.importance || "medium",
    });
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!id || !selected) return;
    await updateFaction(id, selected, editForm);
    qc.invalidateQueries({ queryKey: ["factions", id] });
    qc.invalidateQueries({ queryKey: ["faction", id, selected] });
    setEditing(false);
  };

  const columns = [
    { key: "name", header: "名称" },
    { key: "org_type", header: "类型" },
    { key: "importance", header: "重要性", render: (f: FactionItem) => {
      const v = f.importance ?? "medium";
      const color: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", high: "warning", medium: "info", low: "default" };
      return <Badge variant={color[v] || "default"}>{v}</Badge>;
    }},
    { key: "actions", header: "", render: (f: FactionItem) => (
      <button onClick={(e) => handleDelete(f, e)}
        className="text-xs px-2.5 py-1 rounded transition-colors"
        style={{ color: "#e88c8c", border: "1px solid rgba(200,80,80,0.25)" }}
        onMouseEnter={e => { e.currentTarget.style.background = "rgba(180,40,40,0.12)"; e.currentTarget.style.borderColor = "rgba(200,80,80,0.5)"; }}
        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "rgba(200,80,80,0.25)"; }}
      >删除</button>
    )},
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>势力管理 — 浏览故事中的组织、门派、阵营等势力实体。点击查看详情后可编辑或删除。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="势力" columns={columns} data={list?.factions ?? []} loading={isLoading} onRowClick={(f: FactionItem) => setSelected(f.id)} />
        {detail && (
          <div className="flex-1 min-w-0">
            {editing ? (
              <div className="p-4 rounded-xl space-y-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
                <h3 className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>编辑势力</h3>
                {[
                  ["name", "名称"], ["org_type", "类型"], ["summary", "概述"],
                ].map(([key, label]) => (
                  <div key={key}>
                    <label className="text-[11px] block mb-1" style={{ color: "var(--text-3)" }}>{label}</label>
                    {key === "summary" ? (
                      <textarea value={editForm[key] || ""} onChange={e => setEditForm(p => ({ ...p, [key]: e.target.value }))}
                        rows={3} className="w-full text-[12px] px-3 py-2 rounded-lg outline-none resize-none"
                        style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
                    ) : (
                      <input value={editForm[key] || ""} onChange={e => setEditForm(p => ({ ...p, [key]: e.target.value }))}
                        className="w-full text-[12px] px-3 py-2 rounded-lg outline-none"
                        style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }} />
                    )}
                  </div>
                ))}
                <div>
                  <label className="text-[11px] block mb-1" style={{ color: "var(--text-3)" }}>重要性</label>
                  <select value={editForm.importance || "medium"} onChange={e => setEditForm(p => ({ ...p, importance: e.target.value }))}
                    className="text-[12px] px-3 py-2 rounded-lg outline-none"
                    style={{ background: "var(--bg-base)", border: "1px solid var(--border)", color: "var(--text-1)" }}>
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                    <option value="critical">关键</option>
                  </select>
                </div>
                <div className="flex gap-2">
                  <button onClick={saveEdit} className="px-4 py-2 rounded-lg text-[12px] font-medium"
                    style={{ background: "var(--accent)", color: "var(--bg-base)", border: "none", cursor: "pointer" }}>保存</button>
                  <button onClick={() => setEditing(false)} className="px-4 py-2 rounded-lg text-[12px]"
                    style={{ background: "transparent", color: "var(--text-3)", border: "1px solid var(--border)", cursor: "pointer" }}>取消</button>
                </div>
              </div>
            ) : (
              <FactionDetailView detail={detail} charNames={charNames} onClose={() => setSelected(null)} onEdit={startEdit} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** 势力详情面板 — 补充立场表和扩展字段 */
function FactionDetailView({ detail, charNames, onClose, onEdit }: {
  detail: FactionDetail; charNames: Record<string, string>;
  onClose: () => void; onEdit?: () => void;
}) {
  const stanceEntries = detail.stance_by_character ? Object.entries(detail.stance_by_character) : [];
  const factionRels = detail.relationships ? Object.entries(detail.relationships) : [];

  return (
    <div className="flex flex-col gap-3">
      <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={onClose} title={detail.name} onEdit={onEdit} />

      {/* 立场表 */}
      {stanceEntries.length > 0 && (
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>
            <h4 className="font-semibold text-xs" style={{ color: "var(--text-2)" }}>对各角色立场</h4>
          </div>
          <div className="p-3 space-y-1.5">
            {stanceEntries.map(([charId, stance]) => {
              const label = STANCE_LABELS[stance] || stance;
              const color = stance === "friendly" ? "#4daa85" : stance === "hostile" ? "#e88c8c" : stance === "neutral" ? "#c8975a" : "var(--text-3)";
              return (
                <div key={charId} className="flex justify-between items-center text-xs">
                  <span style={{ color: "var(--text-2)" }}>{charNames[charId] || charId}</span>
                  <span style={{ color, fontWeight: 600 }}>{label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 势力间关系 */}
      {factionRels.length > 0 && (
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>
            <h4 className="font-semibold text-xs" style={{ color: "var(--text-2)" }}>势力间关系</h4>
          </div>
          <div className="p-3 space-y-1.5">
            {factionRels.map(([fid, rel]) => (
              <div key={fid} className="flex justify-between items-center text-xs">
                <span style={{ color: "var(--text-2)" }}>{fid}</span>
                <Badge variant={rel === "ally" ? "success" : rel === "rival" ? "danger" : "info"}>{rel}</Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 扩展字段：目标 / 手段 / 资产 */}
      {(detail.mandate_objectives?.length || detail.methods_tactics?.length || detail.assets_resources?.length) ? (
        <div className="rounded-xl overflow-hidden" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="px-4 py-2.5" style={{ borderBottom: "1px solid var(--border)" }}>
            <h4 className="font-semibold text-xs" style={{ color: "var(--text-2)" }}>详细属性</h4>
          </div>
          <div className="p-3 space-y-2 text-xs">
            {detail.mandate_objectives?.length ? (
              <div><span style={{ color: "var(--text-3)" }}>目标：</span><span style={{ color: "var(--text-2)" }}>{detail.mandate_objectives.join("、")}</span></div>
            ) : null}
            {detail.influence_domains?.length ? (
              <div><span style={{ color: "var(--text-3)" }}>势力范围：</span><span style={{ color: "var(--text-2)" }}>{detail.influence_domains.join("、")}</span></div>
            ) : null}
            {detail.methods_tactics?.length ? (
              <div><span style={{ color: "var(--text-3)" }}>手段策略：</span><span style={{ color: "var(--text-2)" }}>{detail.methods_tactics.join("、")}</span></div>
            ) : null}
            {detail.assets_resources?.length ? (
              <div><span style={{ color: "var(--text-3)" }}>资产资源：</span><span style={{ color: "var(--text-2)" }}>{detail.assets_resources.join("、")}</span></div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
