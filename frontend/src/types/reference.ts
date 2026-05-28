export interface ReferenceImportReq {
  file_path: string;
  title?: string;
}

export interface ReferenceSearchReq {
  query: string;
  top_k?: number;
  source_filter?: string;
}

export interface ReferenceSearchResult {
  source?: string;
  chapter?: string;
  text?: string;
  relevance?: number;
}
