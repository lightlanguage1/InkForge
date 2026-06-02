"""点阵肖像生成 — GLM-4.5V 生成 + 服务端渲染 + 视觉自校验流水线。"""

import json
import logging
import time
import base64
import io
import math

import requests
from fastapi import APIRouter

from ..deps import resolve_project
from ...cli.project import load_project_state

router = APIRouter(prefix="/api/v1", tags=["画像"])
logger = logging.getLogger(__name__)

# ── 硅基流动 API ──
SF_URL = "https://api.siliconflow.cn/v1/chat/completions"
SF_KEY = "sk-ozqdttngwuggxekgjadbabgrqwmjixrdjjgxplewnrlnxjez"
SF_MODEL = "zai-org/GLM-4.5V"

DESIGN_SYSTEM = (
    "你是一位世界级 Logo 与物品设计大师，擅长用极简的点阵线条勾勒出极具设计感的徽章。"
    "你的每一件作品都是艺术品，简洁、优雅、令人过目不忘。你只输出 JSON，不解释。"
)
CRITIC_SYSTEM = (
    "你是一位严格的设计评审专家。你会仔细观察点阵徽章的设计质量并给出评分和改进建议。"
    "只输出 JSON。"
)

MAX_ATTEMPTS = 3
MIN_SCORE = 7


# ── LLM 调用 ──

