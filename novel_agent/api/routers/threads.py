"""支线追踪 REST API。"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..deps import resolve_project, create_agent
from ...memory.manager import MemoryManager
from ...memory.thread_manager import ThreadManager
from ...memory.entities import StoryThread

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["支线"])


# ---- Request models ----

class CreateThreadRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "subplot"
    importance: str = "medium"
    related_characters: list[str] = []
    related_scenes: list[str] = []
    related_loops: list[str] = []
    introduced_tick: int = 0


class UpdateThreadRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    importance: Optional[str] = None
    related_characters: Optional[list[str]] = None
    related_scenes: Optional[list[str]] = None
    related_loops: Optional[list[str]] = None


# ---- Helpers ----

def _serialize_thread(t: StoryThread) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "status": t.status,
        "importance": t.importance,
        "source": t.source,
        "introduced_tick": t.introduced_tick,
        "last_advanced_tick": t.last_advanced_tick,
        "stall_count": max(0, t.introduced_tick and (t.introduced_tick - t.last_advanced_tick)),
        "advancement_history": t.advancement_history,
        "related_characters": t.related_characters,
        "related_scenes": t.related_scenes,
        "related_loops": t.related_loops,
        "suggestion_evidence": t.suggestion_evidence,
        "suggestion_confidence": t.suggestion_confidence,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _get_manager(project_id: str):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    return ThreadManager(memory)


def _get_manager_with_llm(project_id: str):
    project_dir = resolve_project(project_id)
    memory = MemoryManager(project_dir)
    try:
        agent = create_agent(project_dir)
        llm = agent.llm
    except Exception:
        llm = None
    return ThreadManager(memory, llm_interface=llm), project_dir


# ---- Endpoints ----

@router.get("/project/{project_id}/threads")
def list_threads(project_id: str, status: list[str] = Query(default=[])):
    mgr = _get_manager(project_id)
    all_threads = mgr.get_all()
    if status:
        all_threads = [t for t in all_threads if t.status in status]
    return {"threads": [_serialize_thread(t) for t in all_threads]}


@router.get("/project/{project_id}/threads/suggestions")
def list_suggestions(project_id: str):
    """列出所有 pending 状态的 LLM 建议。"""
    mgr = _get_manager(project_id)
    pending = mgr.get_pending()
    return {"suggestions": [_serialize_thread(t) for t in pending]}


@router.post("/project/{project_id}/threads/audit")
def run_audit(project_id: str):
    """触发 LLM 支线审计，返回新发现的建议。"""
    mgr, project_dir = _get_manager_with_llm(project_id)
    if not mgr.llm:
        raise HTTPException(status_code=503, detail="LLM 后端不可用，无法执行审计")
    import json
    state_file = project_dir / "state.json"
    novel_name = ""
    current_tick = 0
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            novel_name = state.get("novel_name", "")
            current_tick = state.get("current_tick", 0)
    suggestions = mgr.run_audit(current_tick, novel_name)
    return {"suggestions": [_serialize_thread(t) for t in suggestions]}


@router.get("/project/{project_id}/threads/{thread_id}")
def get_thread(project_id: str, thread_id: str):
    mgr = _get_manager(project_id)
    thread = mgr.memory.load_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail=f"未找到支线: {thread_id}")
    return _serialize_thread(thread)


@router.post("/project/{project_id}/threads")
def create_thread(project_id: str, req: CreateThreadRequest):
    mgr = _get_manager(project_id)
    thread = mgr.create_thread({
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "importance": req.importance,
        "status": "active",
        "source": "user_created",
        "introduced_tick": req.introduced_tick,
        "last_advanced_tick": req.introduced_tick,
        "related_characters": req.related_characters,
        "related_scenes": req.related_scenes,
        "related_loops": req.related_loops,
    })
    return _serialize_thread(thread)


@router.put("/project/{project_id}/threads/{thread_id}")
def update_thread(project_id: str, thread_id: str, req: UpdateThreadRequest):
    mgr = _get_manager(project_id)
    changes = {k: v for k, v in req.dict().items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="没有提供更新字段")
    thread = mgr.update_thread(thread_id, changes)
    if not thread:
        raise HTTPException(status_code=404, detail=f"未找到支线: {thread_id}")
    return _serialize_thread(thread)


@router.delete("/project/{project_id}/threads/{thread_id}")
def delete_thread(project_id: str, thread_id: str):
    mgr = _get_manager(project_id)
    if not mgr.memory.load_thread(thread_id):
        raise HTTPException(status_code=404, detail=f"未找到支线: {thread_id}")
    mgr.delete_thread(thread_id)
    return {"deleted": thread_id}
