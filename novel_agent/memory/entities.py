"""Entity dataclasses for memory system."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


# ============================================================================
# Helper Classes
# ============================================================================

@dataclass
class PhysicalTraits:
    """Physical characteristics of a character."""
    age: Optional[int] = None
    appearance: str = ""
    distinctive_features: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhysicalTraits":
        return cls(**data)


# ============================================================================
# Faction Entity (Organizations/Groups)
# ============================================================================

@dataclass
class Faction:
    """Organizational entity to ground groups (corporate, guild, agency, etc.)."""
    id: str
    type: str = "faction"
    created_at: str = ""
    updated_at: str = ""

    # Core identity
    name: str = ""
    org_type: str = "other"  # 由 LLM 根据故事语境自行归类
    summary: str = ""

    # Capabilities and position
    mandate_objectives: List[str] = field(default_factory=list)
    influence_domains: List[str] = field(default_factory=list)
    assets_resources: List[str] = field(default_factory=list)
    methods_tactics: List[str] = field(default_factory=list)

    # Relations
    stance_by_character: Dict[str, str] = field(default_factory=dict)  # char_id -> friendly|neutral|hostile|exploitative|unknown
    relationships: Dict[str, str] = field(default_factory=dict)  # faction_id -> ally|rival|parent|subsidiary|unknown

    # Meta
    importance: str = "medium"  # low|medium|high|critical
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Faction":
        return cls(**data)


@dataclass
class Personality:
    """Personality traits and motivations."""
    core_traits: List[str] = field(default_factory=list)
    fears: List[str] = field(default_factory=list)
    desires: List[str] = field(default_factory=list)
    flaws: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Personality":
        return cls(**data)


@dataclass
class Relationship:
    """Relationship between a character and another character."""
    character_id: str
    relationship_type: str  # mentor, friend, rival, enemy, family, etc.
    status: str  # close, strained, hostile, unknown, etc.
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Relationship":
        return cls(**data)


@dataclass
class EmotionState:
    """Structured emotion with valence / arousal dimensions."""
    dominant: str = ""   # e.g., 愤怒, 悲伤, 恐惧, 喜悦, 平静
    valence: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    arousal: float = 0.0  # 0.0 (calm) to 1.0 (intense)
    intensity: float = 0.5  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmotionState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Mapping from Chinese emotion labels to EmotionState values
EMOTION_MAP: Dict[str, EmotionState] = {
    "愤怒": EmotionState(dominant="愤怒", valence=-0.8, arousal=0.9, intensity=0.9),
    "暴怒": EmotionState(dominant="暴怒", valence=-0.9, arousal=1.0, intensity=1.0),
    "悲伤": EmotionState(dominant="悲伤", valence=-0.7, arousal=0.3, intensity=0.7),
    "哀恸": EmotionState(dominant="哀恸", valence=-0.9, arousal=0.4, intensity=0.9),
    "恐惧": EmotionState(dominant="恐惧", valence=-0.6, arousal=0.8, intensity=0.8),
    "绝望": EmotionState(dominant="绝望", valence=-1.0, arousal=0.2, intensity=1.0),
    "焦虑": EmotionState(dominant="焦虑", valence=-0.4, arousal=0.7, intensity=0.6),
    "喜悦": EmotionState(dominant="喜悦", valence=0.8, arousal=0.6, intensity=0.7),
    "兴奋": EmotionState(dominant="兴奋", valence=0.9, arousal=0.9, intensity=0.9),
    "平静": EmotionState(dominant="平静", valence=0.3, arousal=0.1, intensity=0.3),
    "冷静": EmotionState(dominant="冷静", valence=0.2, arousal=0.2, intensity=0.4),
    "坚定": EmotionState(dominant="坚定", valence=0.5, arousal=0.5, intensity=0.7),
    "疲惫": EmotionState(dominant="疲惫", valence=-0.1, arousal=0.1, intensity=0.4),
    "释然": EmotionState(dominant="释然", valence=0.4, arousal=0.1, intensity=0.4),
    "愧疚": EmotionState(dominant="愧疚", valence=-0.5, arousal=0.4, intensity=0.6),
    "警惕": EmotionState(dominant="警惕", valence=-0.2, arousal=0.6, intensity=0.6),
}


@dataclass
class CurrentState:
    """Current state of a character."""
    location_id: Optional[str] = None
    emotional_state: str = ""
    emotion: EmotionState = field(default_factory=EmotionState)
    emotion_history: List[Dict[str, Any]] = field(default_factory=list)
    physical_state: str = ""
    inventory: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    beliefs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["emotion"] = self.emotion.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CurrentState":
        emotion_data = data.get("emotion", {}) or {}
        emotion_history = data.get("emotion_history", []) or []
        return cls(
            location_id=data.get("location_id"),
            emotional_state=data.get("emotional_state", ""),
            emotion=EmotionState.from_dict(emotion_data),
            emotion_history=emotion_history,
            physical_state=data.get("physical_state", ""),
            inventory=data.get("inventory", []) or [],
            goals=data.get("goals", []) or [],
            beliefs=data.get("beliefs", []) or [],
        )


@dataclass
class HistoryEntry:
    """History entry for tracking entity changes over time."""
    tick: int
    scene_id: str
    changes: Dict[str, Any]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        return cls(**data)


@dataclass
class SensoryDetails:
    """Sensory details for a location."""
    visual: str = ""
    auditory: str = ""
    olfactory: str = ""
    tactile: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SensoryDetails":
        return cls(**data)


@dataclass
class LocationConnection:
    """Connection between locations."""
    location_id: str
    connection_type: str  # adjacent, distant, portal, hidden, etc.
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationConnection":
        return cls(**data)


@dataclass
class LocationState:
    """Current state of a location."""
    tension_level: int = 0  # 0-10 scale
    time_of_day: str = ""
    weather: str = ""
    occupants: List[str] = field(default_factory=list)  # Character IDs
    notable_objects: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationState":
        return cls(**data)


@dataclass
class RelationshipHistoryEntry:
    """History entry for relationship changes."""
    tick: int
    scene_id: str
    event: str
    status_change: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipHistoryEntry":
        return cls(**data)


# ============================================================================
# Main Entity Classes
# ============================================================================

@dataclass
class Character:
    """Character entity with full attributes."""
    id: str
    type: str = "character"
    created_at: str = ""
    updated_at: str = ""
    
    # Name fields
    first_name: str = ""
    family_name: str = ""
    title: str = ""  # Dr., Captain, Lord, etc.
    nicknames: List[str] = field(default_factory=list)  # Informal names
    
    role: str = ""  # protagonist, antagonist, supporting, minor
    description: str = ""
    physical_traits: PhysicalTraits = field(default_factory=PhysicalTraits)
    personality: Personality = field(default_factory=Personality)
    relationships: List[Relationship] = field(default_factory=list)
    current_state: CurrentState = field(default_factory=CurrentState)
    backstory: str = ""
    history: List[HistoryEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # NEW: Goal hierarchy (Phase 7A.2)
    immediate_goals: List[str] = field(default_factory=list)  # "Fix the antenna"
    arc_goal: Optional[str] = None  # "Overcome isolation and trust others"
    story_goal: Optional[str] = None  # "Make contact with alien intelligence"
    
    # NEW: Goal tracking
    goal_progress: Dict[str, float] = field(default_factory=dict)  # goal -> progress (0.0-1.0)
    goals_completed: List[str] = field(default_factory=list)
    goals_abandoned: List[str] = field(default_factory=list)

    # NEW: Character lifecycle
    status: str = "active"  # active | sidelined | departed | deceased | returning
    last_scene_tick: int = -1
    appearance_ticks: List[int] = field(default_factory=list)
    off_screen_note: str = ""  # 离场原因 / 当前在做什么
    @property
    def full_name(self) -> str:
        """Get full name: family_name + first_name (Chinese convention)."""
        core = (self.family_name or "") + (self.first_name or "")
        if self.title:
            return f"{self.title} {core}" if core else self.title
        return core if core else "Unnamed"
    
    @property
    def display_name(self) -> str:
        """Get name for prose (first name, or full name if no first name)."""
        return self.first_name if self.first_name else self.full_name
    
    @property
    def name(self) -> str:
        """Backward compatibility property."""
        return self.full_name
    
    def __post_init__(self):
        """Set timestamps and handle migration."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert nested objects
        if isinstance(self.physical_traits, PhysicalTraits):
            data['physical_traits'] = self.physical_traits.to_dict()
        if isinstance(self.personality, Personality):
            data['personality'] = self.personality.to_dict()
        if isinstance(self.current_state, CurrentState):
            data['current_state'] = self.current_state.to_dict()
        data['relationships'] = [r.to_dict() if isinstance(r, Relationship) else r for r in self.relationships]
        data['history'] = [h.to_dict() if isinstance(h, HistoryEntry) else h for h in self.history]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        """Create from dictionary with migration support."""
        # Migrate old 'name' field to first_name/family_name
        if 'name' in data and not data.get('first_name'):
            old_name = data.pop('name')
            # Try to split intelligently
            parts = old_name.strip().split()
            if len(parts) >= 2:
                data['first_name'] = parts[0]
                data['family_name'] = ' '.join(parts[1:])
            elif len(parts) == 1:
                data['first_name'] = parts[0]
        
        # Migrate old 'aliases' to 'nicknames'
        if 'aliases' in data and not data.get('nicknames'):
            data['nicknames'] = data.pop('aliases')
        
        # Convert nested objects
        if 'physical_traits' in data and isinstance(data['physical_traits'], dict):
            data['physical_traits'] = PhysicalTraits.from_dict(data['physical_traits'])
        if 'personality' in data and isinstance(data['personality'], dict):
            data['personality'] = Personality.from_dict(data['personality'])
        if 'current_state' in data and isinstance(data['current_state'], dict):
            data['current_state'] = CurrentState.from_dict(data['current_state'])
        if 'relationships' in data:
            data['relationships'] = [
                Relationship.from_dict(r) if isinstance(r, dict) else r 
                for r in data['relationships']
            ]
        if 'history' in data:
            data['history'] = [
                HistoryEntry.from_dict(h) if isinstance(h, dict) else h 
                for h in data['history']
            ]
        return cls(**data)

    def reset_dynamic_state(self):
        """清空由场景累积的动态状态，保留角色身份属性不变。"""
        self.history = []
        self.current_state.inventory = []
        self.current_state.goals = []
        self.current_state.beliefs = []
        self.current_state.emotional_state = ""
        self.current_state.physical_state = ""
        self.current_state.emotion_history = []
        self.current_state.location_id = None
        self.appearance_ticks = []
        self.last_scene_tick = -1

    @staticmethod
    def _parse_added(change) -> list:
        """解析 changes 中的列表追加记录，兼容新旧格式。"""
        if isinstance(change, list):
            return change
        if isinstance(change, str) and change.startswith("added:"):
            import ast
            try:
                return ast.literal_eval(change[6:].strip())
            except (ValueError, SyntaxError):
                return []
        return []

    def replay_history(self, entries):
        """按 tick 顺序重放 history 条目，重建 dynamic_state。"""
        sorted_entries = sorted(entries, key=lambda e: e.tick)
        for entry in sorted_entries:
            for field, change in entry.changes.items():
                if field in ("inventory", "goals", "beliefs"):
                    added = self._parse_added(change)
                    current = getattr(self.current_state, field, [])
                    for item in added:
                        if item not in current:
                            current.append(item)
                    setattr(self.current_state, field, current)
                elif field == "emotional_state":
                    val = change.get("new", change) if isinstance(change, dict) else change
                    if val:
                        self.current_state.emotional_state = str(val)
                elif field == "physical_state":
                    val = change.get("new", change) if isinstance(change, dict) else change
                    if val:
                        self.current_state.physical_state = str(val)
                elif field == "location_id":
                    val = change.get("new", change) if isinstance(change, dict) else change
                    if val:
                        self.current_state.location_id = str(val)


