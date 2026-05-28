import { get, post } from "./client";
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
