import { post, upload } from "./client";
import type { ReferenceImportReq, ReferenceSearchReq, ReferenceSearchResult } from "../types/reference";

export function importReference(req: ReferenceImportReq) {
  return post<{ novel_id: string; title: string; chunk_count: number }>("/v1/references/import", req);
}

export function uploadReference(file: File, onProgress?: (pct: number) => void) {
  return upload<{ novel_id: string; title: string; chunk_count: number }>("/v1/references/import/upload", file, onProgress);
}

export function searchReferences(req: ReferenceSearchReq) {
  return post<{ results: ReferenceSearchResult[] }>("/v1/references/search", req);
}
