import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Spinner } from "../components/ui/Spinner";
import { listCheckpoints, createCheckpoint, restoreCheckpoint, deleteCheckpoint } from "../api/checkpoints";
import { PageHelp } from "../components/PageHelp";

export function CheckpointsPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["checkpoints", id], queryFn: () => listCheckpoints(id!), enabled: !!id });
  const invalidateAll = () => { qc.invalidateQueries({ queryKey: ["checkpoints", id] }); qc.invalidateQueries({ queryKey: ["timeline", id] }); };
  const createMut = useMutation({ mutationFn: () => createCheckpoint(id!), onSuccess: invalidateAll });
  const restoreMut = useMutation({ mutationFn: (cid: string) => restoreCheckpoint(id!, cid), onSuccess: invalidateAll });
  const deleteMut = useMutation({ mutationFn: (cid: string) => deleteCheckpoint(id!, cid), onSuccess: invalidateAll });

  if (isLoading) return <Spinner />;
  const checkpoints = data?.checkpoints ?? [];

  return (
    <div className="space-y-6">
      <PageHelp>存档管理 — 查看和恢复自动存档点。每 3 章自动存档一次，也可手动创建。恢复存档会将故事回滚到存档时的状态。</PageHelp>
      <div className="flex items-center justify-between">
        <h1 className="font-semibold" style={{ fontSize: "1.375rem", color: "var(--text-1)" }}>存档管理</h1>
        <Button onClick={() => createMut.mutate()} loading={createMut.isPending}>创建存档</Button>
      </div>

      {checkpoints.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-2)" }}>暂无存档</p>
      ) : (
        <div className="space-y-2">
          {checkpoints.map(c => (
            <Card key={c.checkpoint_id} className="p-4 flex items-center justify-between">
              <div>
                <p className="font-semibold text-sm flex items-center gap-2" style={{ color: "var(--text-1)" }}>
                  {c.checkpoint_id}
                  <span className="text-[10px] px-1.5 py-0.5 rounded font-normal" style={{
                    background: c.created_by === "auto" ? "rgba(77,170,133,0.12)" : "rgba(200,151,90,0.12)",
                    color: c.created_by === "auto" ? "#4daa85" : "var(--accent)"
                  }}>{c.created_by === "auto" ? "自动" : "手动"}</span>
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>
                  第 {c.tick} 幕 · {c.scenes_count} 场景 · {c.characters_count} 角色 · {c.locations_count} 地点
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => restoreMut.mutate(c.checkpoint_id)} loading={restoreMut.isPending}>恢复</Button>
                <Button variant="ghost" size="sm" onClick={() => { if (confirm("确认删除此存档？")) deleteMut.mutate(c.checkpoint_id); }}>删除</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
