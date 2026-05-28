export interface SkillInfo {
  id: string;
  slug: string;
  name: string;
  tags: string[];
  genre: string;
  source_novel: string;
  word_count: number;
}

export interface SkillImportReq {
  file_path: string;
  name?: string;
}

export interface SkillImportResult {
  skill_id: string;
  slug: string;
  name: string;
  style_tags: string[];
  patterns: number;
  archetypes: number;
}

export interface SkillApplyReq {
  project_path: string;
  skill_ids: string[];
  mode: string; // "reference" | "style_only" | "full"
}
