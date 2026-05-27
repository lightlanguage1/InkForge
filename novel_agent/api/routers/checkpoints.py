"""存档管理路由。"""

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project
from ..models import CheckpointCreateRequest
from ...cli.project import load_project_state
from ...memory.checkpoint import (
    create_checkpoint, list_checkpoints, restore_checkpoint, delete_checkpoint,
)

router = APIRouter(prefix="/api/v1", tags=["存档"])


@router.post("/project/{project_id}/checkpoints")
def checkpoint_create(project_id: str, req: CheckpointCreateRequest = CheckpointCreateRequest()):
    project_dir = resolve_project(project_id)
    state = load_project_state(project_dir)
    try:
        path = create_checkpoint(project_dir, state.get("current_tick", 0),
                                 created_by=req.message or "api")
        return {"checkpoint_id": path.name, "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/project/{project_id}/checkpoints")
def checkpoint_list(project_id: str):
    checkpoints = list_checkpoints(resolve_project(project_id))
    return {
        "checkpoints": [
            {
                "checkpoint_id": c.checkpoint_id,
                "tick": c.tick, "timestamp": c.timestamp,
                "scenes_count": c.scenes_count,
                "characters_count": c.characters_count,
                "locations_count": c.locations_count,
                "size_bytes": c.size_bytes, "created_by": c.created_by,
            }
            for c in checkpoints
        ]
    }


@router.post("/project/{project_id}/checkpoints/{checkpoint_id}/restore")
def checkpoint_restore(project_id: str, checkpoint_id: str):
    try:
        restore_checkpoint(resolve_project(project_id), checkpoint_id)
        return {"restored": checkpoint_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/project/{project_id}/checkpoints/{checkpoint_id}")
def checkpoint_delete(project_id: str, checkpoint_id: str):
    try:
        delete_checkpoint(resolve_project(project_id), checkpoint_id)
        return {"deleted": checkpoint_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
