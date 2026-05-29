"""前端日志接收端点。"""

import logging
from pydantic import BaseModel
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["日志"])

_LEVEL_MAP = {
    "debug":   logging.DEBUG,
    "info":    logging.INFO,
    "warn":    logging.WARNING,
    "warning": logging.WARNING,
    "error":   logging.ERROR,
}


class FrontendLogEntry(BaseModel):
    level: str = "error"
    source: str = "frontend"
    message: str
    stack: str | None = None
    context: dict | None = None


@router.post("/log")
def receive_frontend_log(entry: FrontendLogEntry):
    level = _LEVEL_MAP.get(entry.level.lower(), logging.ERROR)
    fe_logger = logging.getLogger("novel_agent.frontend")
    extra = f" | stack: {entry.stack}" if entry.stack else ""
    extra += f" | ctx: {entry.context}" if entry.context else ""
    fe_logger.log(level, "[%s] %s%s", entry.source, entry.message, extra)
    return {"ok": True}