def _call_llm(messages: list, max_tokens: int = 3000, temperature: float = 0.9, json_mode: bool = True) -> str:
    payload = {
        "model": SF_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {SF_KEY}", "Content-Type": "application/json"}
    for attempt in range(3):
        try:
            resp = requests.post(SF_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.warning("LLM attempt %d: HTTP %d %s", attempt + 1, resp.status_code, resp.text[:150])
        except Exception as exc:
            logger.warning("LLM attempt %d: %s", attempt + 1, exc)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("LLM API failed after 3 attempts")


# ── 解析 ──

def _parse_shapes(raw: str) -> dict:
    import re
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*"shapes"[^{}]*\[.*?\][^{}]*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError("无法解析 LLM JSON")
    color = data.get("color", "#FFB74D")
    caption = str(data.get("caption", ""))[:12]
    shapes = data.get("shapes", [])
    if not shapes:
        pts = data.get("points", [])
        if pts:
            shapes = [{"type": "scatter", "cx": 220, "cy": 165, "rx": 100, "ry": 80, "count": min(len(pts), 30), "dot_r": 2, "density": 1.5}]
    return {"color": color, "caption": caption, "shapes": shapes}


# ── 兜底 ──

def _fallback_portrait(state: dict) -> dict:
    name = state.get("novel_name", "故事")
    return {
        "color": "#FFB74D",
        "caption": name[:8] or "故事",
        "shapes": [
            {"type": "ring", "cx": 220, "cy": 165, "r": 85, "width": 3, "density": 28},
            {"type": "ring", "cx": 220, "cy": 165, "r": 55, "width": 2, "density": 18},
            {"type": "scatter", "cx": 220, "cy": 165, "rx": 100, "ry": 80, "count": 18, "dot_r": 2, "density": 1.2},
        ],
    }


# ── 服务端渲染 shapes → PNG ──

def _render_to_png(shapes: list, color_hex: str = "#FFB74D", w: int = 440, h: int = 330) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed, cannot render preview")
        return b""
    img = Image.new("RGBA", (w, h), (15, 10, 6, 255))
    draw = ImageDraw.Draw(img)
    r, g, b = int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16)

    for s in shapes:
        stype = s.get("type", "")
        try:
            _draw_shape(draw, s, stype, r, g, b)
        except Exception:
            pass

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_shape(draw, s, stype, r, g, b):
    """Route to the correct drawer based on shape type."""
    if stype == "ring":
        cx, cy, rr = s.get("cx", 220), s.get("cy", 165), s.get("r", 80)
        w, density = s.get("width", 3), int(s.get("density", 30))
        dot_r = max(1, w // 2)
        for i in range(density):
            angle = 2 * math.pi * i / density
            px, py = int(cx + rr * math.cos(angle)), int(cy + rr * math.sin(angle))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "arc":
        cx, cy, rr = s.get("cx", 220), s.get("cy", 165), s.get("r", 70)
        a1, a2 = s.get("a1", 0), s.get("a2", 180)
        w, density = s.get("width", 3), int(s.get("density", 22))
        dot_r = max(1, w // 2)
        a1r, a2r = math.radians(a1), math.radians(a2)
        if a2r < a1r:
            a2r += 2 * math.pi
        for i in range(density):
            angle = a1r + (a2r - a1r) * i / max(1, density - 1)
            px, py = int(cx + rr * math.cos(angle)), int(cy + rr * math.sin(angle))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "line":
        x1, y1, x2, y2 = s.get("x1", 0), s.get("y1", 0), s.get("x2", 440), s.get("y2", 330)
        w, density = s.get("width", 3), int(s.get("density", 18))
        dot_r = max(1, w // 2)
        for i in range(density):
            t = i / max(1, density - 1)
            px, py = int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t)
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "poly":
        pts = s.get("points", [])
        if len(pts) < 3:
            return
        w, density = s.get("width", 3), int(s.get("density", 22))
        dot_r = max(1, w // 2)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        import random as _rnd
        for _ in range(density * 15):
            px, py = _rnd.randint(min_x, max_x), _rnd.randint(min_y, max_y)
            inside, j = False, len(pts) - 1
            for i in range(len(pts)):
                if ((pts[i][1] > py) != (pts[j][1] > py)) and (px < (pts[j][0] - pts[i][0]) * (py - pts[i][1]) / (pts[j][1] - pts[i][1]) + pts[i][0]):
                    inside = not inside
                j = i
            if inside:
                draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "ellipse":
        cx, cy, rx, ry = s.get("cx", 220), s.get("cy", 165), s.get("rx", 10), s.get("ry", 14)
        w, density = s.get("width", 2), int(s.get("density", 14))
        dot_r = max(1, w // 2)
        import random as _rnd
        for _ in range(density * 5):
            angle = _rnd.uniform(0, 2 * math.pi)
            dist = _rnd.uniform(0, 1) ** 0.5
            px, py = int(cx + rx * dist * math.cos(angle)), int(cy + ry * dist * math.sin(angle))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "dot_grid":
        cx, cy, ww, hh = s.get("cx", 220), s.get("cy", 165), s.get("w", 40), s.get("h", 40)
        spacing = s.get("spacing", 7)
        dot_r = int(s.get("dot_r", 2))
        x0, y0 = int(cx - ww / 2), int(cy - hh / 2)
        ix = 0
        while x0 + ix * spacing < cx + ww / 2:
            jy = 0
            while y0 + jy * spacing < cy + hh / 2:
                px, py = int(x0 + ix * spacing), int(y0 + jy * spacing)
                draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 200))
                jy += 1
            ix += 1
    elif stype == "scatter":
        cx, cy, rx, ry = s.get("cx", 220), s.get("cy", 165), s.get("rx", 60), s.get("ry", 60)
        count, dot_r = int(s.get("count", 15)), int(s.get("dot_r", 2))
        import random as _rnd
        for _ in range(count):
            angle = _rnd.uniform(0, 2 * math.pi)
            dist = _rnd.uniform(0, 1) ** 0.5
            px, py = int(cx + rx * dist * math.cos(angle)), int(cy + ry * dist * math.sin(angle))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "radial":
        cx, cy, rr = s.get("cx", 220), s.get("cy", 165), s.get("r", 90)
        rays, w, density = int(s.get("rays", 8)), s.get("width", 3), int(s.get("density", 12))
        dot_r = max(1, w // 2)
        for i in range(rays):
            angle = 2 * math.pi * i / rays
            for j in range(density):
                dist = rr * (j + 1) / density
                px, py = int(cx + dist * math.cos(angle)), int(cy + dist * math.sin(angle))
                draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "zigzag":
        x1, y1 = s.get("x1", 0), s.get("y1", 0)
        x2, y2 = s.get("x2", 440), s.get("y2", 330)
        amp, segs = s.get("amplitude", 30), int(s.get("segments", 6))
        w, density = s.get("width", 3), int(s.get("density", 20))
        dot_r = max(1, w // 2)
        dx_, dy_ = (x2 - x1) / segs, (y2 - y1) / segs
        length = math.hypot(dx_, dy_) or 1
        for seg in range(segs):
            mid = amp if seg % 2 == 0 else -amp
            px_off, py_off = -dy_ / length * mid, dx_ / length * mid
            xa, ya = x1 + dx_ * seg + px_off, y1 + dy_ * seg + py_off
            xb, yb = x1 + dx_ * (seg + 1) - px_off, y1 + dy_ * (seg + 1) - py_off
            for j in range(max(1, density // segs)):
                t = j / max(1, density // segs - 1)
                px, py = int(xa + (xb - xa) * t), int(ya + (yb - ya) * t)
                draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))
    elif stype == "spiral":
        cx, cy = s.get("cx", 220), s.get("cy", 165)
        r0, r1 = s.get("r0", 10), s.get("r1", 90)
        turns, w = s.get("turns", 2), s.get("width", 3)
        density = int(s.get("density", 30))
        dot_r = max(1, w // 2)
        for i in range(density):
            t = i / max(1, density - 1) * turns * 2 * math.pi
            rr = r0 + (r1 - r0) * i / max(1, density - 1)
            px, py = int(cx + rr * math.cos(t)), int(cy + rr * math.sin(t))
            draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r], fill=(r, g, b, 220))


# ── 视觉校验：渲染 → 截图 → GLM-4.5V 评分 ──

def _vision_score(shapes: list, color_hex: str) -> tuple:
    """渲染 shapes → PNG → 发给视觉模型评分。返回 (score, feedback)。"""
    png_bytes = _render_to_png(shapes, color_hex)
    if not png_bytes:
        return MIN_SCORE, ""
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    messages = [
        {"role": "system", "content": CRITIC_SYSTEM},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": (
                "请评审这个点阵徽章设计，从以下维度打分（1-10）：\n"
                "1. 构图美感：布局是否优雅、平衡\n"
                "2. 点阵质感：点间距是否合理，有无糊成一片的实心区域\n"
                "3. 意象契合度：图案是否传达了核心意象\n"
                "4. 留白与呼吸感：画面是否有足够留白\n\n"
                "返回 JSON：\n"
                '{"total": 平均分, "feedback": "如果分数>=7填空字符串，否则1-2句中文改进建议"}'
            )},
        ]},
    ]
    try:
        raw = _call_llm(messages, max_tokens=300, temperature=0.3, json_mode=True)
        result = json.loads(raw.strip().lstrip("```json").rstrip("```").strip())
        score = int(result.get("total", MIN_SCORE))
        feedback = str(result.get("feedback", ""))
        logger.info("Vision score: %d/10 %s", score, feedback)
        return score, feedback
    except Exception as exc:
        logger.warning("Vision scoring failed: %s", exc)
        return MIN_SCORE, ""


# ── Prompt ──

def _build_prompt(state: dict, tick: int, feedback: str = "") -> str:
    foundation = state.get("story_foundation") or {}
    name = state.get("novel_name", "未知")
    genre = foundation.get("genre", "未知")
    premise = (foundation.get("premise", "") or "")[:200]
    protagonist = (foundation.get("protagonist_archetype", "") or "")[:150]
    tone = (foundation.get("tone", "") or "")[:100]

    fb_block = ""
    if feedback:
        fb_block = f"\n### 上一版评审反馈（请务必改进）\n{feedback}\n"

    return f"""你是一位世界级 Logo 与物品设计大师。根据小说的核心意象，设计一个极具设计感、优雅简洁的点阵徽章。

### 核心设计铁律
- 绝不用实心面：所有图形必须由点构成，保持通透感。poly/ellipse 的 density 要低（不超过20），让点与点之间有肉眼可见的间隙。
- 线条感优先：优先用 ring、arc、line、spiral、radial、zigzag 等线性图元来勾勒轮廓。它们天然就是虚线，最有点阵美学。
- 留白是艺术：不要把画布填满。主体控制在中心区域，用 scatter 在周边点缀少量星尘（5-15个点）。
- 2-4 种图元足够：选用最契合意象的 2-4 种即可，不要堆砌。
- 不对称加动感：故意打破对称，让图案像在运动。
{fb_block}
### 可用图元
| 图元 | 参数 | 说明 |
|------|------|------|
| ring | cx,cy,r,width,density | 空心圆环，width<=4, density<=38 |
| arc | cx,cy,r,a1,a2,width,density | 圆弧片段，density<=30 |
| line | x1,y1,x2,y2,width,density | 虚线线段，width<=4, density<=20 |
| poly | points,width,density | 多边形轮廓，points=[[x,y],...]，density<=20 |
| ellipse | cx,cy,rx,ry,width,density | 椭圆，rx/ry<=16，小装饰，density<=15 |
| dot_grid | cx,cy,w,h,spacing,dot_r | 矩形点阵，w,h<=60, spacing>=7 |
| scatter | cx,cy,rx,ry,count,dot_r | 椭圆内散布点，count<=20, dot_r<=3 |
| radial | cx,cy,r,rays,width,density | 放射线，rays<=12, density<=12 |
| zigzag | x1,y1,x2,y2,amplitude,segments,width,density | 锯齿折线，density<=25 |
| spiral | cx,cy,r0,r1,turns,width,density | 螺旋，turns 1.5-3, density<=35 |

### 经典配色
科幻=#00E5FF 奇幻=#B44CFF 修仙/武侠=#FFB74D 悬疑=#FF5252 言情=#FF80AB 历史=#FFD54F

### 小说信息
名称：{name} / 类型：{genre} / 简介：{premise}
主角特质：{protagonist} / 基调：{tone} / 进度：第{tick}幕

### 输出格式（严格 JSON）
{{"color":"#hex","caption":"6-10字标题","shapes":[{{"type":"ring","cx":220,"cy":165,"r":85,"width":3,"density":32}},...]}}
"""


# ── Endpoint ──

@router.get("/project/{project_id}/portrait")
def get_portrait(project_id: str, force: bool = False):
    project_dir = resolve_project(project_id)
    cache_file = project_dir / "portrait.json"
    state = load_project_state(str(project_dir))
    tick = state.get("current_tick", 0)

    if not force and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            portrait = cached.get("portrait", {})
            if portrait.get("shapes") and abs(cached.get("cached_tick", -999) - tick) < 5:
                return portrait
        except Exception:
            pass

    # ── 生成 + 视觉校验循环 ──
    best_portrait = None
    best_score = 0
    feedback = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info("Portrait generation attempt %d/%d", attempt, MAX_ATTEMPTS)
            prompt = _build_prompt(state, tick, feedback)
            raw = _call_llm([
                {"role": "system", "content": DESIGN_SYSTEM},
                {"role": "user", "content": prompt},
            ])
            portrait = _parse_shapes(raw)
            shapes = portrait.get("shapes", [])
            color = portrait.get("color", "#FFB74D")

            if not shapes:
                continue

            # Vision scoring
            score, fb = _vision_score(shapes, color)
            logger.info("Attempt %d score: %d/10", attempt, score)

            if score > best_score:
                best_score = score
                best_portrait = portrait

            if score >= MIN_SCORE:
                logger.info("Accepted at attempt %d with score %d", attempt, score)
                break

            feedback = fb if fb else "请改进设计质量，增加设计感和艺术性"
        except Exception as exc:
            logger.warning("Attempt %d failed: %s", attempt, exc)

    if best_portrait:
        cache_file.write_text(
            json.dumps({"cached_tick": tick, "portrait": best_portrait}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return best_portrait

    # 全部失败 → fallback
    portrait = _fallback_portrait(state)
    try:
        cache_file.write_text(
            json.dumps({"cached_tick": tick, "portrait": portrait}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return portrait
