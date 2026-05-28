import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EntityList } from "../components/EntityList";
import { Badge } from "../components/ui/Badge";
import { getLoops } from "../api/entities";
import type { LoopItem } from "../types/entities";

export function LoopsPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading } = useQuery({ queryKey: ["loops", id], queryFn: () => getLoops(id!), enabled: !!id });

  const columns = [
    { key: "description", header: "描述" },
    { key: "importance", header: "重要性", render: (l: LoopItem) => {
      const v = l.importance ?? "medium";
      const color: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", high: "warning", medium: "info", low: "default" };
      return <Badge variant={color[v] || "default"}>{v}</Badge>;
    }},
    { key: "status", header: "状态", render: (l: LoopItem) => <Badge variant={l.status === "open" ? "warning" : "success"}>{l.status}</Badge> },
  ];

  return <EntityList title="开放线索" columns={columns} data={data?.loops ?? []} loading={isLoading} />;
}
