import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { Badge } from "../components/ui/Badge";
import { getFactions, getFaction } from "../api/entities";
import type { FactionItem } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

export function FactionsPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list, isLoading } = useQuery({ queryKey: ["factions", id], queryFn: () => getFactions(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["faction", id, selected], queryFn: () => getFaction(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "name", header: "名称" },
    { key: "org_type", header: "类型" },
    { key: "importance", header: "重要性", render: (f: FactionItem) => {
      const v = f.importance ?? "medium";
      const color: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", high: "warning", medium: "info", low: "default" };
      return <Badge variant={color[v] || "default"}>{v}</Badge>;
    }},
  ];
  return (
    <div className="h-full flex flex-col">
      <PageHelp>势力管理 — 浏览故事中的组织、门派、阵营等势力实体。点击左侧势力查看详情，包含目标、影响范围、资产等信息。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="势力" columns={columns} data={list?.factions ?? []} loading={isLoading} onRowClick={(f: FactionItem) => setSelected(f.id)} />
        {detail && <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={() => setSelected(null)} title={detail.name} />}
      </div>
    </div>
  );
}
