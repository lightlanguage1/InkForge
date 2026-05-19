# StoryDaemon 实施计划

> 与 `ARCHITECTURE_DEEP_ANALYSIS.md`（设计原则）互补，本文是文件级实施指南  
> 顺序按依赖排列：先基础设施，后业务逻辑

---

## 总览

```
Phase 1 ────────────────────────────────────
  [cache]    memory/manager.py    +20 行    tick 级缓存
  [context]  agent/context.py     +60 行    统一 TickContext

Phase 2 ────────────────────────────────────
  [deprecate] agent/multi_stage_planner.py  -640 行
  [merge]     agent/agent.py      ±150 行   6 步 tick 循环

Phase 3 ────────────────────────────────────
  [provider] tools/provider.py    +50 行    新文件，chat() 接口
  [prompt]   agent/prompts.py     ±60 行    system/user 分离

Phase 4 ────────────────────────────────────
  [update]   memory/update.py     +120 行   后处理合并
  [cleanup]  标记废弃文件                  不删除，只标记

总计：+250 行，-640 行
```

---

## Phase 1：基础设施

### 1.1 `memory/manager.py` — 添加 tick 缓存 [x]

**改动**：在 `__init__` 加两行，加两个方法，在 4 个写入方法末尾加 `invalidate_cache()`。

```python
# ——— 1a. __init__ 末尾加两行 ———
def __init__(self, project_path: Path):
    # ...原有代码不变...
    self._cache: Dict[str, Any] = {}   # ← 新增
    self._cache_tick: int = -1         # ← 新增


# ——— 1b. 添加两个方法（加在 _load_counters 之前或之后） ———
def _cache_get(self, key: str, loader: Callable[[], Any]) -> Any:
    """同一 tick 内复用缓存，tick 变更时自动失效。"""
    if self._cache_tick != self.counters.get("_tick", 0):
        self._cache.clear()
        self._cache_tick = self.counters.get("_tick", 0)
    if key not in self._cache:
        self._cache[key] = loader()
    return self._cache[key]

def invalidate_cache(self):
    """数据变更后调用：下次 _cache_get 时重建。"""
    self._cache_tick = -1


# ——— 1c. 在 4 个写入方法末尾加 ———
def save_character(self, character: Character) -> None:
    # ...原有代码...
    self.invalidate_cache()             # ← 新增

def save_location(self, location: Location) -> None:
    # ...原有代码...
    self.invalidate_cache()             # ← 新增

def add_open_loop(self, loop_data: dict) -> OpenLoop:
    # ...原有代码...
    self.invalidate_cache()             # ← 新增

def save_lore(self, lore: Lore) -> None:
    # ...原有代码...
    self.invalidate_cache()             # ← 新增


# ——— 1d. 将高频读取方法改为走缓存（仅改 2 个） ———
def get_all_characters(self) -> List[Character]:
    return self._cache_get("all_characters", lambda: [
        self.load_character(c) for c in self.list_characters()
    ])

def get_all_locations(self) -> List[Location]:
    return self._cache_get("all_locations", lambda: [
        self.load_location(l) for l in self.list_locations()
    ])
```

**为什么只缓存 2 个**：`get_all_characters` 和 `get_all_locations` 是 tick 循环中调用最频繁的方法（context builder、writer context、多个 extractor 都调用它们）。其他方法（如 `load_scene`）调用次数少，不值得缓存。

**测试**：
- 写一个 3-tick 循环，确认 `_cache_get` 被调用但磁盘读取次数不增长
- 调用 `save_character` 后确认缓存被清除

---

### 1.2 `agent/context.py` — 添加 TickContext [x]

**改动**：在 `ContextBuilder` 类内部或旁边加 `TickContext`，加 `build_tick_context()` 方法。

