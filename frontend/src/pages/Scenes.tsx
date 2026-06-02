import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { Modal } from "../components/ui/Modal";
import { PageHelp } from "../components/PageHelp";
import { Badge } from "../components/ui/Badge";
import { getScenes, getScene } from "../api/entities";
import type { SceneItem } from "../types/entities";

export function ScenesPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list, isLoading } = useQuery({ queryKey: ["scenes", id], queryFn: () => getScenes(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["scene", id, selected], queryFn: () => getScene(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "number", header: "编号" },
    { key: "pov_character", header: "POV" },
    { key: "word_count", header: "字数" },
    { key: "tension_level", header: "张力", render: (s: SceneItem) => s.tension_level != null ? <Badge variant="info">{String(s.tension_level)}/10</Badge> : <span className="text-zinc-400">—</span> },
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>场景列表 — 查看已生成的所有场景。每行显示字数、POV 角色、张力等级。点击可查看场景完整详情。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="场景" columns={columns} data={list?.scenes ?? []} loading={isLoading}
          onRowClick={(s: SceneItem) => setSelected(`S${String(s.number).padStart(3, "0")}`)} />
        <Modal open={!!detail} title={`场景详情`} onClose={() => setSelected(null)}>
          {detail && (
          <div className="p-6 space-y-2 text-sm" style={{ overflowWrap: "break-word", wordBreak: "break-word" }}>
            <p><strong>标题:</strong> {detail.title}</p>
            <p><strong>POV:</strong> {detail.pov_character_id}</p>
            <p><strong>地点:</strong> {detail.location_id}</p>
            <p><strong>字数:</strong> {detail.word_count}</p>
            <p><strong>张力:</strong> {detail.tension_level}/10 ({detail.tension_category})</p>
            <p><strong>摘要:</strong> {detail.summary?.join("; ")}</p>
            <p><strong>关键事件:</strong> {detail.key_events?.join("; ") || "—"}</p>
          </div>
        )}
        </Modal>
      </div>
    </div>
  );
}
