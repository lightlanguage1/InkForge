"""情节节拍路由。"""

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project
from ..models import BeatGenerateRequest
from ...cli.commands.plot import (
    get_plot_status, generate_and_append_beats_cli, clear_plot_outline,
)

router = APIRouter(prefix="/api/v1", tags=["节拍"])


@router.get("/project/{project_id}/plot")
def plot_status(project_id: str):
    return get_plot_status(resolve_project(project_id))


@router.post("/project/{project_id}/plot/generate")
def plot_generate(project_id: str, req: BeatGenerateRequest = BeatGenerateRequest()):
    result = generate_and_append_beats_cli(resolve_project(project_id), count=req.count)
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
