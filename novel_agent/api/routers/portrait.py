"""点阵标志生成端点。给 LLM 几何图元脚手架，让它根据故事自由创作。"""
import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project, get_engine
from ...cli.project import load_project_state

router = APIRouter(prefix="/api/v1", tags=["画像"])
logger = logging.getLogger(__name__)

_PROMPT = """\
你是点阵徽章设计大师。你的每一件作品都由离散的小圆点构成——没有实线，没有实心面，只有精确排列的圆点。点与点之间保持肉眼可见的间隙，这是点阵美学的核心。

══════════════════════════════════════════
图元工具箱（10 种，灵活组合、大胆创新）
══════════════════════════════════════════

┌──────────────────────────────────────────────────────────────┐
│ 1. ring(cx, cy, r, width, density)                          │
│    圆环。半径 r 圆周上均匀散布 density 个直径为 width 的圆点 │
│    density≤40  width≤5  保持虚线感，不要密到连成实线          │
│    例: ring(220,165,90,3,36) → 半径90的虚线空心圆            │
├──────────────────────────────────────────────────────────────┤
│ 2. arc(cx, cy, r, a1, a2, width, density)                   │
│    圆弧片段。角度a1到a2（0°=右→, 90°=下↓, 180°=左←）       │
│    density≤30  width≤5                                       │
│    例: arc(220,165,70,0,180,3,22) → 上半圆弧                  │
├──────────────────────────────────────────────────────────────┤
│ 3. line(x1, y1, x2, y2, width, density)                     │
│    线段。两点间均匀放置 density 个圆点，直径 width            │
│    density≤25  width≤4                                        │
│    例: line(220,80,220,250,3,18) → 垂直虚线                  │
│    高级用法: 放射线束、交叉阵列、锯齿折线、网格骨架           │
├──────────────────────────────────────────────────────────────┤
│ 4. poly(points, width, density)                              │
│    填充多边形。内部随机撒点，points是[[x,y],...]顶点数组       │
│    density≤35  width≤4  ★ 点必须稀疏，不能连成片              │
│    例: poly([[160,120],[280,120],[300,200],[140,200]],3,28)   │
│    高级用法: 盾形(六边形)、星形(10+顶点交替内外径)、           │
│            菱形、箭头形、钥匙孔形、旗帜形、新月形              │
├──────────────────────────────────────────────────────────────┤
│ 5. ellipse(cx, cy, rx, ry, width, density)                   │
│    填充椭圆。小尺寸装饰节点 rx,ry≤16                          │
│    density≤20  width≤3  ★ 仅用于点缀，主角要大                │
│    例: ellipse(220,165,8,12,2,14) → 竖椭圆装饰点              │
├──────────────────────────────────────────────────────────────┤
│ 6. dot_grid(cx, cy, w, h, spacing, dot_r)                   │
│    矩形点阵。在 w×h 矩形内以 spacing 间距均匀撒点             │
│    w,h≤80  spacing≥6  dot_r≤2.5                               │
│    高级用法: 棋盘格、砖墙纹理、电路板节点、数据矩阵            │
├──────────────────────────────────────────────────────────────┤
│ 7. scatter(cx, cy, rx, ry, count, dot_r)                     │
│    椭圆区域内随机散布 count 个独立圆点。点与点不连线           │
│    rx,ry≤60  count≤25  dot_r≤3                               │
│    高级用法: 星尘、火花、沙粒、碎光、血滴、魔法粒子            │
├──────────────────────────────────────────────────────────────┤
│ 8. spiral(cx, cy, r0, r1, turns, width, density)             │
│    螺旋线。从内径r0到外径r1，旋转turns圈（推荐1.5-3圈）       │
│    width≤4  density≤40                                        │
│    高级用法: 漩涡、禅绕、卷轴、龙卷、银河旋臂                  │
├──────────────────────────────────────────────────────────────┤
│ 9. zigzag(x1, y1, x2, y2, amplitude, segments, width, density)│
│    锯齿波。两点间以振幅 amplitude、段数 segments 折线放置点    │
│    amplitude≤40  segments≤12  width≤4  density≤30              │
│    高级用法: 闪电、心电图、山脉轮廓、荆棘、利齿、声波           │
├──────────────────────────────────────────────────────────────┤
│ 10. radial(cx, cy, r, rays, width, density)                  │
│     放射线。从中心向外均匀放射 rays 条线段到半径 r             │
│     r≤130  rays≤16  width≤3  density≤15                       │
│     高级用法: 太阳光、表盘刻度、花瓣骨架、爆炸冲击              │
└──────────────────────────────────────────────────────────────┘

══════════════════════════════════════════
少样本示例 —— 学习这些设计的层次感
══════════════════════════════════════════

【示例A — 修仙·剑修 "青云洗剑"】
小说：修仙世界，主角以剑证道，一柄青锋斩尽不平
设计思路：
- 核心意象为"剑"——剑身竖直贯穿画面，剑柄处有一轮满月
- 外框用六边形 poly 做盾形底盘，象征稳固根基
- 骨架用一条垂直线(剑脊) + 交叉的两条短横线(剑格)，形成"剑"字的抽象结构
- 剑柄处放一个小 ring 代表满月
- 六边形每个顶点外侧用 scatter 点缀星尘，呼应"青云"
- 底部用 zigzag 做山脉剪影，暗示主角出身

【示例B — 科幻·考古 "星海拾遗"】
小说：宇宙考古学家在废弃戴森球中发现上古文明信息水晶
设计思路：
- 核心意象为"水晶"与"星图"——中心水晶辐射出星轨
- 外框用两个偏移 poly 叠加（一大一小菱形），制造立体层次
- 内部用 6 条 radial 放射线，长短不一，每条末端放小 ellipse
- 中心放小椭圆(<10px)暗示水晶核心
- 用 3 条不同半径的 arc（0°到 120°/180°/270°）模拟不完整星轨
- 边缘 scatter 散布 20 个点模拟深空背景

【示例C — 奇幻·魔法 "魔女塔"】
小说：被遗弃孤女在魔法学院逆袭，塔是她命定的归宿
设计思路：
- 核心意象为"塔"与"星辰"——塔从底部升起，塔顶有星
- 外框用 poly 五边形做塔身轮廓，略微不对称
- 塔内部用 3 条水平短线标注楼层
- 塔顶用一个小 ring + radial(8条射线) 表现魔法光芒
- 底部 spiral 蜿蜒而上暗示魔力萦绕
- 左上角 scatter 散布 15 个小星点

══════════════════════════════════════════
当前小说信息
══════════════════════════════════════════
名称：{name}
类型：{genre}
前提：{premise}
主角：{protagonist}
基调：{tone}
进度：第{tick}幕

══════════════════════════════════════════
画布规格
══════════════════════════════════════════
440×330 像素，中心 (220,165)。主体控制在半径 60-130px 内。
图元总数 12-25 个，其中至少有 3 种不同类型。
densiy 参数控制点数：线条类(ring/arc/line/zigzag/spiral/radial) 为沿线放置的点数，
填充类(poly/ellipse/dot_grid/scatter) 为区域内的总点数。

══════════════════════════════════════════
颜色方案（hex，不可更改）
══════════════════════════════════════════
科幻→ #00E5FF (青) | 奇幻→ #B44CFF (紫) | 武侠/修仙→ #FFB74D (琥珀)
悬疑→ #FF5252 (红) | 言情→ #FF80AB (粉) | 历史→ #FFD54F (金)
选择一个最契合当前小说的，直接填 hex。

══════════════════════════════════════════
你的设计流程——必须显式输出
══════════════════════════════════════════

第一步：输出"设计思路"段落（3-6句话，用中文）
  - 从当前小说中提取1-2个核心意象（具体物品/符号/形态）
  - 说明为什么选它，以及准备用什么几何手法表现
  - 说明外框形状选择的原因
  - 说明颜色选择的理由

第二步：分层次列出图元清单
  - [外框] 1-2个图元 —— 定下整体轮廓
  - [骨架] 3-6个图元 —— 核心意象的几何结构
  - [细节] 5-12个图元 —— 装饰、氛围、点缀
  - [背景] 0-4个图元 —— 深空、星辰、纹理
  - 每个图元标注 {类型, 参数, 作用}

第三步：输出最终JSON

══════════════════════════════════════════
输出格式 —— 严格按照以下格式
══════════════════════════════════════════

【设计思路】
...3-6句话...

【图元清单】
[外框] ...
[骨架] ...
[细节] ...
[背景] ...

【JSON】
{{
  "color": "#HEXCODE",
  "caption": "8字以内标题",
  "shapes": [
    {{"type":"poly","points":[...],"width":3,"density":28}},
    {{"type":"line","x1":...,"y1":...,"x2":...,"y2":...,"width":3,"density":18}},
    ...
  ]
}}

⚠️ JSON 必须合法可解析。shapes 数组之外不要有任何额外文字。caption 8 字以内。
"""


