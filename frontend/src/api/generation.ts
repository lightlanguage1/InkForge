import { post } from "./client";
import type { TickRequest, TickResponse, RunResult } from "../types/generation";

const BASE = "/api";  // not proxied for SSE

export function runTick(projectId: string, req?: TickRequest) {
  return post<TickResponse>(`/v1/project/${projectId}/tick`, req);
}

export function tickEventSource(projectId: string): EventSource {
  return new EventSource(`${BASE}/v1/project/${projectId}/tick/stream`);
}

export function runMultiple(projectId: string, n: number) {
  return post<RunResult>(`/v1/project/${projectId}/run?n=${n}`);
}
