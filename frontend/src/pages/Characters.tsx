import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { EntityDetail } from "../components/EntityDetail";
import { Badge } from "../components/ui/Badge";
import { CharacterEditModal } from "../components/CharacterEditModal";
import { getCharacters, getCharacter } from "../api/entities";
import type { CharacterItem } from "../types/entities";
import { PageHelp } from "../components/PageHelp";

export function CharactersPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState<boolean>(false);
  const { data: list, isLoading } = useQuery({ queryKey: ["characters", id], queryFn: () => getCharacters(id!), enabled: !!id });
  const { data: detail } = useQuery({ queryKey: ["character", id, selected], queryFn: () => getCharacter(id!, selected!), enabled: !!selected });

  const columns = [
    { key: "name", header: "名称" },
    { key: "role", header: "角色" },
    { key: "status", header: "状态", render: (c: CharacterItem) => <Badge variant={c.status === "active" ? "success" : "default"}>{c.status}</Badge> },
  ];

  return (
    <div className="h-full flex flex-col">
      <PageHelp>角色管理 — 浏览所有角色详情。点击角色查看详情，再点击「✎ 编辑」可修改角色设定并全局替换名称。也可前往「主角设定」编辑主角。</PageHelp>
      <div className="flex flex-col md:flex-row gap-4 md:gap-6 flex-1 min-h-0">
        <EntityList title="角色" columns={columns} data={list?.characters ?? []} loading={isLoading} onRowClick={(c: CharacterItem) => setSelected(c.id)} />
        {detail && (
          <EntityDetail
            data={detail as unknown as Record<string,unknown>}
            onClose={() => setSelected(null)}
            title={(detail.family_name || "") + (detail.first_name || "") || detail.id}
            onEdit={() => setEditing(true)}
          />
        )}
      </div>
      {editing && detail && id && (
        <CharacterEditModal
          open={editing}
          projectId={id}
          character={detail}
          onClose={() => setEditing(false)}
        />
      )}
    </div>
  );
}
