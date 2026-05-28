import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Select } from "../components/ui/Select";
import { Spinner } from "../components/ui/Spinner";
import { getLore } from "../api/status";
import type { LoreItem } from "../types/status";

export function LorePage() {
  const { id } = useParams<{ id: string }>();
  const [category, setCategory] = useState("");
  const [loreType, setLoreType] = useState("");
  const [importance, setImportance] = useState("");

  const params: Record<string, string> = {};
  if (category) params.category = category;
  if (loreType) params.lore_type = loreType;
  if (importance) params.importance = importance;

  const { data, isLoading } = useQuery({
    queryKey: ["lore", id, params],
    queryFn: () => getLore(id!, params),
    enabled: !!id,
  });

  const impColor: Record<string, "warning" | "danger" | "default" | "info"> = { critical: "danger", important: "warning", normal: "info", minor: "default" };

  return (
    <div>
      <h1 className="text-xl font-semibold text-zinc-900 tracking-tight mb-4">世界观</h1>
      <div className="flex gap-4 mb-4">
        <Select label="类别" value={category} onChange={setCategory}
          options={[{ value: "", label: "全部" }, { value: "magic", label: "魔法" }, { value: "technology", label: "科技" }, { value: "society", label: "社会" }, { value: "physics", label: "物理" }, { value: "biology", label: "生物" }]} />
        <Select label="类型" value={loreType} onChange={setLoreType}
          options={[{ value: "", label: "全部" }, { value: "rule", label: "规则" }, { value: "fact", label: "事实" }, { value: "constraint", label: "约束" }, { value: "capability", label: "能力" }, { value: "limitation", label: "限制" }]} />
        <Select label="重要性" value={importance} onChange={setImportance}
          options={[{ value: "", label: "全部" }, { value: "critical", label: "关键" }, { value: "important", label: "重要" }, { value: "normal", label: "普通" }, { value: "minor", label: "次要" }]} />
      </div>
      {isLoading ? <Spinner /> : (
        <div className="space-y-3">
          <p className="text-sm text-zinc-500">共 {data?.total_count ?? 0} 条</p>
          {(data?.lore ?? []).map((l: LoreItem) => (
            <Card key={l.id} className="p-4">
              <div className="flex items-start gap-2 mb-1">
                <Badge variant={impColor[l.importance] || "default"}>{l.importance}</Badge>
                <Badge variant="default">{l.type}</Badge>
                <span className="text-xs text-zinc-400">{l.category} · 来源: {l.source_scene || `tick ${l.tick}`}</span>
              </div>
              <p className="text-sm">{l.content}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
