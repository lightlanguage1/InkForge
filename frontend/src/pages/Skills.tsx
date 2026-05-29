import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { listSkills, importSkill, deleteSkill } from "../api/skills";

export function SkillsPage() {
  const qc = useQueryClient();
  const [filePath, setFilePath] = useState("");
  const { data, isLoading } = useQuery({ queryKey: ["skills"], queryFn: listSkills });
  const importMut = useMutation({ mutationFn: () => importSkill({ file_path: filePath }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["skills"] }); setFilePath(""); } });
  const deleteMut = useMutation({ mutationFn: (slug: string) => deleteSkill(slug), onSuccess: () => qc.invalidateQueries({ queryKey: ["skills"] }) });

  if (isLoading) return <Spinner />;
  const skills = data?.skills ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>写作技能</h1>
      </div>

      <Card className="p-4">
        <p className="text-sm mb-3" style={{ color: "var(--text-2)" }}>导入小说文件，提取写作风格技能</p>
        <div className="flex gap-2">
          <Input value={filePath} onChange={setFilePath} placeholder="小说文件路径（.txt）" />
          <Button onClick={() => importMut.mutate()} loading={importMut.isPending} disabled={!filePath}>导入</Button>
        </div>
      </Card>

      {skills.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-2)" }}>暂无导入的技能</p>
      ) : (
        <div className="space-y-2">
          {skills.map(s => (
            <Card key={s.id} className="p-4 flex items-start justify-between">
              <div>
                <p className="font-semibold text-sm" style={{ color: "var(--text-1)" }}>{s.name}</p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>
                  {s.genre} · {s.word_count?.toLocaleString()} 字 · 来源：{s.source_novel}
                </p>
                <div className="flex gap-1 mt-1.5 flex-wrap">
                  {s.tags?.slice(0, 5).map(t => <Badge key={t} variant="info">{t}</Badge>)}
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => { if (confirm("确认删除此技能？")) deleteMut.mutate(s.slug); }}>删除</Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
