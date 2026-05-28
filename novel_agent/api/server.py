"""StoryDaemon REST API 入口。"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import (
    health, projects, generation, entities, status,
    compile, plot, checkpoints, skills, references,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="StoryDaemon API", version="1.0.0")

# CORS — 允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常兜底 — 保证所有未捕获异常都有 traceback 日志
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


app.include_router(health.router)
app.include_router(projects.router)
app.include_router(generation.router)
app.include_router(status.router)
app.include_router(entities.router)
app.include_router(compile.router)
app.include_router(plot.router)
app.include_router(checkpoints.router)
app.include_router(skills.router)
app.include_router(references.router)
