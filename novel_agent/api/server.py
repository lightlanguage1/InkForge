"""FastAPI server for StoryDaemon."""

import time
import logging
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from ..engine.core import EngineCore
from ..configs.config import Config
from ..cli.project import find_project_dir, load_project_state
from ..memory.manager import MemoryManager
from ..agent.streaming_agent import StreamingStoryAgent
from ..skill.importer import SkillImporter
from ..skill.injector import SkillInjector
from ..reference.indexer import ReferenceIndexer

logger = logging.getLogger(__name__)

app = FastAPI(title="StoryDaemon API", version="0.2.0")


# ========== Request/Response Models ==========

class TickRequest(BaseModel):
    project_path: str
    save_prompts: bool = False
    llm_backend: Optional[str] = None
    llm_model: Optional[str] = None


class TickResponse(BaseModel):
    success: bool
    tick: int
    scene_id: str
    scene_file: str
    word_count: int
    actions_executed: int
    tension: Optional[dict] = None


class ProjectCreateRequest(BaseModel):
    name: str
    directory: Optional[str] = None
    genre: Optional[str] = None
    premise: Optional[str] = None
    protagonist: Optional[str] = None
    setting: Optional[str] = None
    tone: Optional[str] = None
    themes: Optional[str] = None
    use_plot_first: bool = False


class ProjectStatusResponse(BaseModel):
    project_id: str
    current_tick: int
    novel_name: str
    scene_count: int
    character_count: int
    location_count: int
    word_count: int
    avg_tension: float


class SkillImportRequest(BaseModel):
    file_path: str
    name: Optional[str] = None
    source_lang: str = "zh"


class SkillApplyRequest(BaseModel):
    project_path: str
    skill_ids: List[str]
    mode: str = "reference"


# ========== Engine Singleton ==========

_engine = None


def get_engine():
    """Get or create the engine singleton."""
    global _engine
    if _engine is None:
        cfg = Config()
        _engine = EngineCore(cfg.to_dict())
    return _engine


# ========== Routes ==========

@app.get("/health")
def health_check():
    """Service health check."""
    return {"status": "ok", "service": "storydaemon"}


@app.post("/api/v1/project", response_model=dict)
def create_project(req: ProjectCreateRequest):
    """Create a new project."""
    engine = get_engine()
    dir_path = engine.create_project(
        name=req.name,
        directory=req.directory,
        genre=req.genre,
        premise=req.premise,
        protagonist=req.protagonist,
        setting=req.setting,
        tone=req.tone,
        themes=req.themes,
        use_plot_first=req.use_plot_first,
    )
    return {"project_path": dir_path}


@app.get("/api/v1/projects")
def list_projects():
    """List all active projects."""
    engine = get_engine()
    return {"projects": engine.project_manager.get_active_projects()}


