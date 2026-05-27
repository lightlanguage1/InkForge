"""StoryDaemon REST API 入口 — 组装路由，不写业务逻辑。"""

from fastapi import FastAPI

from .routers import (
    health, projects, generation, entities, status,
    compile, plot, checkpoints, skills, references,
)

app = FastAPI(title="StoryDaemon API", version="1.0.0")

# 每个 router 负责一个业务域，内部不要交叉引用
app.include_router(health.router)        # GET /health
app.include_router(projects.router)      # POST /api/v1/project, /projects, /resume, /tick
app.include_router(generation.router)    # /tick/stream, /run
app.include_router(status.router)        # /status, /goals, /lore
app.include_router(entities.router)      # /characters, /locations, /scenes, /loops, /factions
app.include_router(compile.router)       # /compile, /summarize, /titles
app.include_router(plot.router)          # /plot, /plot/generate
app.include_router(checkpoints.router)   # /checkpoints
app.include_router(skills.router)        # /skills
app.include_router(references.router)    # /references
