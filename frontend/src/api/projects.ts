import { get, post, del } from "./client";
import type { CreateProjectReq, ProjectInfo, ResumeResult } from "../types/project";

export function createProject(req: CreateProjectReq) {
  return post<{ project_path: string }>("/v1/project", req);
}

export function listProjects() {
  return get<{ projects: ProjectInfo[] }>("/v1/projects");
}

export function resume() {
  return post<ResumeResult>("/v1/resume");
}

export function deleteProject(projectId: string) {
  return del<{ deleted: string }>(`/v1/project/${encodeURIComponent(projectId)}`);
}

export function getCoverUrl(projectId: string, bust?: number) {
  const b = bust ? `?t=${bust}` : "";
  return `/api/v1/project/${encodeURIComponent(projectId)}/cover${b}`;
}

export async function uploadCover(projectId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const token = localStorage.getItem("inkforge_token");
  const r = await fetch(`/api/v1/project/${encodeURIComponent(projectId)}/cover`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form,
  });
  if (!r.ok) { const e = await r.json().catch(() => ({ detail: "error" })); throw new Error(e.detail); }
  return r.json() as Promise<{ ok: boolean; has_cover: boolean }>;
}

export async function removeCover(projectId: string) {
  return del<{ ok: boolean; has_cover: boolean }>(`/v1/project/${encodeURIComponent(projectId)}/cover`);
}
