export interface CreateProjectReq {
  name: string;
  directory?: string;
  genre?: string;
  premise?: string;
  protagonist?: string;
  setting?: string;
  tone?: string;
  themes?: string;
  primary_goal?: string;
  use_plot_first?: boolean;
  skill_ids?: string[];
  style_id?: string;
  craft_id?: string;
}

export interface ProjectInfo {
  project_path: string;
  project_id?: string;
  novel_name?: string;
  current_tick?: number;
  has_cover?: boolean;
}

export interface ResumeResult {
  project_path: string;
  project_id: string;
  novel_name: string;
  current_tick: number;
}
