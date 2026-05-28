import { get } from "./client";
import type { StatusInfo, GoalsInfo, LoreResult } from "../types/status";

export function getStatus(projectId: string) {
  return get<StatusInfo>(`/v1/project/${projectId}/status`);
}

export function getGoals(projectId: string) {
  return get<GoalsInfo>(`/v1/project/${projectId}/goals`);
}

export function getLore(projectId: string, params?: Record<string, string>) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return get<LoreResult>(`/v1/project/${projectId}/lore${qs}`);
}
