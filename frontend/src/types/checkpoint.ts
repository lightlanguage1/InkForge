export interface CheckpointItem {
  checkpoint_id: string;
  tick: number;
  timestamp: string;
  scenes_count: number;
  characters_count: number;
  locations_count: number;
  size_bytes: number;
  created_by: string;
}

export interface CheckpointCreateReq {
  message?: string;
}
