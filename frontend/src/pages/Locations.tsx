import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { getLocations, getLocation } from "../api/entities";
import type { LocationItem } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

export function LocationsPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list, isLoading } = useQuery({ queryKey: ["locations", id], queryFn: () => getLocations(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["location", id, selected], queryFn: () => getLocation(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "name", header: "名称" },
    { key: "description", header: "描述" },
    { key: "atmosphere", header: "氛围" },
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>地点管理 — 浏览故事中所有场景地点。点击左侧地点查看详情，包含氛围、感官细节、关联角色等信息。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="地点" columns={columns} data={list?.locations ?? []} loading={isLoading} onRowClick={(c: LocationItem) => setSelected(c.id)} />
        {detail && <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={() => setSelected(null)} title={detail.name} />}
      </div>
    </div>
  );
}
