"""情节节拍路由。"""

import logging
from fastapi import APIRouter, HTTPException

from ..deps import resolve_project
from ..models import BeatGenerateRequest
from ...cli.commands.plot import (
    get_plot_status, generate_and_append_beats_cli, clear_plot_outline,
)
from ...cli.project import get_project_config
from ...tools.llm_interface import initialize_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["节拍"])


@router.get("/project/{project_id}/plot")
def plot_status(project_id: str):
    return get_plot_status(resolve_project(project_id))


@router.post("/project/{project_id}/plot/generate")
def plot_generate(project_id: str, req: BeatGenerateRequest = BeatGenerateRequest()):
    project_dir = resolve_project(project_id)
    config = get_project_config(project_dir)
    backend = config.get("llm.backend", "api")
    model = config.get("llm.model") or config.get("llm.openai_model") or "deepseek-chat"
    codex_bin = config.get("llm.codex_bin_path")
    initialize_llm(backend=backend, model=model, codex_bin=codex_bin)

    result = generate_and_append_beats_cli(project_dir, count=req.count)
    return {
        "generated": len(result.get("beats", [])),
        "beats": [
            {
                "id": b.id, "description": b.description,
                "characters_involved": b.characters_involved,
                "location": b.location, "tension_target": b.tension_target,
                "status": b.status,
            }
            for b in result.get("beats", [])
        ],
    }


@router.delete("/project/{project_id}/plot")
def plot_clear(project_id: str):
    ok = clear_plot_outline(resolve_project(project_id), confirm=False)
    return {"cleared": ok}
