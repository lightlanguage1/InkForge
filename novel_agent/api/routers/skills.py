"""技能管理路由。"""

from fastapi import APIRouter, HTTPException

from ..deps import get_engine
from ..models import SkillImportRequest, SkillApplyRequest
from ...skill.importer import SkillImporter
from ...skill.injector import SkillInjector
from ...skill.store import SkillStore
from ...configs.config import Config

router = APIRouter(prefix="/api/v1", tags=["技能"])


@router.post("/skills/import")
def skill_import(req: SkillImportRequest):
    engine = get_engine()
    store = engine.skill_store
    backend = engine.config.get("llm.backend", "codex")
    importer = SkillImporter(engine.llm_pool.get_connection(backend=backend), store)
    skill = importer.import_novel(file_path=req.file_path, name=req.name)
    return {
        "skill_id": skill.id, "slug": skill.slug, "name": skill.name,
        "style_tags": skill.tags,
        "patterns": len(skill.patterns),
        "archetypes": len(skill.character_archetypes),
    }


@router.get("/skills")
def skill_list():
    engine = get_engine()
    skills = engine.skill_store.list_skills()
    return {
        "skills": [
            {
                "id": s.id, "slug": s.slug, "name": s.name,
                "tags": s.tags, "genre": s.genre,
                "source_novel": s.source_novel, "word_count": s.word_count,
            }
            for s in skills
        ]
    }


@router.post("/skills/apply")
def skill_apply(req: SkillApplyRequest):
    engine = get_engine()
    store = engine.skill_store
    skills = [s for sid in req.skill_ids if (s := store.load_skill(sid))]
    if not skills:
        raise HTTPException(status_code=404, detail="未找到匹配的技能")
    injector = SkillInjector(project_path=req.project_path, config=engine.config)
    injector.inject(skills, mode=req.mode)
    return {"applied": len(skills), "skills": [s.name for s in skills]}


@router.delete("/skills/{slug}")
def skill_delete(slug: str):
    cfg = Config()
    store = SkillStore(cfg.get("skill.store_path", ""))
    skill = store.load_skill(slug)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"未找到技能: {slug}")
    store.delete_skill(slug)
    return {"deleted": slug, "name": skill.name}
