export interface CharacterItem {
  id: string;
  name: string;
  role: string;
  status: string;
  type?: string;
}

export interface CharacterDetail {
  id: string;
  first_name: string;
  family_name: string;
  title: string;
  nicknames: string[];
  role: string;
  description: string;
  backstory: string;
  personality: {
    core_traits: string[];
    fears: string[];
    desires: string[];
    flaws: string[];
  };
  physical_traits: {
    age: number | null;
    appearance: string;
    distinctive_features: string[];
  };
  current_state: {
    location_id: string | null;
    emotional_state: string;
    physical_state: string;
    emotion: { dominant: string; valence: number; arousal: number; intensity: number };
    inventory: string[];
    goals: string[];
    beliefs: string[];
  };
  relationships: { character_id: string; relationship_type: string; status: string; description: string }[];
  history: { tick: number; scene_id: string; summary: string; changes?: Record<string, unknown> }[];
  appearance_ticks: number[];
  last_scene_tick: number;
  pov_count: number;
  status_name: string; // active | sidelined | departed | deceased | returning
}

export interface LocationItem {
  id: string;
  name: string;
  type: string;
  atmosphere: string;
}

export interface LocationDetail {
  id: string;
  name: string;
  type: string;
  atmosphere: string;
  description: string;
  significance?: string;
  sensory_details?: { visual: string; auditory: string; olfactory: string; tactile: string };
  features?: string[];
  connections?: { location_id: string; connection_type: string; description: string }[];
  current_state?: { tension_level: number; time_of_day: string; weather: string; occupants: string[] };
}

export interface SceneItem {
  file: string;
  number: string;
  word_count: number;
  pov_character: string;
  tension_level: number | null;
  tension_category: string | null;
}

export interface SceneDetail {
  id: string;
  tick: number;
  title: string;
  pov_character_id: string;
  location_id: string;
  word_count: number;
  summary: string[];
  characters_present: string[];
  key_events: string[];
  emotional_beats?: string[];
  tension_level: number | null;
  tension_category: string | null;
  open_loops_created?: string[];
  open_loops_resolved?: string[];
}

export interface LoopItem {
  id: string;
  description: string;
  priority: number;
  status: string;
  importance?: string;
  category?: string;
  related_characters?: string[];
  scenes_mentioned?: number;
  is_story_goal?: boolean;
}

export interface FactionItem {
  id: string;
  name: string;
  org_type: string;
  importance: string;
  summary?: string;
  tags?: string[];
}

export interface FactionDetail {
  id: string;
  name: string;
  org_type: string;
  importance: string;
  summary?: string;
  tags?: string[];
  mandate_objectives?: string[];
  influence_domains?: string[];
  assets_resources?: string[];
  methods_tactics?: string[];
  stance_by_character?: Record<string, string>;
  relationships?: Record<string, string>;
}

export interface GraphNode {
  id: string; name: string; status: string;
  degree: number; colorGroup: number;
}
export interface GraphEdge {
  source: string; target: string; sourceName: string; targetName: string;
  type: string; status: string; description: string;
}
export interface RelationshipGraph {
  nodes: GraphNode[]; edges: GraphEdge[];
}
