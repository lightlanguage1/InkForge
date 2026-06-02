import { get, post, patch, del } from "./client";
import type { PlotStatus, BeatGenReq, BeatGenResult } from "../types/plot";

export function getPlotStatus(projectId: string) {
  return get<PlotStatus>(`/v1/project/${projectId}/plot`);
}

export function generateBeats(projectId: string, req?: BeatGenReq) {
  return post<BeatGenResult>(`/v1/project/${projectId}/plot/generate`, req);
}

export function updateBeat(projectId: string, beatId: string, data: Record<string, unknown>) {
  return patch<{ updated: string }>(`/v1/project/${projectId}/plot/beats/${beatId}`, data);
}

export function deleteBeat(projectId: string, beatId: string) {
  return del<{ deleted: string }>(`/v1/project/${projectId}/plot/beats/${beatId}`);
}

export function clearBeats(projectId: string) {
  return del<{ cleared: boolean }>(`/v1/project/${projectId}/plot`);
}
