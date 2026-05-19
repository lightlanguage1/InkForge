"""Skill store — persistent skill library with YAML storage.

Directory structure:
    data/skills/
    ├── index.yaml           # LLM-friendly catalog for skill discovery
    └── <slug>/              # English slug (e.g. "sword-and-fairy-3")
        └── SKILL.yaml       # canonical skill data (Chinese content OK)
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional

import yaml

from ..configs.constants import SKILL_FILE

from .models import Skill

logger = logging.getLogger(__name__)


class SkillStore:
    """YAML-backed skill library.

    Each skill lives in a directory named by its English slug so that
    both the filesystem and LLMs can reason about it without encoding
    issues.  The index.yaml at the root is optimised for LLM discovery.
    """

    def __init__(self, config: dict):
        skill_cfg = config.get("skill", {}) or {}
        store_path = skill_cfg.get("store_path", "data/skills")
        self.store_path = Path(store_path).expanduser().resolve()
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_path / "index.yaml"
        self._load_index()

    # ---- index -----------------------------------------------------------

    def _load_index(self) -> None:
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as fh:
                self.index = yaml.safe_load(fh) or {}
        else:
            self.index: dict = {}
            self._save_index()

    def _save_index(self) -> None:
        with open(self.index_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.index, fh, allow_unicode=True, sort_keys=False)

    def _upsert_index(self, skill: Skill) -> None:
        self.index[skill.slug] = {
            "name": skill.name,
            "name_en": skill.source_novel if skill.source_novel != skill.name else "",
            "tags": skill.tags,
            "genre": skill.genre,
            "word_count": skill.word_count,
            "chapter_count": skill.chapter_count,
            "imported_at": skill.imported_at,
            "description": _make_description(skill),
        }
        self._save_index()

    def _remove_from_index(self, slug: str) -> None:
        self.index.pop(slug, None)
        self._save_index()

    # ---- CRUD -----------------------------------------------------------

    def list_slugs(self) -> List[str]:
        return list(self.index.keys())

    def list_skills(self) -> List[Skill]:
        skills: List[Skill] = []
        for slug in self.index:
            skill = self.load_skill(slug)
            if skill is not None:
                skills.append(skill)
        return skills

    def load_skill(self, key: str) -> Optional[Skill]:
        """Load by slug first, then fall back to id search."""
        skill = self._load_by_slug(key)
        if skill is not None:
            return skill
        return self._load_by_id(key)

    def save_skill(self, skill: Skill) -> None:
        skill_dir = self.store_path / skill.slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        yaml_file = skill_dir / SKILL_FILE
        with open(yaml_file, "w", encoding="utf-8") as fh:
            yaml.safe_dump(skill.to_dict(), fh, allow_unicode=True, sort_keys=False)
        self._upsert_index(skill)
        logger.info("Saved skill %s → %s", skill.slug, yaml_file)

    def delete_skill(self, key: str) -> None:
        slug = self._resolve_slug(key)
        if slug is None:
            return
        skill_dir = self.store_path / slug
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        self._remove_from_index(slug)
        logger.info("Deleted skill %s", slug)

    # ---- internal helpers ------------------------------------------------

    def _load_by_slug(self, slug: str) -> Optional[Skill]:
        yaml_file = self.store_path / slug / SKILL_FILE
        if not yaml_file.exists():
            return None
        with open(yaml_file, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return Skill.from_dict(data) if data else None

    def _load_by_id(self, skill_id: str) -> Optional[Skill]:
        for slug in self.index:
            skill = self._load_by_slug(slug)
            if skill is not None and skill.id == skill_id:
                return skill
        return None

    def _resolve_slug(self, key: str) -> Optional[str]:
        """Return slug if key is a known slug; otherwise search by id."""
        if key in self.index:
            return key
        for slug in self.index:
            skill = self._load_by_slug(slug)
            if skill is not None and skill.id == key:
                return slug
        return None


def _make_description(skill: Skill) -> str:
    """One-line English description for the index (LLM-friendly)."""
    pattern_types = sorted({p.type for p in skill.patterns})
    if not pattern_types:
        return f"Writing style: {skill.name}"
    return (
        f"Narrative patterns ({', '.join(pattern_types[:4])}); "
        f"style tags: {', '.join(skill.tags[:5])}"
    )