```python
# ——— 1.2a 文件顶部加 dataclass import 和 TickContext ———
from dataclasses import dataclass
from typing import List, Optional
from ..memory.entities import Character, Location, Scene, OpenLoop, PlotBeat

@dataclass
class TickContext:
    """一次 tick 的全部上下文。一次构建，多处复用。"""
    tick: int
    novel_name: str
    foundation: dict
    active_char: Optional[Character] = None
    active_location: Optional[Location] = None
    recent_scenes: List[Scene] = None
    open_loops: List[OpenLoop] = None
    plot_beat: Optional[PlotBeat] = None
    tool_results: List[dict] = None
    qa_feedback: str = ""


# ——— 1.2b 在 ContextBuilder 类中加 build_tick_context() ———
class ContextBuilder:
    # ...原有 __init__ 不变...

    def build_tick_context(
        self,
        project_state: dict,
        current_beat: Optional[PlotBeat] = None
    ) -> TickContext:
        """统一构建一次 tick 的全部上下文。"""
        tick = project_state.get("current_tick", 0)
        foundation = project_state.get("story_foundation", {})

        active_char_id = project_state.get("active_character", "")
        active_char = self.memory.load_character(active_char_id) if active_char_id else None
        active_loc_id = active_char.current_state.location_id if active_char else None
        active_loc = self.memory.load_location(active_loc_id) if active_loc_id else None

        return TickContext(
            tick=tick,
            novel_name=project_state.get("novel_name", "Untitled"),
            foundation=foundation,
            active_char=active_char,
            active_location=active_loc,
            recent_scenes=self._load_recent_scenes(tick),
            open_loops=self._format_open_loops(),
            plot_beat=current_beat,
            qa_feedback=self._load_qa_feedback(tick),
        )

    def _load_recent_scenes(self, tick: int, count: int = 5) -> List[Scene]:
        """加载最近 N 个场景，最新的在前。"""
        scene_ids = self.memory.list_scenes()
        scenes = []
        for sid in reversed(scene_ids[-count:]):
            scene = self.memory.load_scene(sid)
            if scene:
                scenes.append(scene)
        return scenes

    def _load_qa_feedback(self, tick: int) -> str:
        """加载最近 QA 反馈（用于 planner 上下文）。"""
        qa_feedback = ""
        qa_path = self.memory.memory_path / "qa"
        if qa_path.exists():
            qa_files = sorted(qa_path.glob("*.json"))
            if qa_files:
                try:
                    data = json.loads(qa_files[-1].read_text(encoding="utf-8"))
                    issues = data.get("issues", [])
                    if issues:
                        qa_feedback = "; ".join(issues[:3])
                except (IOError, json.JSONDecodeError):
                    pass
        return qa_feedback

    def _format_open_loops(self) -> List[OpenLoop]:
        """获取未解决的开放线索。"""
        return self.memory.get_open_loops()
```

**为什么这么做**：
- `build_tick_context()` 替代原来的 `build_planner_context()`，返回 dataclass 而非 dict
- planner 和 writer 都从同一个 TickContext 取数据
- `_load_recent_scenes` 一次加载两个人共用
- 原有 `build_planner_context()` 保留不动（向后兼容），内部改为先调用 `build_tick_context()` 再转 dict

```python
# ——— 1.2c 原有 build_planner_context 简化为包装 ———
def build_planner_context(self, project_state: dict, current_beat=None) -> dict:
    """保留的兼容接口。"""
    ctx = self.build_tick_context(project_state, current_beat)
    foundation = ctx.foundation
    return {
        "novel_name": ctx.novel_name,
        "current_tick": ctx.tick,
        "active_character_id": ctx.active_char.id if ctx.active_char else "",
        "active_character_name": ctx.active_char.name if ctx.active_char else "Unknown",
        "active_character_details": self._format_character(ctx.active_char) if ctx.active_char else "No active character set.",
        "active_location_name": ctx.active_location.name if ctx.active_location else "Unknown",
        "active_location_details": self._format_location(ctx.active_location) if ctx.active_location else "",
        "story_foundation_summary": (
            f"Genre: {foundation.get('genre', '')}\n"
            f"Premise: {foundation.get('premise', '')}\n"
            f"Setting: {foundation.get('setting', '')}"
        ),
        "recent_scenes_summary": self._format_scenes_summary(ctx.recent_scenes),
        "open_loops_list": self._format_loops(ctx.open_loops),
        "qa_feedback": ctx.qa_feedback,
        "character_relationships": self._format_relationships(
            ctx.active_char.id if ctx.active_char else ""
        ),
        "existing_characters_summary": self._format_existing_chars(),
        "factions_summary": self._format_factions(),
    }
```

