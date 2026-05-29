export interface StatusInfo {
  project_id: string;
  current_tick: number;
  novel_name: string;
  scene_count: number;
  character_count: number;
  location_count: number;
  faction_count: number;
  open_loops_count: number;
  lore_count: number;
  word_count: number;
  avg_tension: number;
  generating?: boolean;
  genre?: string;
}

export interface GoalsInfo {
  story_goal: { description: string; promoted_at_tick: number; loop_id: string } | null;
  secondary_goals: { description: string }[];
  protagonist_id: string | null;
  protagonist_name: string | null;
  protagonist_goals: {
    immediate: string[];
    arc_goal: string | null;
    story_goal: string | null;
    progress: Record<string, number>;
    completed: string[];
    abandoned: string[];
  } | null;
  story_goal_loops: {
    id: string;
    description: string;
    category: string;
    importance: string;
    scenes_mentioned: number;
    created_in_scene: string;
  }[];
  current_tick: number;
}

export interface LoreItem {
  id: string;
  type: string;
  category: string;
  content: string;
  importance: string;
  source_scene: string;
  tick: string | number;
  tags: string[];
  contradictions?: unknown[];
}

export interface LoreResult {
  total_count: number;
  importance_counts: Record<string, number>;
  lore: LoreItem[];
}

export interface LoreParams {
  category?: string;
  lore_type?: string;
  importance?: string;
}
