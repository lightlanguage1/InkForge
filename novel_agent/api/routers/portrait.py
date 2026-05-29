"""点阵标志生成端点。给 LLM 几何图元脚手架，让它根据故事自由创作。"""
import json
import logging

from fastapi import APIRouter, HTTPException

from ..deps import resolve_project, get_engine
from ...cli.project import load_project_state

router = APIRouter(prefix="/api/v1", tags=["画像"])
logger = logging.getLogger(__name__)

_PROMPT = """\
你是点阵徽章设计专家。所有图案由离散的**小圆点**组成，不能有连续实线或实心面。
每个图元的 density 和 width 决定了点阵的疏密，点与点之间必须保持肉眼可见的间隙。

== 图元工具 ==
ring(cx, cy, r, width, density)
  - 在半径 r 的圆周上均匀放置 density 个直径为 width 的圆点。
  - 要保持空心圆环的"虚线感"：density ≤ 40，width ≤ 5

arc(cx, cy, r, a1, a2, width, density)
  - 从角度 a1 到 a2（0°=右, 90°=下）均匀放置 density 个圆点。
  - 用于弧线片段，density ≤ 30, width ≤ 5

line(x1, y1, x2, y2, width, density)
  - 两点间线段上均匀放置 density 个圆点。
  - 表现虚线、放射线、分割线，density ≤ 25, width ≤ 4

poly(points, width, density)
  - 填充多边形（顶点 [[x,y], ...]），内部随机撒 density 个直径为 width 的圆点。
  - **关键**：点数必须稀疏，不能连成片。密度限制：density ≤ 35 且 width ≤ 4
  - 适合做盾形、星形、剑形、钥匙孔形等异形外框或核心符号。

ellipse(cx, cy, rx, ry, width, density)
  - 填充椭圆，仅用于小装饰节点（rx, ry ≤ 16）。
  - 严格限制：density ≤ 20, width ≤ 3，防止变成实心圆饼。

== 小说信息 ==
名称：{name} | 类型：{genre}
简介：{premise}
主角：{protagonist}
基调：{tone} | 进度：第{tick}幕

== 画布 ==
440×330 像素，中心 (220,165)。主体控制在半径 60-130px 内。

== 你必须执行的内部设计流程（不输出） ==
1. **提取意象**：从简介和主角中找到 1-2 个核心物品、符号或形态（例如：钥匙、齿轮、莲花、剑、眼睛、沙漏、树、面具）。
2. **抽象为几何**：将意象拆解成几何元素：
   - 钥匙 → 圆头(中心小椭圆) + 杆(竖线) + 齿(短横线)
   - 莲花 → 中心点 + 周围 5-7 条弧线花瓣
   - 齿轮 → 多边形外框 + 辐射线段 + 中心小环
3. **确定外轮廓**：选择一个呼应故事世界的轮廓。可以是：
   - 直接用 poly 构成复杂多边形（盾形、七角星、菱形、扁六边形、钥匙孔形）
   - 或用多条 line + arc 拼接成闭合轮廓（例如上方弧线 + 下方折线组成心形、水滴形）
   - **禁止**用 ring 做唯一外框，除非内部线条将其改造成明确符号（如十字、缺角）。
4. **搭建骨架**：用 3-6 条 line 或 arc 画出主体的方向性结构（交叉、放射、折线、螺旋等），这些线条必须与意象相关，不能是纯装饰。
5. **添加细节**：在骨架节点上放置小椭圆、小 ring 或短弧线，增强层次。所有细节图元总数 8-15 个。
6. **检查密度**：确保任何一个填充图元（poly / ellipse）的点与点之间**有明显空隙**。想象一下：如果缩小到 32×24 像素，你仍能看清每个独立的点，而不是一团色块。

== 强制性设计规则（违反将导致生成失败） ==
- **外轮廓**：必须使用 poly 或 3 条以上的 line/arc 组合作为外框。ring 只能作为内部装饰。
- **内部骨架**：必须包含至少 3 个 line 或 arc 图元，且这些线条必须构成可辨识的意象符号。
- **禁止实心面**：任何 poly 的 density > 35 或 ellipse 的 density > 20 均禁止。记住你是点阵艺术家，不是填色游戏。
- **禁止同心圆堆砌**：绝对禁止出现"两个以上同心 ring 而无其他结构打破"的靶子图案。
- **禁止傻瓜模板**：以下图案直接判定不合格：十字准星、六角星、三条射线+圆环、纯齿轮、纯星图、纯瞄准镜。每部小说的徽章必须独一无二。
- **不对称与动感**：主体不应完美居中对称，重心可以有 20-40px 的偏移，利用线条平衡画面。

== 颜色（十六进制，不可更改） ==
- 科幻：cyan  #00E5FF
- 奇幻：purple #B44CFF
- 武侠/修仙：amber #FFB74D
- 悬疑：red #FF5252
- 言情：pink #FF80AB
- 历史：gold #FFD54F
直接使用对应 hex 值，不要使用其他颜色。

== 最终输出 ==
只输出一个 JSON 对象，无任何额外文字和代码块标记：
{{
  "color": "#00E5FF",
  "caption": "标题12字内",
  "shapes": [
    {{"type":"poly", "points":[[100,90],[340,90],[300,240],[140,240]], "width":3, "density":28}},
    {{"type":"line", "x1":220,"y1":60,"x2":220,"y2":270,"width":3,"density":20}},
    ...
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
        raw    = llm.generate_with_retry(prompt, max_tokens=2000)
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