---

## Phase 2：核心精简

### 2.1 `agent/multi_stage_planner.py` — 标记废弃 [x]

```python
# ——— 文件顶部加废弃标记 ———
"""
DEPRECATED — 将在下个版本移除。

原因：三阶段规划器增加了不必要的复杂度。
- Stage 1（战略）和 Stage 3（战术）本质是两次 LLM 调用
- 实际使用中 Stage 2（语义检索）与 context builder 的功能重叠
- 单阶段 LLM 调用 + tool use 模式更简洁，效果相同

替代方案：agent.py 的 _generate_plan() 直接调用 LLM。
"""

import warnings
warnings.warn(
    "multi_stage_planner is deprecated. Use single-stage planning via agent._generate_plan().",
    DeprecationWarning,
    stacklevel=2,
)
```

**agent.py 中的引用**：

```python
# ——— agent.py 修改 ———
class StoryAgent:
    def __init__(self, ...):
        # ...
        # 移除 multi_stage_planner 的初始化
        # self.use_multi_stage = config.get('generation.use_multi_stage_planner', True)
        # if self.use_multi_stage:
        #     self.multi_stage_planner = MultiStagePlanner(...)
        
        # 改为总是单阶段：
        self.plot_manager = PlotOutlineManager(self.project_path, llm_interface)

    def _generate_plan(self, context: dict) -> dict:
        """生成计划（仅单阶段）。"""
        prompt = format_planner_prompt(context)
        response = self.llm.generate(prompt, max_tokens=1500)
        plan = json.loads(self._extract_json(response))
        validate_plan(plan)
        return plan
```

**同时移除 `from .multi_stage_planner import MultiStagePlanner`**（文件顶部 import 行）。

---

### 2.2 `agent/agent.py` — 合并 tick 循环 [x]

**核心改动**：`_normal_tick()` 从 19 步缩为 6 步，22 个 `_step_*` 方法缩为 3 个内部函数。

```python
# ——— 重写 _normal_tick ———
def _normal_tick(self) -> Dict[str, Any]:
    """一次 tick：build → plan → execute → write → commit → update."""
    tick = self.state["current_tick"]

    try:
        # 1. 构建上下文（含 plot beat 解析）
        current_beat = self._resolve_plot_beat(tick)
        ctx = self.context_builder.build_tick_context(self.state, current_beat)

        # 2. 生成并执行计划
        plan = self._generate_plan(self.context_builder.build_planner_context(self.state, current_beat))
        results = self.executor.execute_plan(plan, tick)
        self._set_active_char(results, plan)

        # 3. 写场景
        writer_ctx = self.writer_context_builder.build_writer_context(plan, results, self.state)
        scene_data = self.writer.write_scene(writer_ctx)

        # 4. 提交（含评估、张力、QA）
        self.evaluator.evaluate_scene(scene_data["text"], writer_ctx)  # 失败会抛异常
        tension = self.tension_evaluator.evaluate_tension(scene_data["text"], writer_ctx)
        scene_id = self.committer.commit_scene(scene_data, tick, plan)
        self._save_qa(scene_id, tick, plan)
        self._save_tension(scene_id, tension)

        # 5. 后处理（事实、实体、世界观、角色检测、节拍验证）
        self._update_memory(scene_data, scene_id, tick, writer_ctx, current_beat, plan)

        # 6. 状态推进
        self.state["current_tick"] += 1
        self._save_state()

        return {
            "success": True, "tick": tick, "scene_id": scene_id,
            "scene_file": scene_data.get("scene_file", ""),
            "word_count": scene_data.get("word_count", 0),
            "actions_executed": len(results.get("actions_executed", [])),
            "tension": {"level": tension["tension_level"], "category": tension["tension_category"]},
        }

    except RuntimeError as e:
        self.plan_manager.save_error(tick, e, getattr(e, 'plan', {}), getattr(e, 'execution_results', {}))
        raise
    except Exception as e:
        logger.exception("tick %d 失败: %s", tick, e)
        self.plan_manager.save_error(tick, e, {}, {})
        raise


# ——— 新增 _update_memory：替代 8 个 _step_* ———
def _update_memory(self, scene_data, scene_id, tick, writer_ctx, current_beat, plan):
    """场景提交后的内存更新：事实提取 → 实体更新 → 世界观 → 角色检测 → 节拍验证。"""
    # 事实与实体
    if self.config.get('generation.enable_fact_extraction', True):
        facts = self.fact_extractor.extract_facts(scene_data["text"], writer_ctx)
        self.entity_updater.apply_updates(facts, tick, scene_id, self.state)

    # 世界观
    if self.config.get('generation.enable_lore_tracking', True):
        self.lore_extractor.extract_lore(scene_data["text"], writer_ctx, tick, scene_id)

    # 角色检测
    if self.config.get('generation.auto_detect_characters', True):
        self.character_detector.detect_characters(scene_data["text"])

    # 节拍验证
    if current_beat:
        self._verify_beat(scene_id, plan, current_beat, scene_data["text"])

    # 目标晋升
    self._check_goal_promotion(tick)
```

