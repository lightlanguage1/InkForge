"""故事生成（流式 + 批量）路由。"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import resolve_project, create_agent
from ...agent.streaming_agent import StreamingStoryAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["生成"])

# 并发锁——每个项目同时只能有一个 tick 在运行
_locks: dict[str, asyncio.Lock] = {}
_running: set[str] = set()


def _try_lock(project_id: str) -> bool:
    """尝试获取项目锁。已被占用返回 False。"""
    if project_id in _running:
        return False
    _running.add(project_id)
    return True


def _release(project_id: str):
    _running.discard(project_id)


@router.get("/project/{project_id}/tick/stream")
async def tick_stream(project_id: str, notes: str = "", llm_backend: str = "", llm_model: str = ""):
    if not _try_lock(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        agent = create_agent(project_dir, llm_backend=llm_backend or None, llm_model=llm_model or None)
        notes = notes.strip()
        if notes:
            logger.info("场景指导已接收: %s", notes)
        streaming_agent = StreamingStoryAgent(agent, notes=notes)

        async def generate():
            try:
                for chunk in streaming_agent.tick_stream():
                    yield chunk
            except asyncio.CancelledError:
                logger.info("SSE client disconnected, releasing lock for %s", project_id)
            finally:
                _release(project_id)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception:
        _release(project_id)
        raise


@router.post("/project/{project_id}/run")
def run_multiple(project_id: str, n: int = 5):
    if not _try_lock(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        results = []
        for i in range(n):
            try:
                agent = create_agent(project_dir)
                result = agent.tick()
                results.append({
                    "tick": result.get("tick"),
                    "scene_id": result.get("scene_id"),
                    "word_count": result.get("word_count"),
                })
            except Exception:
                logger.exception("批量 tick 第 %d/%d 幕失败", i + 1, n)
                break
        return {"results": results, "completed": len(results)}
    finally:
        _release(project_id)