def _extract_json(raw: str) -> str:
    """Extract JSON from model output — handles both bare JSON and sections."""
    import re
    raw = raw.strip()

    # Case 1: 【JSON】 section marker → extract everything after it
    json_marker = re.search(r'【JSON】\s*\n?(.+)', raw, re.DOTALL)
    if json_marker:
        section = json_marker.group(1).strip()
        # Remove surrounding ``` fences if present
        section = re.sub(r'^```\w*\s*\n?', '', section)
        section = re.sub(r'\n?```\s*$', '', section)
        return section.strip()

    # Case 2: Bare JSON with ``` fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    # Case 3: Try to find JSON object directly
    match = re.search(r'\{[^{}]*"color"[^{}]*"shapes"[^{}]*\[.*\][^{}]*\}', raw, re.DOTALL)
    if match:
        return match.group(0).strip()

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
        model  = engine.config.get("llm.model") or engine.config.get("llm.default_model") or "deepseek-chat"
        if model in ("gpt-5.1", "gpt-4", "gpt-4o"):
            model = "deepseek-chat"
        llm    = engine.llm_pool.get_connection(backend="api", model=model)
        raw    = llm.generate_with_retry(prompt, max_tokens=3000)
        portrait = json.loads(_extract_json(raw))
        cache_file.write_text(
            json.dumps({"cached_tick": tick, "portrait": portrait},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return portrait
    except Exception as exc:
        logger.exception("画像生成失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"画像生成失败: {exc}")
