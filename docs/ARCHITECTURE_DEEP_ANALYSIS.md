# InkForge 架构改进方案

> 参考 Claude Code 设计哲学：简洁的 harness 优于复杂的 pipeline，上下文是核心接口，而非组件拼盘  
> 日期：2026-05-05

---

## 设计原则

1. **一个循环，而非 19 步** — Claude Code 用一个 while 循环驱动全部行为。InkForge 有 19 个步骤方法、15+ 组件，不必要的分层
2. **上下文即接口** — 所有组件从统一上下文读写，而非各自拼 prompt
3. **缓存是架构问题，不是优化问题** — 没有缓存的 tick 循环是架构缺陷
4. **够用即可** — 不提前抽象、不预留接口、不为"未来可能"设计

---

## 问题本质

InkForge 的核心问题不是代码质量，而是**过度设计**：

```
当前架构                     Claude Code 风格
─────────────────            ─────────────────
19 步 tick 流水线            1 个 loop + 工具
15+ 组件类                   4-5 个模块
3 层规划器（multi-stage）    1 次 LLM 调用 + tool use
独立上下文构建器 × 2         统一 Context 对象
独立 Schema 验证             内联校验
独立 plan manager            文件写入即持久化
独立 evaluator/system        不需要单独类
```

---

## 改进方案

### 1. 合并 Tick 循环 [x]

**当前**：`_normal_tick()` 调用 19 个 `_step_*` 方法

**改为**：

```python
def tick(self) -> dict:
    """一次 tick = plan → execute → write → commit."""
    context = self._build_context()
    plan = self._call_llm(PLANNER_PROMPT, context)
    execute_results = self._run_tools(plan.pop("actions", []))
    scene_text = self._call_llm(WRITER_PROMPT, {**context, **execute_results})
    scene_id = self._commit(scene_text, plan)
    self._update_memory(scene_text, scene_id)
    self.state["current_tick"] += 1
    self._save_state()
    return self._result(scene_id, scene_text, plan)
```

合并清单：

| 当前 19 步 | 改为 |
|---|---|
| `_ensure_plot_beats` | 合并入 `_build_context` |
| `_step_context` | `_build_context` |
| `_step_plan` | `_call_llm` |
| `validate_plan` | 内联于 `_call_llm` |
| `_step_execute`, `_step_set_active_char`, `_step_save_plan` | `_run_tools` |
| Writer context + write + evaluate | `_call_llm` + `_commit` |
| `_step_evaluate_tension`, `_step_verify_beat`, `_step_detect_characters` | `_update_memory` |
| `_step_extract_facts`, `_step_update_entities`, `_step_extract_lore` | `_update_memory` |
| `_step_commit_scene`, `_step_save_qa`, `_step_save_tension` | `_commit` |
| `_check_goal_promotion` | `_update_memory` |

> **为什么这么做**：19 步拆分是在"保持原有逻辑不变"的前提下做的重构。现在可以进一步——这些步骤不需要各自为政。`_update_memory` 内部按顺序调子函数，但没有必要暴露为 8 个独立步骤。

---

### 2. 统一 Context，消除两个 Builder [x]

**当前**：`ContextBuilder`（planner 用）+ `WriterContextBuilder`（writer 用），各自从磁盘读数据、各自拼 prompt

**改为**：

```python
@dataclass
class TickContext:
    """一次 tick 的全部上下文。一次构建，多处复用。"""
    state: dict                      # state.json
    tick: int
    active_char: Optional[Character]
    location: Optional[Location]
    recent_scenes: List[Scene]
    open_loops: List[OpenLoop]
    plot_beat: Optional[PlotBeat]
    foundation: dict
    # 以下由 _run_tools 填充
    tool_results: List[dict] = None

def _build_context(self) -> TickContext:
    """构建一次 tick 的全部上下文（带缓存）。"""
    if self._context and self._context.tick == self.state["current_tick"]:
        return self._context
    self._context = TickContext(
        state=self.state,
        tick=self.state["current_tick"],
        active_char=self._load_active_character(),
        location=self._load_current_location(),
        recent_scenes=self._load_recent_scenes(),
        open_loops=self._load_open_loops(),
        plot_beat=self._resolve_plot_beat(),
        foundation=self.state.get("story_foundation", {}),
    )
    return self._context
```

然后构建 prompt 时直接从 context 取数据：

```python
def _planner_prompt(self, ctx: TickContext) -> str:
    return f"""...
Current tick: {ctx.tick}
Active character: {ctx.active_char.name}
Location: {ctx.location.name}
Open loops: {len(ctx.open_loops)}
..."""

def _writer_prompt(self, ctx: TickContext) -> str:
    return f"""...
Scene intention: {ctx.plot_beat.description if ctx.plot_beat else 'continue story'}
Recent scenes full text:
{chr(10).join(s.full_text for s in ctx.recent_scenes[:2])}
..."""
```