@app.post("/api/v1/project/{project_id}/tick", response_model=TickResponse)
def run_tick(project_id: str):
    """Execute one story generation tick."""
    engine = get_engine()
    project = engine.project_manager.get_or_create_project(project_id)
    try:
        project.status = "running"
        result = project.agent.tick()
        project.last_tick_at = time.time()
        project.tick_count += 1
        project.status = "idle"
        return TickResponse(
            success=True,
            tick=result.get("tick", 0),
            scene_id=result.get("scene_id", ""),
            scene_file=result.get("scene_file", ""),
            word_count=result.get("word_count", 0),
            actions_executed=result.get("actions_executed", 0),
            tension=result.get("tension"),
        )
    except Exception as e:
        project.status = "error"
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/project/{project_id}/tick/stream")
async def run_tick_stream(project_id: str):
    """Execute one tick with SSE streaming."""
    engine = get_engine()
    project = engine.project_manager.get_or_create_project(project_id)
    streaming_agent = StreamingStoryAgent(project.agent)
    return StreamingResponse(
        streaming_agent.tick_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/v1/project/{project_id}/run")
def run_multiple_ticks(project_id: str, n: int = 5):
    """Execute N ticks in sequence."""
    engine = get_engine()
    results = []
    for i in range(n):
        project = engine.project_manager.get_or_create_project(project_id)
        project.status = "running"
        result = project.agent.tick()
        project.last_tick_at = time.time()
        project.tick_count += 1
        project.status = "idle"
        results.append({
            "tick": result.get("tick"),
            "scene_id": result.get("scene_id"),
            "word_count": result.get("word_count"),
        })
    return {"results": results, "completed": len(results)}


@app.get("/api/v1/project/{project_id}/status", response_model=ProjectStatusResponse)
def get_project_status(project_id: str):
    """Get project status."""
    try:
        engine = get_engine()
        if project_id in engine.project_manager.projects:
            proj = engine.project_manager.projects[project_id]
            path = proj.project_path
        else:
            path = Path(find_project_dir(project_id))

        state = load_project_state(path)
        memory = MemoryManager(path)

        scenes = memory.list_scenes()
        chars = memory.list_characters()
        locs = memory.list_locations()

        total_words = 0
        tensions = []
        for sid in scenes:
            s = memory.load_scene(sid)
            if s:
                total_words += s.word_count or 0
                if s.tension_level is not None:
                    tensions.append(s.tension_level)

        avg_tension = sum(tensions) / len(tensions) if tensions else 0

        return ProjectStatusResponse(
            project_id=project_id,
            current_tick=state.get('current_tick', 0),
            novel_name=state.get('novel_name', 'Untitled'),
            scene_count=len(scenes),
            character_count=len(chars),
            location_count=len(locs),
            word_count=total_words,
            avg_tension=avg_tension,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Skill Routes ==========


@app.post("/api/v1/skill/import")
def skill_import(req: SkillImportRequest):
    """Import a novel file as a writing skill."""
    engine = get_engine()
    store = engine.skill_store

    backend = engine.config.get("llm.backend", "codex")
    importer = SkillImporter(engine.llm_pool.get_connection(backend=backend), store)
    skill = importer.import_novel(file_path=req.file_path, name=req.name)
    return {
        "skill_id": skill.id,
        "slug": skill.slug,
        "name": skill.name,
        "style_tags": skill.tags,
        "patterns": len(skill.patterns),
        "archetypes": len(skill.character_archetypes),
    }


@app.get("/api/v1/skills")
def skill_list():
    """List all available skills."""
    engine = get_engine()
    store = engine.skill_store
    skills = store.list_skills()
    return {
        "skills": [
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "tags": s.tags,
                "genre": s.genre,
                "source_novel": s.source_novel,
                "word_count": s.word_count,
            }
            for s in skills
        ]
    }


@app.post("/api/v1/skill/apply")
def skill_apply(req: SkillApplyRequest):
    """Apply skills to a project."""
    engine = get_engine()
    store = engine.skill_store

    skills = []
    for sid in req.skill_ids:
        s = store.load_skill(sid)
        if s:
            skills.append(s)

    if not skills:
        raise HTTPException(status_code=404, detail="No matching skills found")

    injector = SkillInjector(project_path=req.project_path, config=engine.config)
    injector.inject(skills, mode=req.mode)
    return {"applied": len(skills), "skills": [s.name for s in skills]}


# ========== Reference Routes ==========


class ReferenceImportRequest(BaseModel):
    file_path: str
    title: Optional[str] = None


class ReferenceSearchRequest(BaseModel):
    query: str
    top_k: int = 3
    source_filter: Optional[str] = None


@app.post("/api/v1/reference/import")
def reference_import(req: ReferenceImportRequest):
    """Import a novel file as a reference for retrieval."""
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    novel = indexer.index_novel(file_path=req.file_path, title=req.title)
    return {
        "novel_id": novel.id,
        "title": novel.title,
        "chunk_count": novel.chunk_count,
    }


@app.post("/api/v1/reference/search")
def reference_search(req: ReferenceSearchRequest):
    """Search reference library."""
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    results = indexer.search(
        query=req.query,
        top_k=req.top_k,
        source_filter=req.source_filter,
    )
    return {"results": results}
