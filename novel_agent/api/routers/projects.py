"""项目生命周期路由。"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from ...utils.log_manager import rmtree_force
from ...memory.manager import MemoryManager

from ..deps import get_engine, get_novels_dir, resolve_project, create_agent
from ..models import ProjectCreateRequest, TickRequest, TickResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["项目"])


def _has_cover(project_dir: Path) -> bool:
    """检查项目目录是否存在封面文件。"""
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if (project_dir / f"cover{ext}").exists():
            return True
    return False


def _find_cover(project_dir: Path) -> Path | None:
    """查找项目目录中的封面文件路径。"""
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        p = project_dir / f"cover{ext}"
        if p.exists():
            return p
    return None


def _list_filesystem_projects() -> list[dict]:
    """扫描用户 novels 目录，返回所有有效项目。"""
    novels = get_novels_dir()
    if not novels.exists():
        return []
    projects = []
    for entry in sorted(novels.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        state_file = entry / "state.json"
        if not state_file.exists():
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        projects.append({
            "project_path": str(entry.resolve()),
            "project_id": state.get("project_id", entry.name),
            "novel_name": state.get("novel_name", entry.name),
            "current_tick": state.get("current_tick", 0),
            "has_cover": _has_cover(entry),
        })
    return projects


# ---- 创建 / 列表 / 恢复 ----

@router.post("/project")
def create_project(req: ProjectCreateRequest):
    engine = get_engine()
    user_novels_dir = str(get_novels_dir())
    try:
        path = engine.create_project(
            name=req.name, directory=user_novels_dir,
            genre=req.genre, premise=req.premise,
            protagonist=req.protagonist, setting=req.setting,
            tone=req.tone, themes=req.themes,
            primary_goal=req.primary_goal,
            use_plot_first=req.use_plot_first,
        )
        # 写入 style_id / craft_id 到 state.json（安全访问，防止模型缺少字段）
        style_id = getattr(req, "style_id", None)
        craft_id = getattr(req, "craft_id", None)
        if style_id or craft_id:
            state_path = Path(path) / "state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if style_id:
                    state["style_id"] = style_id
                if craft_id:
                    state["craft_id"] = craft_id
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # 记录到用户项目表
        from ...user.context import get_current_user
        from ...user.db import Database as UserDB
        uid = get_current_user()
        if uid:
            pid = Path(path).name
            UserDB().upsert_project(uid, pid, req.name)
    except Exception:
        logger.exception("创建项目失败: %s", req.name)
        raise HTTPException(status_code=500, detail="创建项目失败")

    # 自动注入选中的写作技能
    if req.skill_ids:
        applied = []
        store = engine.skill_store
        skills = [s for sid in req.skill_ids if (s := store.load_skill(sid))]
        if skills:
            from ...skill.injector import SkillInjector
            injector = SkillInjector(project_path=path, config=engine.config)
            injector.inject(skills, mode="reference")
            applied = [s.name for s in skills]
        return {"project_path": path, "skills_applied": applied}

    return {"project_path": path}


@router.get("/projects")
def list_projects():
    return {"projects": _list_filesystem_projects()}


@router.post("/resume")
def resume():
    from ...cli.recent_projects import RecentProjects
    from ...cli.project import load_project_state

    # 优先 RecentProjects 追踪
    recent = RecentProjects()
    path = recent.get_most_recent()
    if path:
        state = load_project_state(Path(path))
        return {
            "project_path": path,
            "project_id": state.get("project_id", ""),
            "novel_name": state.get("novel_name", ""),
            "current_tick": state.get("current_tick", 0),
        }

    # fallback: 扫描目录取最新
    projects = _list_filesystem_projects()
    if projects:
        p = projects[0]
        return {
            "project_path": p["project_path"],
            "project_id": p["project_id"],
            "novel_name": p["novel_name"],
            "current_tick": p["current_tick"],
        }

    # 无项目时不报错，前端空状态
    return {
        "project_path": "",
        "project_id": "",
        "novel_name": "",
        "current_tick": 0,
    }


# ---- 重置 ----

@router.post("/project/{project_id}/reset")
def reset_project(project_id: str):
    """重置项目进度——清空场景和动态数据，保留设定和角色身份。"""
    from ..deps import try_lock_generation, release_generation
    if not try_lock_generation(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        project_dir = resolve_project(project_id)
        memory = MemoryManager(project_dir)

        # 1. 删除所有场景文件
        scenes_dir = project_dir / "scenes"
        if scenes_dir.exists():
            for f in scenes_dir.glob("*.md"):
                f.unlink()
        meta_dir = project_dir / "memory" / "scenes"
        if meta_dir.exists():
            for f in meta_dir.glob("*.json"):
                f.unlink()
        plans_dir = project_dir / "plans"
        if plans_dir.exists():
            for f in plans_dir.glob("*.json"):
                f.unlink()
        # QA files
        qa_dir = project_dir / "memory" / "qa"
        if qa_dir.exists():
            for f in qa_dir.glob("*.json"):
                f.unlink()

        # 2. 重置所有角色动态状态
        for char_id in memory.list_characters():
            char = memory.load_character(char_id)
            if char:
                char.reset_dynamic_state()
                memory.save_character(char)

        # 3. 清空 lore / loops / relationships
        memory._write_json(memory.lore_file, {"lore": []})
        memory.save_open_loops([])
        memory._write_json(memory.relationships_file, {"relationships": []})
        # 清空 story threads
        threads_dir = project_dir / "memory" / "story_threads"
        if threads_dir.exists():
            for f in threads_dir.glob("*.json"):
                f.unlink()

        # 4. 重置 current_tick
        state_file = project_dir / "state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["current_tick"] = 0
            state["last_updated"] = datetime.utcnow().isoformat() + "Z"
            state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # 5. 清理 plot beats
        plot_file = project_dir / "plot_outline.json"
        if plot_file.exists():
            plot_file.unlink()

        # 6. 清理 vector store 索引
        index_dir = project_dir / "memory" / "index"
        if index_dir.exists():
            shutil.rmtree(index_dir, ignore_errors=True)

        logger.info("项目已重置: %s", project_id)
        return {"reset": project_id, "message": "项目进度已重置，保留故事设定和角色身份"}
    finally:
        release_generation(project_id)


# ---- 删除 ----

@router.delete("/project/{project_id}")
def delete_project(project_id: str):
    try:
        project_dir = resolve_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"项目不存在: {project_id}")
    try:
        rmtree_force(project_dir)
    except OSError as exc:
        logger.exception("删除项目失败: %s", project_dir)
        raise HTTPException(status_code=500, detail=f"删除失败: {exc}")
    return {"deleted": str(project_dir)}


# ---- 封面 ----

def _find_project_across_users(project_id: str) -> Path | None:
    """跨用户目录查找项目 — 用于无需认证的公开访问（如封面图片）。"""
    users_dir = Path("work/users")
    if not users_dir.exists():
        return None
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        novels = user_dir / "novels"
        if not novels.exists():
            continue
        for entry in novels.iterdir():
            if entry.is_dir() and entry.name == project_id:
                if (entry / "state.json").exists():
                    return entry
    return None


@router.get("/project/{project_id}/cover")
def get_cover(project_id: str):
    """获取项目封面图片（公开访问，无需登录）。"""
    # 先尝试认证用户的目录，失败则跨用户搜索
    try:
        project_dir = resolve_project(project_id)
    except ValueError:
        project_dir = _find_project_across_users(project_id)
    if not project_dir:
        raise HTTPException(status_code=404, detail="项目不存在")
    cover_path = _find_cover(project_dir)
    if not cover_path:
        raise HTTPException(status_code=404, detail="无封面")
    from fastapi.responses import FileResponse
    ext = cover_path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    return FileResponse(cover_path, media_type=media_map.get(ext, "image/jpeg"))


@router.post("/project/{project_id}/cover")
async def upload_cover(project_id: str, file: UploadFile):
    """上传项目封面。支持 jpg/png/webp/gif。"""
    try:
        project_dir = resolve_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 校验类型
    ext = Path(file.filename or "cover.jpg").suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp/gif 格式")

    # 限制大小 (5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 5MB")

    # 删除旧封面
    old = _find_cover(project_dir)
    if old:
        old.unlink()

    # 保存
    cover_path = project_dir / f"cover{ext}"
    cover_path.write_bytes(content)
    return {"ok": True, "has_cover": True}


@router.delete("/project/{project_id}/cover")
def remove_cover(project_id: str):
    """删除项目封面。"""
    try:
        project_dir = resolve_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="项目不存在")
    cover_path = _find_cover(project_dir)
    if cover_path:
        cover_path.unlink()
    return {"ok": True, "has_cover": False}


# ---- Tick ----

@router.post("/project/{project_id}/tick", response_model=TickResponse)
def run_tick(project_id: str, req: TickRequest = None):
    from ..deps import try_lock_generation, release_generation
    if not try_lock_generation(project_id):
        raise HTTPException(status_code=409, detail="该项目正在生成中，请等待完成")
    try:
        if req is None:
            req = TickRequest()
        project_dir = resolve_project(project_id)
        agent = create_agent(
            project_dir,
            llm_backend=req.llm_backend,
            llm_model=req.llm_model,
            save_prompts=req.save_prompts,
        )
        result = agent.tick(notes=req.notes or "")
    except HTTPException:
        release_generation(project_id)
        raise
    except Exception:
        release_generation(project_id)
        logger.exception("Tick 失败: project=%s", project_id)
        raise HTTPException(status_code=500, detail="故事生成失败，请查看服务端日志")
    release_generation(project_id)
    return TickResponse(
        success=True,
        tick=result.get("tick", 0),
        scene_id=result.get("scene_id", ""),
        scene_file=result.get("scene_file", ""),
        word_count=result.get("word_count", 0),
        actions_executed=result.get("actions_executed", 0),
        tension=result.get("tension"),
    )