> **为什么这么做**：当前两个 builder 各自查数据库、各自拼字符串，中间很多重复工作。统一 context 后，数据只加载一次、缓存贯穿整个 tick，两处 prompt 拼装只是对同一 context 的不同投影。

---

### 3. 最简单的缓存策略 [x]

**当前**：每 tick 30-50 次独立磁盘读取，无任何缓存

**改为三行改动**：

```python
# memory/manager.py — 添加 tick 级缓存

class MemoryManager:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self._cache: Dict[str, Any] = {}   # ← 新增
        self._cache_tick: int = -1         # ← 新增
    
    def _cache_get(self, key: str, loader: Callable) -> Any:
        if self._cache_tick == self._last_tick:   # 同一 tick 内复用
            if key in self._cache:
                return self._cache[key]
        else:
            self._cache.clear()
            self._cache_tick = self._last_tick
        value = loader()
        self._cache[key] = value
        return value
    
    def invalidate_cache(self):
        """数据变更后调用."""
        self._cache_tick = -1
```

调用方改动：

```python
# 改动前
def get_all_characters(self) -> List[Character]:
    return [self.load_character(c) for c in self.list_characters()]

# 改动后
def get_all_characters(self) -> List[Character]:
    return self._cache_get("all_characters", lambda: [
        self.load_character(c) for c in self.list_characters()
    ])
```

**缓存失效点**（4 处）：
- `save_character()` → `self.invalidate_cache()`
- `save_location()` → `self.invalidate_cache()`
- `add_open_loop()` / `resolve_loop()` → `self.invalidate_cache()`
- `save_lore()` → `self.invalidate_cache()`

> **为什么这么做**：不需要 lru_cache、不需要 TTL、不需要版本号。tick 是天然的单位——同一 tick 内数据不变，cache 直接复用。下个 tick 开始时自然失效。总计约 20 行代码。

---

### 4. Prompt 缓存：只做最直接的 [x]

**当前**：无 system/user 分离，无 Anthropic cache_control

**改为**：只在 Anthropic 后端做一件事——结构分离

```python
# agent/prompts.py
SYSTEM_CORE = """You are a novel writing assistant. Rules:
- Strict POV: write only from the active character's perspective
- Show don't tell
- Each scene must advance plot or character
- Maintain consistency with established lore"""

# writer_context.py 或对应的 prompt builder
def _build_anthropic_messages(ctx: TickContext) -> list:
    static_section = _format_static_context(ctx)  # 基础设定 + 写作约束 + 格式说明
    dynamic_section = _format_dynamic_context(ctx)  # 本 tick 特定内容
    
    return [
        {"role": "system", "content": [
            {"type": "text", "text": SYSTEM_CORE},
            {"type": "text", "text": static_section,
             "cache_control": {"type": "ephemeral"}}
        ]},
        {"role": "user", "content": dynamic_section}
    ]
```

**不做**（避免过度设计）：
- 不做应用层 PromptCache 类
- 不做 token 计数和分段缓存
- 不做 OpenAI cache 优化（自动的，不需要代码）
- 不做跨 tick 缓存（稳定段变动少，但 Anthropic 5 分钟 TTL 也就覆盖连续 tick）

> **为什么这么做**：Anthropic 的 prompt caching 只需要 system/user 分离 + 一条 `cache_control` 标记。不需要额外抽象。对于小说生成（通常连续运行），5 分钟 TTL 够覆盖同一写作 session 的连续 tick。

---

### 5. 简化 LLM 后端 [x]

**当前**：`multi_provider_llm.py` 处理 6 种后端，接口只接受字符串

**改为**：在现有接口之上加一层消息支持

```python
# tools/provider.py — 新增统一接口
class LLMProvider:
    """统一的 LLM 调用接口。"""
    
    def generate(self, prompt: str, **kwargs) -> str:
        """兼容旧接口：纯文本 prompt."""
        return self._backend.generate(prompt, **kwargs)
    
    def chat(self, messages: list, **kwargs) -> str:
        """消息列表接口（支持 cache_control）。"""
        # 后端具体实现
        if self.backend_type == "anthropic":
            return self._anthropic_chat(messages, **kwargs)
        # 非 anthropic 后端 fallback
        return self._fallback_chat(messages, **kwargs)
    
    def _fallback_chat(self, messages: list, **kwargs) -> str:
        """将消息列表拼回字符串。"""
        prompt = "\n\n".join(
            m.get("content") if isinstance(m.get("content"), str)
            else "\n".join(
                c["text"] for c in m["content"] if c["type"] == "text"
            )
            for m in messages
        )
        return self._backend.generate(prompt, **kwargs)
```

