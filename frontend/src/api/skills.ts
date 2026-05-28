import { get, post, del } from "./client";
import type { SkillInfo, SkillImportReq, SkillImportResult, SkillApplyReq } from "../types/skill";

export function listSkills() {
  return get<{ skills: SkillInfo[] }>("/v1/skills");
}

export function importSkill(req: SkillImportReq) {
  return post<SkillImportResult>("/v1/skills/import", req);
}

export function applySkills(req: SkillApplyReq) {
  return post<{ applied: number; skills: string[] }>("/v1/skills/apply", req);
}

export function deleteSkill(slug: string) {
  return del<{ deleted: string; name: string }>(`/v1/skills/${slug}`);
}
