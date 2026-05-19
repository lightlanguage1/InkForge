"""Skill system data models."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class NarrativePattern:
    """Narrative pattern extracted from a novel.

    template: Actionable formula like "[环境] → [动作] → [对话]"
    description: What this pattern does (Chinese)
    example: Actual text from source novel showing the pattern
    frequency: How often this pattern appears (0.0-1.0)
    """
    type: str
    template: str = ""
    description: str = ""
    example: str = ""
    frequency: float = 0.0


@dataclass
class StyleProfile:
    """Writing style metrics — all computed from full text, no LLM.

    Qualitative aspects (tense, perspective, POV quality, etc.) are
    captured by the LLM-extracted style_tags, not by fake defaults.
    """
    avg_sentence_length: float = 0.0
    sentence_length_std: float = 0.0
    vocab_richness: float = 0.0       # unique bigrams / total bigrams
    dialogue_ratio: float = 0.0       # characters inside quotes / total chars
    paragraph_length_avg: float = 0.0 # avg chars per paragraph
    style_tags: List[str] = field(default_factory=list)


@dataclass
class CharacterArchetype:
    """Character archetype extracted from a novel."""
    name: str
    role: str  # protagonist | antagonist | supporting | mentor | love_interest | minor
    traits: List[str] = field(default_factory=list)
    arc_type: str = ""
    relationship_patterns: List[str] = field(default_factory=list)
    name_type: str = ""      # proper | alias | descriptor — LLM self-labelled
    name_confidence: str = ""  # high | medium | low — LLM self-assessed reliability
    is_entity: bool = True    # False if LLM suspects it's an item/concept, not a character
    aliases: List[str] = field(default_factory=list)  # names merged into this character


@dataclass
class Skill:
    """A writing skill extracted from a novel.

    Contains style features, narrative patterns, and character archetypes
    that can be reused as guidance in new writing projects.

    slug: filesystem-safe English identifier (e.g. "sword-and-fairy-3").
          Used as the skill directory name. Auto-generated if empty.
    """

    id: str
    name: str
    slug: str = ""
    source_novel: str = ""
    source_file: str = ""
    imported_at: str = ""
    tags: List[str] = field(default_factory=list)
    style_profile: Optional[StyleProfile] = None
    patterns: List[NarrativePattern] = field(default_factory=list)
    character_archetypes: List[CharacterArchetype] = field(default_factory=list)
    genre: str = ""
    themes: List[str] = field(default_factory=list)
    word_count: int = 0
    chapter_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.imported_at:
            self.imported_at = datetime.utcnow().isoformat() + "Z"
        if not self.slug or not all(c.isascii() for c in self.slug):
            self.slug = self.id

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = asdict(self)
        if self.style_profile:
            result['style_profile'] = asdict(self.style_profile)
        result['patterns'] = [asdict(p) for p in self.patterns]
        result['character_archetypes'] = [asdict(c) for c in self.character_archetypes]
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        """Deserialize from dictionary."""
        if 'style_profile' in data and data['style_profile']:
            data['style_profile'] = StyleProfile(**data['style_profile'])
        if 'patterns' in data:
            data['patterns'] = [NarrativePattern(**p) for p in data['patterns']]
        if 'character_archetypes' in data:
            data['character_archetypes'] = [CharacterArchetype(**c) for c in data['character_archetypes']]
        return cls(**data)