**移除的 `_step_*` 方法**（19 个中保留 4 个内部辅助，其余删除或合并）：

```
移除清单：
  _step_context                     → 合并入 _normal_tick
  _step_plan                        → 合并入 _normal_tick
  _step_execute                     → 合并入 _normal_tick
  _step_set_active_char             → 改为 _set_active_char（私有，不移除）
  _step_save_plan                   → 合并入 _normal_tick
  _step_write_scene                 → 合并入 _normal_tick
  _step_evaluate                    → 合并入 _normal_tick
  _step_evaluate_tension            → 合并入 _normal_tick
  _step_commit_scene                → 合并入 _normal_tick
  _step_save_qa                     → 合并入 _normal_tick
  _step_verify_beat                 → 改为 _verify_beat（私有，不移除）
  _step_save_tension                → 合并入 _normal_tick
  _step_detect_characters           → 合并入 _update_memory
  _step_extract_facts               → 合并入 _update_memory
  _step_update_entities             → 合并入 _update_memory
  _step_extract_lore                → 合并入 _update_memory
  _check_goal_promotion             → 改为 _promote_goals（移到 _update_memory 内）

保留：
  _ensure_plot_beats                → 改为 _resolve_plot_beat（名更短）
  _beat_to_dict                     → 内联
  _build_tick_result               → 内联
  _step_context                     → 已删除
```

**改动前后行数对比**：

```
改前：_normal_tick       58 行 + 19 个辅助方法 ~350 行 = ~408 行
改后：_normal_tick       40 行 + _update_memory 30 行 + _resolve_plot_beat 25 行 + _verify_beat 30 行 = ~125 行
节省：~280 行
```

---

## Phase 3：LLM 层优化

### 3.1 `tools/provider.py` — 新建 LLMProvider [x]

```python
"""LLM 统一接口：字符串 generate + 消息 chat。"""
from typing import List, Dict, Optional


class LLMProvider:
    """LLM 调用封装。支持纯文本和消息列表两种模式。"""

    def __init__(self, backend, backend_type: str = "api"):
        self._backend = backend
        self.backend_type = backend_type

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """纯文本 prompt（兼容旧接口）。"""
        return self._backend.generate(prompt, max_tokens=max_tokens)

    def chat(self, messages: List[Dict], max_tokens: int = 2000) -> str:
        """消息列表模式（支持 Anthropic cache_control）。"""
        if self.backend_type == "anthropic":
            return self._anthropic_chat(messages, max_tokens)
        return self._fallback_chat(messages, max_tokens)

    def _anthropic_chat(self, messages: List[Dict], max_tokens: int) -> str:
        """Anthropic 消息格式。"""
        from anthropic import Anthropic
        import os
        client = Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[m for m in messages if m["role"] != "system"],
            system=next((m["content"] for m in messages if m["role"] == "system"), None),
        )
        return response.content[0].text

    def _fallback_chat(self, messages: List[Dict], max_tokens: int) -> str:
        """非 Anthropic 后端：拼回字符串再 generate。"""
        parts = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(c["text"] for c in content if c["type"] == "text")
            parts.append(content)
        return self._backend.generate("\n\n".join(parts), max_tokens=max_tokens)
```

