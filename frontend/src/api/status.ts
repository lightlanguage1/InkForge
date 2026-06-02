import { get, post, patch, del } from "./client";
import type { StatusInfo, GoalsInfo, LoreResult, LoreItem } from "../types/status";

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

export function updateLore(projectId: string, loreId: string, data: Record<string, unknown>) {
  return patch<LoreItem>(`/v1/project/${projectId}/lore/${loreId}`, data);
}

export function createLore(projectId: string, body: { content: string; category: string; lore_type: string; importance: string; tags: string[] }) {
  return post<LoreItem>(`/v1/project/${projectId}/lore`, body);
}

export function deleteLore(projectId: string, loreId: string) {
  return del<{ deleted: string }>(`/v1/project/${projectId}/lore/${loreId}`);
}
