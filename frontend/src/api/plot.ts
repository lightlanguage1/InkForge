import { get, post, del } from "./client";
import type { PlotStatus, BeatGenReq, BeatGenResult } from "../types/plot";

export function getPlotStatus(projectId: string) {
  return get<PlotStatus>(`/v1/project/${projectId}/plot`);
}

export function generateBeats(projectId: string, req?: BeatGenReq) {
  return post<BeatGenResult>(`/v1/project/${projectId}/plot/generate`, req);
}

export function clearBeats(projectId: string) {
  return del<{ cleared: boolean }>(`/v1/project/${projectId}/plot`);
}