@dataclass
class Location:
    """Location entity with full attributes."""
    id: str
    type: str = "location"
    created_at: str = ""
    updated_at: str = ""
    name: str = ""
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    atmosphere: str = ""
    sensory_details: SensoryDetails = field(default_factory=SensoryDetails)
    features: List[str] = field(default_factory=list)
    connections: List[LocationConnection] = field(default_factory=list)
    current_state: LocationState = field(default_factory=LocationState)
    significance: str = ""
    history: List[HistoryEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set timestamps if not provided."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if isinstance(self.sensory_details, SensoryDetails):
            data['sensory_details'] = self.sensory_details.to_dict()
        if isinstance(self.current_state, LocationState):
            data['current_state'] = self.current_state.to_dict()
        data['connections'] = [c.to_dict() if isinstance(c, LocationConnection) else c for c in self.connections]
        data['history'] = [h.to_dict() if isinstance(h, HistoryEntry) else h for h in self.history]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        """Create from dictionary."""
        if 'sensory_details' in data and isinstance(data['sensory_details'], dict):
            data['sensory_details'] = SensoryDetails.from_dict(data['sensory_details'])
        if 'current_state' in data and isinstance(data['current_state'], dict):
            data['current_state'] = LocationState.from_dict(data['current_state'])
        if 'connections' in data:
            data['connections'] = [
                LocationConnection.from_dict(c) if isinstance(c, dict) else c 
                for c in data['connections']
            ]
        if 'history' in data:
            data['history'] = [
                HistoryEntry.from_dict(h) if isinstance(h, dict) else h 
                for h in data['history']
            ]
        return cls(**data)

    def reset_dynamic_state(self):
        """清空由场景累积的动态状态。"""
        self.history = []
        self.current_state.tension_level = 0
        self.current_state.time_of_day = ""
        self.current_state.weather = ""
        self.current_state.occupants = []
        self.current_state.notable_objects = []

    def replay_history(self, entries):
        """按 tick 顺序重放 history 条目，重建 current_state。"""
        sorted_entries = sorted(entries, key=lambda e: e.tick)
        for entry in sorted_entries:
            for field, change in entry.changes.items():
                if field in ("occupants", "notable_objects"):
                    added = Character._parse_added(change)
                    current = getattr(self.current_state, field, [])
                    for item in added:
                        if item not in current:
                            current.append(item)
                    setattr(self.current_state, field, current)
                elif field in ("tension_level", "time_of_day", "weather", "atmosphere"):
                    val = change.get("new", change) if isinstance(change, dict) else change
                    if val is not None:
                        setattr(self.current_state, field, val)


@dataclass
class Scene:
    """Scene entity with metadata."""
    id: str
    type: str = "scene"
    created_at: str = ""
    tick: int = 0
    title: str = ""
    pov_character_id: str = ""
    location_id: str = ""
    markdown_file: str = ""
    word_count: int = 0
    summary: List[str] = field(default_factory=list)
    characters_present: List[str] = field(default_factory=list)
    key_events: List[str] = field(default_factory=list)
    emotional_beats: List[str] = field(default_factory=list)
    entities_created: List[str] = field(default_factory=list)
    entities_updated: List[str] = field(default_factory=list)
    open_loops_created: List[str] = field(default_factory=list)
    open_loops_resolved: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # NEW: Tension tracking (Phase 7A.3)
    tension_level: Optional[int] = None  # 0-10 scale
    tension_category: Optional[str] = None  # calm, rising, high, climactic
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class OpenLoop:
    """Open story loop (unresolved plot thread)."""
    id: str
    type: str = "open_loop"
    created_at: str = ""
    created_in_scene: str = ""
    status: str = "open"  # open, resolved, abandoned
    category: str = ""    # 由 LLM 根据语境自行归类
    description: str = ""
    importance: str = "medium"  # low, medium, high, critical
    related_characters: List[str] = field(default_factory=list)
    related_locations: List[str] = field(default_factory=list)
    notes: str = ""
    resolved_in_scene: Optional[str] = None
    resolution_summary: Optional[str] = None
    
    # NEW: Tracking fields (Phase 7A.2)
    scenes_mentioned: int = 0  # How many scenes has this appeared in?
    last_mentioned_tick: Optional[int] = None
    is_story_goal: bool = False  # Promoted to main story goal?
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenLoop":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class RelationshipGraph:
    """Relationship between two characters (bidirectional)."""
    id: str
    type: str = "relationship"
    created_at: str = ""
    updated_at: str = ""
    character_a: str = ""
    character_b: str = ""
    relationship_type: str = ""  # mentor-student, friends, rivals, enemies, family, romantic, etc.
    status: str = "neutral"  # close, strained, hostile, unknown, complicated, etc.
    perspective_a: str = ""  # How character_a views character_b
    perspective_b: str = ""  # How character_b views character_a
    intensity: int = 5  # 0-10 scale, how important this relationship is
    history: List[RelationshipHistoryEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set timestamps if not provided."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['history'] = [h.to_dict() if isinstance(h, RelationshipHistoryEntry) else h for h in self.history]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipGraph":
        """Create from dictionary."""
        if 'history' in data:
            data['history'] = [
                RelationshipHistoryEntry.from_dict(h) if isinstance(h, dict) else h 
                for h in data['history']
            ]
        return cls(**data)
    
    def involves_character(self, character_id: str) -> bool:
        """Check if this relationship involves the given character."""
        return character_id in (self.character_a, self.character_b)
    
    def get_other_character(self, character_id: str) -> Optional[str]:
        """Get the other character in the relationship."""
        if character_id == self.character_a:
            return self.character_b
        elif character_id == self.character_b:
            return self.character_a
        return None
    
    def get_perspective(self, character_id: str) -> Optional[str]:
        """Get the perspective from a specific character's viewpoint."""
        if character_id == self.character_a:
            return self.perspective_a
        elif character_id == self.character_b:
            return self.perspective_b
        return None


@dataclass
class Lore:
    """World rule or lore fact (Phase 7A.4).
    
    Tracks established world rules, constraints, and facts to maintain
    internal consistency across the emergent narrative.
    """
    id: str
    type: str = "lore"
    lore_type: str = ""    # 由 LLM 根据语境自行归类
    content: str = ""      # 世界观陈述内容（中文）
    category: str = ""     # 由 LLM 根据故事情境自行归类
    source_scene_id: str = ""  # Scene where this was established
    tick: int = 0
    importance: str = "normal"  # "critical", "important", "normal", "minor"
    tags: List[str] = field(default_factory=list)  # For categorization
    related_lore: List[str] = field(default_factory=list)  # IDs of related lore
    potential_contradictions: List[str] = field(default_factory=list)  # IDs of potentially conflicting lore
    created_at: str = ""
    
    def __post_init__(self):
        """Set created_at if not provided."""
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lore":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PlotBeat:
    """A single plot beat (factual event) for the plot outline layer."""
    id: str
    description: str
    characters_involved: List[str] = field(default_factory=list)
    location: Optional[str] = None
    plot_threads: List[str] = field(default_factory=list)
    tension_target: Optional[int] = None  # 0-10 target tension level
    prerequisites: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, skipped
    created_at: str = ""
    consumed_at_tick: Optional[int] = None  # tick when beat was consumed
    executed_in_scene: Optional[str] = None
    execution_notes: str = ""

    # Verification metadata
    verification_score: Optional[float] = None  # 0.0-1.0 confidence score
    verification_method: Optional[str] = None   # trusted_planner, semantic, llm, manual

    # Metadata for validation / analysis
    advances_character_arcs: List[str] = field(default_factory=list)
    resolves_loops: List[str] = field(default_factory=list)
    creates_loops: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotBeat":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PlotOutline:
    """Collection of plot beats and high-level arc metadata."""
    beats: List[PlotBeat] = field(default_factory=list)
    created_at: str = ""
    last_updated: str = ""
    current_arc: str = ""
    arc_progress: float = 0.0

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.last_updated:
            self.last_updated = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "beats": [b.to_dict() for b in self.beats],
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "current_arc": self.current_arc,
            "arc_progress": self.arc_progress,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotOutline":
        """Create from dictionary."""
        beats_data = data.get("beats", [])
        beats = [PlotBeat.from_dict(b) for b in beats_data]
        return cls(
            beats=beats,
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
            current_arc=data.get("current_arc", ""),
            arc_progress=data.get("arc_progress", 0.0),
        )

    def to_json(self, filepath: Path) -> None:
        """Serialize to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, filepath: Path) -> "PlotOutline":
        """Deserialize from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @staticmethod
    def now_iso() -> str:
        """Get current timestamp in ISO format."""
        return datetime.utcnow().isoformat() + "Z"


@dataclass
class StoryThread:
    """Named narrative thread spanning multiple scenes — 故事支线追踪。

    Tracks subplot arcs, relationship arcs, mystery threads, and character
    arcs as first-class entities. LLM suggestions flow through pending →
    user confirmation → active → resolved.
    """
    id: str                          # ST000, ST001...
    type: str = "story_thread"
    created_at: str = ""
    updated_at: str = ""

    name: str = ""                   # 支线名称
    description: str = ""            # 支线描述
    category: str = "subplot"        # main|subplot|relationship|mystery|character_arc
    status: str = "pending"          # pending|active|dormant|resolved|rejected
    importance: str = "medium"       # critical|high|medium|low
    source: str = "llm_suggested"    # llm_suggested|user_created

    introduced_tick: int = 0
    last_advanced_tick: int = 0
    advancement_history: list = field(default_factory=list)  # [{tick, scene_id, note}]

    related_characters: list = field(default_factory=list)   # ["C000", "C003"]
    related_scenes: list = field(default_factory=list)       # ["S005", "S012"]
    related_loops: list = field(default_factory=list)        # ["OL01"]

    suggestion_evidence: str = ""      # LLM suggestion only
    suggestion_confidence: str = ""    # high|medium|low (LLM suggestion only)
    resolution_note: str = ""

    def __post_init__(self):
        now = datetime.utcnow().isoformat() + "Z"
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoryThread":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
