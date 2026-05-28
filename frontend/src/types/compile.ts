export interface CompileReq {
  format?: string;     // "markdown" | "html" | "prose"
  include_metadata?: boolean;
  scene_range?: string; // "1-10" or "5,7,9"
}

export interface CompileResult {
  content: string;
  format: string;
}

export interface TitleReq {
  count?: number;
}
