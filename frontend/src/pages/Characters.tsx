import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { Badge } from "../components/ui/Badge";
import { getCharacters, getCharacter } from "../api/entities";
import type { CharacterItem } from "../types/entities";

export function CharactersPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const { data: list, isLoading } = useQuery({ queryKey: ["characters", id], queryFn: () => getCharacters(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["character", id, selected], queryFn: () => getCharacter(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "name", header: "名称" },
    { key: "role", header: "角色" },
    { key: "status", header: "状态", render: (c: CharacterItem) => <Badge variant={c.status === "active" ? "success" : "default"}>{c.status}</Badge> },
  ];

  return (
    <div className="flex gap-6 h-full">
      <EntityList title="角色" columns={columns} data={list?.characters ?? []} loading={isLoading} onRowClick={(c: CharacterItem) => setSelected(c.id)} />
      {detail && <EntityDetail data={detail as unknown as Record<string,unknown>} onClose={() => setSelected(null)} title={detail.first_name || detail.id} />}
    </div>
  );
}
