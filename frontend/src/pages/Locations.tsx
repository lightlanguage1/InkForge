import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { getLocations, getLocation } from "../api/entities";
import type { LocationItem } from "../types/entities";

export function LocationsPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list, isLoading } = useQuery({ queryKey: ["locations", id], queryFn: () => getLocations(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["location", id, selected], queryFn: () => getLocation(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "name", header: "名称" },
    { key: "type", header: "类型" },
    { key: "atmosphere", header: "氛围" },
  ];

  return (
    <div className="flex gap-6 h-full">
      <EntityList title="地点" columns={columns} data={list?.locations ?? []} loading={isLoading} onRowClick={(c: LocationItem) => setSelected(c.id)} />
      {detail && <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={() => setSelected(null)} title={detail.name} />}
    </div>
  );
}