> **为什么这么做**：不重写整个 LLM 后端层。只加一个 `chat()` 方法和 Anthropic 分支。其他后端自动 fallback。~30 行代码。

---

### 6. 精简组件结构 [x]

**目标**：减少文件数量和类层次

```
当前 15+ agent 组件                    精简后 5 模块
─────────────────────────              ──────────────
agent.py (StoryAgent)                  agent.py (StoryAgent + tick loop)
context.py (ContextBuilder)            context.py (统一 TickContext)
writer_context.py (WriterContextB.)      ↑ 合并入 context.py
prompts.py (4 模板)                    prompts.py (精简为 2 模板)
schemas.py                               ↑ 内联到 prompts.py
runtime.py (PlanExecutor)              tools.py (工具执行)
plan_manager.py                          ↑ 内联到 agent.py
writer.py (SceneWriter)                writer.py (场景生成)
evaluator.py                             ↑ 内联到 writer.py
scene_committer.py                       ↑ 内联到 agent.py
tension_evaluator.py                     ↑
character_detector.py                    ↑ 合并为 memory/
fact_extractor.py                        ↑ 下的 update.py
entity_updater.py                        ↑
lore_extractor.py                        ↑
lore_contradiction_detector.py           ↑ 删除（不必要）
multi_stage_planner.py                   ↑ 删除（单阶段够用）
```

**不做**：
- 不删除现有文件（向后兼容），只标记废弃
- 不重写 memory/manager.py（体积大但职责明确）
- 不重写 tools/（接口稳定）

---

### 7. 快速见效清单

按投入产出比排序：

| # | 改动 | 文件 | 行数 | 效果 |
|---|------|------|------|------|
| 1 | MemoryManager 添加 tick 缓存 | `memory/manager.py` | ~20 | 减少 80% 磁盘 I/O |
| 2 | 统一 TickContext | `agent/context.py` | ~50 | 消除重复数据加载 |
| 3 | 合并 tick 循环 | `agent/agent.py` | ~80 | 19 步 → 6 步 |
| 4 | Anthropic 消息结构 | `agent/prompts.py` | ~30 | 启用 prompt caching |
| 5 | 加 `chat()` 接口 | `tools/provider.py` 新文件 | ~40 | 支持 cache_control |
| 6 | 精简 prompt 模板 | `agent/prompts.py` | ~60 | 4 模板 → 2 模板 |
| 7 | 合并后处理组件 | `agent/` | ~100 | 8 文件 → 1 文件 |
| 8 | 删除 multi-stage planner | `agent/` | -640 | 消除不必要的复杂度 |

**总计约 300 行新增，-1000 行删除**。

---

## 不做的事

以下在 Claude Code 设计哲学下明确**不处理**：

| 问题 | 原因 |
|------|------|
| 中文分词 `len(text.split())` | 对故事生成没有实质性影响，字数只是参考 |
| `enable_thinking` 未使用 | 配置项在前端存在无害，运行时没被读即可 |
| `get_character_by_name` 子串匹配 | 工作正常，改了可能破坏现有项目 |
| Lore/Location ID 前缀不统一 | 前缀不同，不会碰撞，改了要迁移数据 |
| VectorStore 删除不覆盖 Lore/Faction | 项目中极少删除 lore/faction |
| PlotOutlineManager 静默备份 | 设计意图，崩溃时保护数据 |
| Lazy import 过多 | 启动性能 vs 代码清晰度的取舍，当前平衡可接受 |
| 配置访问风格不统一 | 纯代码风格问题，不影响正确性 |
| 测试覆盖率 | 独立问题，不在架构变更范围内 |

---

## 最终架构（简化后）

```
┌─────────────────────────────────────────────────────┐
│                    tick() loop                       │
│                                                      │
│  1. _build_context() → TickContext                   │
│  2. plan = _call_llm(PLANNER, ctx)                   │
│  3. _run_tools(plan.actions)                         │
│  4. scene = _call_llm(WRITER, ctx + tool_results)     │
│  5. _commit(scene) → scene_id                        │
│  6. _update_memory(scene_id)                          │
│                                                      │
│  7. state.tick += 1; _save_state()                   │
└─────────────────────────────────────────────────────┘
        │
        ├── context.py → TickContext + prompt builders
        ├── writer.py → SceneWriter（调用 LLM）
        ├── tools.py → 工具注册 + 执行
        └── memory/
            ├── manager.py → CRUD + tick cache
            ├── update.py → 后处理（事实/世界观/张力）
            └── vector_store.py → ChromaDB
```

**核心度量**：
- tick 循环：1 个函数，6 个步骤，约 60 行
- 上下文：1 个 dataclass，贯穿整个 tick
- 缓存：1 个 dict + 1 个 tick 计数器
- Prompt caching：1 条 cache_control 标记
- 后处理：1 个函数内部按序调用
