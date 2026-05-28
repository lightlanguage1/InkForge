export interface TickRequest {
  project_path?: string;
  save_prompts?: boolean;
  llm_backend?: string;
  llm_model?: string;
  notes?: string;
}

export interface TickResponse {
  success: boolean;
  tick: number;
  scene_id: string;
  scene_file: string;
  word_count: number;
  actions_executed: number;
  tension?: { level: number; category: string };
}

export interface TickResultItem {
  tick: number;
  scene_id: string;
  word_count: number;
}

export interface RunResult {
  results: TickResultItem[];
  completed: number;
}