**集成到 agent**：

```python
# ——— StoryAgent.__init__ 改动 ———
# 改前：
self.llm = llm_interface

# 改后：
from ..tools.provider import LLMProvider
backend_type = "anthropic" if "claude" in config.get("llm.model", "").lower() else "api"
self.llm = LLMProvider(llm_interface, backend_type)
```

---

### 3.2 `agent/prompts.py` — system/user 分离 [x]

**不需要改模板内容**，只需要在每个 prompt 模板前加一个 system 前缀，然后提供拆分函数：

```python
# ——— 文件顶部加 ———
SYSTEM_CORE = """You are a novel writing assistant for an emergent narrative system.

Core rules:
1. Strict POV: write only from the active character's perspective
2. Show don't tell — reveal through action, dialogue, and sensory details
3. Each scene must advance plot or character development
4. Maintain consistency with established lore and character traits
5. Track open story loops — resolve some, create others"""

SYSTEM_PLANNER = SYSTEM_CORE + """\n\nAll output must be valid JSON matching the plan schema."""
SYSTEM_WRITER = SYSTEM_CORE + """\n\nOutput prose only, no meta-commentary."""


# ——— 新增拆分函数 ———
def split_prompt(template: str, context: dict) -> dict:
    """将 prompt 拆为 system（稳定段）和 user（动态段）。
    
    返回 {"system": str, "user": str}，可用于 chat() 接口。
    """
    # 提取稳定前缀（模板中第一段说明文字）
    # 粗略拆分：前 30% 是 instructions，后 70% 是 context
    lines = template.split("\n")
    mid = len(lines) // 3  # 取前 1/3 作为 system 指令
    system_text = "\n".join(lines[:mid])
    
    # 用 context 格式化 user 部分
    user_text = template
    for key, value in context.items():
        placeholder = "{" + key + "}"
        if placeholder in user_text:
            user_text = user_text.replace(placeholder, str(value))
    
    return {"system": system_text, "user": user_text}
```

**实际使用**（在 agent 中）：

```python
# ——— agent.py _generate_plan 用 chat() 替代 generate() ———
def _generate_plan(self, context: dict) -> dict:
    prompt = format_planner_prompt(context)
    
    if hasattr(self.llm, 'chat') and self.llm.backend_type == "anthropic":
        split = split_prompt(prompt, context)
        messages = [
            {"role": "system", "content": [
                {"type": "text", "text": SYSTEM_PLANNER},
                {"type": "text", "text": split["system"],
                 "cache_control": {"type": "ephemeral"}}
            ]},
            {"role": "user", "content": split["user"]}
        ]
        response = self.llm.chat(messages)
    else:
        response = self.llm.generate(prompt, max_tokens=1500)
    
    plan = json.loads(self._extract_json(response))
    validate_plan(plan)
    return plan
```

---

## Phase 4：后处理合并

### 4.1 `memory/update.py` — 新建后处理模块 [x]

