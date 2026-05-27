"""编译输出路由 — compile / summarize / titles。"""

import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project
from ..models import CompileRequest, TitleRequest
from ...cli.commands.compile import compile_manuscript
from ...cli.commands.summarize import generate_summary
from ...cli.commands.titles import generate_titles

router = APIRouter(prefix="/api/v1", tags=["编译"])


@router.post("/project/{project_id}/compile")
def compile_novel(project_id: str, req: CompileRequest = CompileRequest()):
    project_dir = resolve_project(project_id)
    fd, tmp_path = tempfile.mkstemp(suffix=f".{req.format}")
    os.close(fd)
    try:
        ok = compile_manuscript(
            project_dir, Path(tmp_path),
            format=req.format,
            include_metadata=req.include_metadata,
            scene_range=req.scene_range,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="编译失败，没有场景可编译")
        content = Path(tmp_path).read_text(encoding="utf-8")
        return {"content": content, "format": req.format}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.get("/project/{project_id}/summarize")
def summarize(project_id: str):
    return {"content": generate_summary(resolve_project(project_id))}


@router.post("/project/{project_id}/titles")
def generate_title(project_id: str, req: TitleRequest = TitleRequest()):
    return {"titles": generate_titles(resolve_project(project_id), count=req.count)}
