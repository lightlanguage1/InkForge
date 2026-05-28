export interface PlotStatus {
  total_beats: number;
  pending: number;
  in_progress: number;
  completed: number;
  skipped: number;
  current_arc: string | null;
  arc_progress: number | null;
  created_at: string;
  last_updated: string;
  duplicate_ids: string[];
  missing_prerequisites: { beat_id: string; prerequisite: string }[];
}

export interface BeatGenReq {
  count?: number;
}

export interface BeatInfo {
  id: string;
  description: string;
  characters_involved: string[];
  location: string | null;
  tension_target: number | null;
  status: string;
}

export interface BeatGenResult {
  generated: number;
  beats: BeatInfo[];
}
