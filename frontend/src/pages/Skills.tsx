import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { listSkills, importSkill, deleteSkill, getActiveSkills, applyProjectSkills } from "../api/skills";

export function SkillsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [filePath, setFilePath] = useState("");

  const { data: allData, isLoading } = useQuery({ queryKey: ["skills"], queryFn: listSkills });
  const { data: activeData } = useQuery({
    queryKey: ["skills-active", id],
    queryFn: () => getActiveSkills(id!),
    enabled: !!id,
  });

  const importMut = useMutation({
    mutationFn: () => importSkill({ file_path: filePath }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["skills"] }); setFilePath(""); },
  });

  const deleteMut = useMutation({
    mutationFn: (slug: string) => deleteSkill(slug),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skills"] }),
  });

  const applyMut = useMutation({
    mutationFn: (ids: string[]) => applyProjectSkills(id!, ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skills-active", id] }),
  });

  if (isLoading) return <Spinner />;

  const skills = allData?.skills ?? [];
  const activeIds = new Set((activeData?.active ?? []).map(a => a.id));

  function toggleSkill(skillId: string) {
    if (!id) return;
    const next = new Set(activeIds);
    if (next.has(skillId)) next.delete(skillId);
    else next.add(skillId);
    applyMut.mutate([...next]);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>写作技能</h1>
        {activeIds.size > 0 && (
          <span className="text-xs px-2 py-1 rounded-full" style={{ background: "var(--accent)", color: "#fff" }}>
            {activeIds.size} 个已激活
          </span>
        )}
      </div>

      {/* 导入 */}
      <Card className="p-4">
        <p className="text-sm mb-3" style={{ color: "var(--text-2)" }}>导入小说文件，提取写作风格技能</p>
        <div className="flex gap-2">
          <Input value={filePath} onChange={setFilePath} placeholder="小说文件路径（.txt）" />
          <Button onClick={() => importMut.mutate()} loading={importMut.isPending} disabled={!filePath}>导入</Button>
        </div>
      </Card>

      {/* 技能库 */}
      {skills.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-2)" }}>暂无导入的技能</p>
      ) : (
        <>
          <p className="text-xs" style={{ color: "var(--text-3)" }}>点击技能卡片激活 / 取消激活，可同时激活多个技能进行风格融合</p>
          <div className="space-y-2">
            {skills.map(s => {
              const active = activeIds.has(s.id);
              return (
                <div
                  key={s.id}
                  className="rounded-xl p-4 flex items-start justify-between cursor-pointer transition-all"
                  style={{
                    border: active ? "1.5px solid var(--accent)" : "1.5px solid var(--border)",
                    background: active ? "color-mix(in srgb, var(--accent) 8%, var(--bg-surface))" : "var(--bg-surface)",
                    opacity: applyMut.isPending ? 0.6 : 1,
                  }}
                  onClick={() => toggleSkill(s.id)}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* 激活指示点 */}
                    <div className="mt-1 flex-shrink-0 w-2.5 h-2.5 rounded-full" style={{
                      background: active ? "var(--accent)" : "var(--border)",
                      boxShadow: active ? "0 0 6px var(--accent)" : "none",
                    }} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>{s.name}</p>
                        {active && <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--accent)", color: "#fff" }}>激活中</span>}
                      </div>
                      <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>
                        {s.genre} · {s.word_count?.toLocaleString()} 字 · {s.source_novel}
                      </p>
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {s.tags?.slice(0, 5).map(t => <Badge key={t} variant="info">{t}</Badge>)}
                      </div>
                    </div>
                  </div>
                  <div onClick={e => e.stopPropagation()}>
                    <Button
                      variant="ghost" size="sm"
                      onClick={() => { if (confirm("确认删除此技能？")) deleteMut.mutate(s.slug); }}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
