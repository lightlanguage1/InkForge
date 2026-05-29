"""点阵标志生成端点。给 LLM 几何图元脚手架，让它根据故事自由创作。"""
import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project, get_engine
from ...cli.project import load_project_state

router = APIRouter(prefix="/api/v1", tags=["画像"])
logger = logging.getLogger(__name__)

_PROMPT = """\
你是一位点阵视觉艺术家。用以下几何图元，为这部小说设计一个独特的点阵标志/图腾。

== 小说信息 ==
名称：{name}
类型：{genre}
简介：{premise}
主角：{protagonist}
基调：{tone}
进度：第 {tick} 幕

== 画布规格 ==
尺寸：400 × 300 像素
中心：(200, 150)
可用区域：建议图案填满中心区域约 260×220 像素

== 可用图元 ==

1. ellipse — 填充椭圆
   参数：cx, cy, rx, ry, density
   示例：{{"type":"ellipse","cx":200,"cy":150,"rx":60,"ry":40,"density":3.0}}

2. ring — 空心圆环
   参数：cx, cy, r, width, density
   示例：{{"type":"ring","cx":200,"cy":150,"r":80,"width":8,"density":2.0}}

3. line — 粗线段
   参数：x1, y1, x2, y2, width, density
   示例：{{"type":"line","x1":200,"y1":60,"x2":200,"y2":240,"width":6,"density":2.5}}

4. arc — 圆弧段（开口曲线）
   参数：cx, cy, r, a1, a2, width, density
   a1/a2 为角度（0=右，90=下，180=左，270=上）
   示例：{{"type":"arc","cx":200,"cy":150,"r":100,"a1":30,"a2":150,"width":6,"density":1.5}}

5. poly — 填充多边形（至少3个顶点）
   参数：points（[[x,y],...]列表）, density
   示例：{{"type":"poly","points":[[200,80],[260,200],[140,200]],"density":2.0}}

== density 说明 ==
0.3=极稀疏背景 / 1.0=标准 / 2.0=中等 / 3.0=密集 / 4.0=实心核心

== 颜色 ==
color 从以下选一个，代表故事气质：
cyan（科幻/星际）、purple（奇幻/魔法）、amber（武侠/修仙）、
red（悬疑/黑暗）、pink（言情/青春）、gold（历史/帝王）

== 你的任务 ==
根据小说的核心元素（道具/符号/场景/图腾/概念），用 10-22 个图元组合成一个
有辨识度、有美感的图案。图案应该：
- 能让人联想到这部小说的世界观或核心道具
- 有清晰的主体结构（核心元素 density 2.5-4.0）
- 有层次感（内核密集，外围和装饰稀疏）
- 几何构图精美，不要杂乱

仅输出 JSON，不要解释，不要代码块：
{{
  "color": "cyan",
  "caption": "画面标题（中文12字以内）",
  "shapes": [ ...图元列表... ]
}}
"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:])
    if raw.rstrip().endswith("```"):
        raw = "\n".join(raw.rstrip().splitlines()[:-1])
    return raw.strip()


@router.get("/project/{project_id}/portrait")
def get_portrait(project_id: str, force: bool = False):
    project_dir = resolve_project(project_id)
    cache_file  = project_dir / "portrait.json"
    state       = load_project_state(str(project_dir))
    tick        = state.get("current_tick", 0)

    if not force and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            portrait = cached.get("portrait", {})
            # Invalidate cache if format is outdated (missing shapes) or tick drifted
            if portrait.get("shapes") and abs(cached.get("cached_tick", -999) - tick) < 5:
                return portrait
        except Exception:
            pass

    foundation = state.get("story_foundation") or {}
    prompt = _PROMPT.format(
        name        = state.get("novel_name", "未知"),
        genre       = foundation.get("genre",                  "未知"),
        premise     = (foundation.get("premise",               "") or "")[:200],
        protagonist = (foundation.get("protagonist_archetype", "") or "")[:150],
        tone        = (foundation.get("tone",                  "") or "")[:100],
        tick        = tick,
    )

    try:
        engine = get_engine()
        # Read the configured model; fall back to deepseek-chat (the project's LLM).
        # Never default to gpt-5.1 — that requires an OpenAI key the user doesn't have.
        model  = engine.config.get("llm.model") or engine.config.get("llm.default_model") or "deepseek-chat"
        if model in ("gpt-5.1", "gpt-4", "gpt-4o"):   # safety: reject OpenAI models
            model = "deepseek-chat"
        llm    = engine.llm_pool.get_connection(backend="api", model=model)
        raw    = llm.generate_with_retry(prompt, max_tokens=1800)
        portrait = json.loads(_strip_fences(raw))
        cache_file.write_text(
            json.dumps({"cached_tick": tick, "portrait": portrait},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return portrait
    except Exception as exc:
        logger.exception("画像生成失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"画像生成失败: {exc}")
