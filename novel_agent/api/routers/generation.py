"""故事生成（流式 + 批量）路由。"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import resolve_project, create_agent
from ...agent.streaming_agent import StreamingStoryAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["生成"])


@router.get("/project/{project_id}/tick/stream")
async def tick_stream(project_id: str):
    project_dir = resolve_project(project_id)
    agent = create_agent(project_dir)
    streaming_agent = StreamingStoryAgent(agent)
    return StreamingResponse(
        streaming_agent.tick_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/project/{project_id}/run")
def run_multiple(project_id: str, n: int = 5):
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
