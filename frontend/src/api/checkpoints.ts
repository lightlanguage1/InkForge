import { get, post, del } from "./client";
import type { CheckpointItem, CheckpointCreateReq } from "../types/checkpoint";

export function listCheckpoints(projectId: string) {
  return get<{ checkpoints: CheckpointItem[] }>(`/v1/project/${projectId}/checkpoints`);
}

export function createCheckpoint(projectId: string, req?: CheckpointCreateReq) {
  return post<{ checkpoint_id: string; path: string }>(`/v1/project/${projectId}/checkpoints`, req);
}

export function restoreCheckpoint(projectId: string, checkpointId: string) {
  return post<{ restored: string }>(`/v1/project/${projectId}/checkpoints/${checkpointId}/restore`);
}

export function deleteCheckpoint(projectId: string, checkpointId: string) {
  return del<{ deleted: string }>(`/v1/project/${projectId}/checkpoints/${checkpointId}`);
}
