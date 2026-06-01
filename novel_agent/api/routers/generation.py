"""故事生成（流式 + 批量）路由。"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import resolve_project, create_agent
from ...agent.streaming_agent import StreamingStoryAgent
from ...user.context import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["生成"])

# 线程池——避免长时间生成阻塞事件循环
_executor = ThreadPoolExecutor(max_workers=20)

# 并发锁——user_id:project_id 粒度，不同用户互不阻塞
_running: set[str] = set()


def _scope_key(project_id: str) -> str:
    return f"{get_current_user()}:{project_id}"


def _try_lock(project_id: str) -> bool:
    key = _scope_key(project_id)
    if key in _running:
        return False
    _running.add(key)
    return True


def _release(project_id: str):
    _running.discard(_scope_key(project_id))


_FINALE_INSTRUCTION = (
    "【结尾完结模式】这是故事的最终阶段。你必须：\n"
    "1. 将所有主要开放线索收束或给出明确交代\n"
    "2. 完成主角的核心人物弧线\n"
    "3. 解决故事的中心冲突\n"
    "4. 给出令读者满意的结局——可以是开放式，但必须有情感上的落点\n"
    "5. 不要开启新的冲突或线索\n"
    "请以完结的笔法写作，语气可以深沉、回望、充满余韵。"
)


@router.get("/project/{project_id}/tick/stream")
async def tick_stream(
    project_id: str,
    notes: str = "",
    llm_backend: str = "",
    llm_model: str = "",
    finale: bool = False,
):
    if not _try_lock(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        agent = create_agent(project_dir, llm_backend=llm_backend or None, llm_model=llm_model or None)
        effective_notes = notes.strip()
        if finale:
            effective_notes = _FINALE_INSTRUCTION + ("\n\n附加指导：" + effective_notes if effective_notes else "")
            logger.info("结尾完结模式已启用")
        elif effective_notes:
            logger.info("场景指导已接收: %s", effective_notes)
        streaming_agent = StreamingStoryAgent(agent, notes=effective_notes)

        async def generate():
            import queue
            q: queue.Queue = queue.Queue()
            done = object()

            def _run():
                try:
                    for chunk in streaming_agent.tick_stream():
                        q.put(chunk)
                    q.put(done)
                except Exception as exc:
                    q.put(exc)

            loop = asyncio.get_event_loop()
            loop.run_in_executor(_executor, _run)
            try:
                while True:
                    item = await loop.run_in_executor(None, q.get)
                    if item is done:
                        break
                    if isinstance(item, Exception):
                        logger.exception("Tick generation failed")
                        yield f"event: tick_error\ndata: {{\"error\": \"{item}\"}}\n\n"
                        break
                    yield item
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