```python
"""场景后处理：事实提取 → 实体更新 → 世界观 → 角色检测。

从 agent/ 下的 5 个独立组件合并到此处。减少类层次，保留核心逻辑。
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def update_from_scene(
    scene_text: str,
    scene_id: str,
    tick: int,
    state: dict,
    memory,
    vector,
    llm,
    config: dict,
):
    """场景提交后的全部内存更新。依次执行：
    1. 事实提取 + 实体更新
    2. 世界观提取
    3. 角色检测
    """
    _extract_and_update(scene_text, scene_id, tick, state, memory, llm, config)
    _extract_lore(scene_text, scene_id, tick, memory, llm, config)
    _detect_characters(scene_text, memory, config)


def _extract_and_update(scene_text, scene_id, tick, state, memory, llm, config):
    """提取事实并更新实体。"""
    if not config.get('generation.enable_fact_extraction', True):
        return
    
    from ..agent.fact_extractor import FactExtractor
    from ..agent.entity_updater import EntityUpdater
    
    extractor = FactExtractor(llm, memory, config)
    updater = EntityUpdater(memory, config)
    
    try:
        facts = extractor.extract_facts(scene_text, {"scene_id": scene_id, "tick": tick})
        if facts:
            updater.apply_updates(facts, tick, scene_id, state)
    except (ValueError, json.JSONDecodeError, RuntimeError) as e:
        logger.warning("事实提取失败 (tick %d): %s", tick, e)


def _extract_lore(scene_text, scene_id, tick, memory, llm, config):
    """提取世界观规则。"""
    if not config.get('generation.enable_lore_tracking', True):
        return
    
    from ..agent.lore_extractor import LoreExtractor
    extractor = LoreExtractor(llm, memory, config)
    
    try:
        extractor.extract_lore(scene_text, {"scene_id": scene_id, "tick": tick}, tick, scene_id)
    except (ValueError, json.JSONDecodeError, RuntimeError) as e:
        logger.warning("世界观提取失败 (tick %d): %s", tick, e)


def _detect_characters(scene_text, memory, config):
    """从场景文本中发现新角色名。"""
    if not config.get('generation.auto_detect_characters', True):
        return
    
    from ..agent.character_detector import CharacterDetector
    detector = CharacterDetector(memory, config)
    
    try:
        detector.detect_characters(scene_text)
    except Exception as e:
        logger.warning("角色检测失败: %s", e)
```

**agent.py 中调用**：

```python
# ——— 替换原来的 8 行 _step_* 调用 ———
# 改前：
self._step_detect_characters(scene_data)
facts = self._step_extract_facts(scene_data, writer_context)
update_stats = self._step_update_entities(facts, tick, scene_id, writer_context)
self._step_extract_lore(scene_data, writer_context, tick, scene_id)

# 改后：
from ..memory.update import update_from_scene
update_from_scene(
    scene_text=scene_data["text"],
    scene_id=scene_id,
    tick=tick,
    state=self.state,
    memory=self.memory,
    vector=self.vector,
    llm=self.llm,
    config=self.config,
)
```

---

## 文件变更汇总

```
改动           文件                   操作       行数变化
───────────────────────────────────────────────────────────
Phase 1a       memory/manager.py    修改        +25
Phase 1b       agent/context.py     修改        +65
Phase 2a       agent/multi_stage_planner.py  修改（头部加注释）  +3
Phase 2b       agent/agent.py       修改        -280
Phase 3a       tools/provider.py    新建        +50
Phase 3b       agent/prompts.py     修改        +40
Phase 4a       memory/update.py     新建        +120

总计           7 文件                2 新建 5 修改  +23 / -280
```

---

## 验证方法

```bash
# 1. 基础测试
cd F:\StoryDaemon
python -m pytest tests/ -v --tb=short

# 2. 导入测试（确保无循环依赖）
python -c "
from novel_agent.memory.manager import MemoryManager
from novel_agent.agent.context import TickContext, ContextBuilder
from novel_agent.tools.provider import LLMProvider
from novel_agent.memory.update import update_from_scene
print('所有新导入成功')
"

# 3. 快速 tick 测试（使用现有项目）
python -m novel_agent.cli.main status --project examples/ghost_in_the_node --json
python -m novel_agent.cli.main summarize --project examples/ghost_in_the_node

# 4. 缓存测试
python -c "
from pathlib import Path
from novel_agent.memory.manager import MemoryManager
mm = MemoryManager(Path('examples/ghost_in_the_node'))
chars1 = mm.get_all_characters()
chars2 = mm.get_all_characters()
print(f'缓存可用: {mm._cache_tick != -1}')
print(f'缓存命中: {mm._cache.get(\"all_characters\") is not None}')
"
```

---

## 实施顺序建议

```
步骤 1：memory/manager.py   缓存（副作用最小，先做）
步骤 2：tools/provider.py    新文件（独立无依赖）
步骤 3：agent/context.py     TickContext（provider 就绪后）
步骤 4：agent/prompts.py     system/user 分离
步骤 5：memory/update.py     后处理合并
步骤 6：agent/agent.py       合并 tick 循环（依赖 1-5 全部完成）
步骤 7：multi_stage_planner.py  最后标记废弃
```

**每步完成后执行一次 `pytest -v --tb=short`**。
