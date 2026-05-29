"""点阵标志生成端点。给 LLM 几何图元脚手架，让它根据故事自由创作。"""
import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project, get_engine
from ...cli.project import load_project_state

router = APIRouter(prefix="/api/v1", tags=["画像"])
logger = logging.getLogger(__name__)

_PROMPT = """\
你是矢量徽章设计专家。为下面这部小说设计一枚点阵风格的专属徽章/Logo。

== 小说信息 ==
名称：{name} | 类型：{genre}
简介：{premise}
主角：{protagonist}
基调：{tone} | 进度：第{tick}幕

== 画布 ==
440×330 像素，中心 (220,165)。图案主体控制在 半径80-120px 范围内。

== 图元工具箱 ==
ring(cx,cy,r,width,density)          — 空心圆环
arc(cx,cy,r,a1,a2_度,width,density) — 弧线（0°=右,90°=下）
line(x1,y1,x2,y2,width,density)     — 线段
poly(points[[x,y]...],density)       — 填充多边形
ellipse(cx,cy,rx,ry,density)         — 填充椭圆（仅小节点,rx/ry≤18）

== 强制设计规则 ==
1. 外框必须是 ring 或 poly（六边形/菱形/八边形等），不能是填充ellipse
2. 内部必须有线条结构：放射线/分割线/内嵌几何形，不能全是圆弧
3. ellipse 只用于中心点（rx≤12）或小装饰节点
4. 整体像一枚有辨识度的徽章，不是模糊的圆形色块
5. 共20-30个图元，层次丰富

== 好设计示例（科幻星图徽章） ==
外六边形: poly([[220,55],[307,110],[307,220],[220,275],[133,220],[133,110]],d=2.5)
内圆环:   ring(220,165,r=70,w=4,d=2.0)
内圆环2:  ring(220,165,r=45,w=2,d=1.8)
放射线×6: line(220,165→六个方向到六边形边,w=2,d=1.5)
中心点:   ellipse(220,165,rx=10,ry=10,d=3.0)
弧装饰:   arc(220,165,r=70,a1=0,a2=60,w=6,d=2.0) ×6段

== 糟糕示例（禁止） ==
大填充椭圆: ellipse(220,165,rx=100,ry=60) ← 禁止！这只是一坨圆
多个同心圆环没有内部结构 ← 禁止！看起来像靶心不像徽章

== 颜色 ==
cyan科幻, purple奇幻, amber武侠/修仙, red悬疑, pink言情, gold历史

请根据《{name}》的世界观，创作一个独特的、有辨识度的徽章图案。
只输出JSON，无解释无代码块：
{{
  "color":"cyan",
  "caption":"标题12字内",
  "shapes":[
    {{"type":"poly","points":[[220,55],[307,110],[307,220],[220,275],[133,220],[133,110]],"density":2.5}},
    ...更多图元...
  ]
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
