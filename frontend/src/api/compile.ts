import { get, post } from "./client";
import type { CompileReq, CompileResult, TitleReq } from "../types/compile";

export function compile(projectId: string, req?: CompileReq) {
  return post<CompileResult>(`/v1/project/${projectId}/compile`, req);
}

export function summarize(projectId: string) {
  return get<{ content: string }>(`/v1/project/${projectId}/summarize`);
}

export function generateTitles(projectId: string, req?: TitleReq) {
  return post<{ titles: string[] }>(`/v1/project/${projectId}/titles`, req);
}
