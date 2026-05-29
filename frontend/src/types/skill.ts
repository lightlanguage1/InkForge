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

export interface ActiveSkillRef {
  id: string;
  name: string;
  mode: string;
}
