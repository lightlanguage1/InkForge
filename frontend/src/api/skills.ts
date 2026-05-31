import { get, post, upload, del } from "./client";
import type { SkillInfo, SkillImportReq, SkillImportResult, ActiveSkillRef } from "../types/skill";

export function listSkills() {
  return get<{ skills: SkillInfo[] }>("/v1/skills");
}

export function importSkill(req: SkillImportReq) {
  return post<SkillImportResult>("/v1/skills/import", req);
}

export function uploadSkill(file: File) {
  return upload<SkillImportResult>("/v1/skills/import/upload", file);
}

export function getActiveSkills(projectId: string) {
  return get<{ active: ActiveSkillRef[] }>(`/v1/project/${projectId}/skills/active`);
}

export function applyProjectSkills(projectId: string, skillIds: string[], mode = "reference") {
  return post<{ applied: number; skills: string[] }>(`/v1/project/${projectId}/skills/apply`, { skill_ids: skillIds, mode });
}

export function deleteSkill(slug: string) {
  return del<{ deleted: string; name: string }>(`/v1/skills/${slug}`);
}
