# 上下文优化方案（技术储备）

借鉴 A.U.T.O 条件注入 + 变量路由 + 异步任务的设计思路，对 InkForge 的上下文管理做三阶段优化。

## 问题分析

当前 `ContextBuilder` 和 `WriterContextBuilder` 将所有实体全量加载到 prompt。随着小说推进（50+ 场景, 20+ 角色, 30+ 世界观条目），prompt 无限膨胀，最终超出 LLM 上下文窗口。

已有基础：
- `_rank_characters()` — 时间衰减 + 连接度 + active 加权排序
- `_rank_loops()` — 时间衰减 + POV 关联 + importance 加权排序
- `_rank_lore()` — importance 排序 + 去重
- `_entity_time_decay()` — 通用衰减函数: `1.0 / (1.0 + gap * 0.08)`
- `_format_relevant_lore()` — 用 ChromaDB 语义搜索相关世界观（已有但只取 top 5）

**缺失的环节**：只有排序，没有预算约束和裁剪。排序后仍然全部注入。

---

## Phase 1: Token 预算管理器

**目标**：对 Planner 和 Writer 的 prompt 做硬性 token 预算约束，超出时自动裁剪低优先级内容。

**借鉴 A.U.T.O**：条件注入（变量触发开启/关闭内容块）+ 世界书重组（条目按优先级合并/拆分）

### 新增: `novel_agent/context/budget.py`

```python
class ContextBudgeter:
    """Token 预算管理器。

    对上下文做四层注入（Tier 1→4），当预算不足时低 tier 内容被摘要化或删除。
    """

    PLANNER_BUDGET = 6000   # Planner prompt 中文 token 预算
    WRITER_BUDGET  = 8000   # Writer prompt 中文 token 预算

    # Tier 映射: context_key → (tier, 超预算策略)
    TIER_MAP_PLANNER = {
        # ── Tier 1: 必须保留 ──
        "story_foundation_summary":     (1, "keep"),
        "novel_name":                   (1, "keep"),
        "current_tick":                 (1, "keep"),
        "active_character_details":     (1, "keep"),
        "character_relationships":      (1, "keep"),
        "next_plot_beat":               (1, "keep"),
        "beat_enforcement_instructions":(1, "keep"),
        "available_tools_description":  (1, "keep"),

        # ── Tier 2: 优先保留（截断到 top-N） ──
        "recent_scenes_summary":        (2, "top_n=3"),
        "open_loops_list":              (2, "top_n=5"),
        "tension_history":              (2, "keep"),
        "relevant_lore":                (2, "top_n=5"),

        # ── Tier 3: 按需保留 ──
        "pov_candidates":               (3, "top_n=5"),
        "pov_history":                  (3, "top_n=5"),
        "existing_characters_summary":  (3, "top_n=10"),
        "factions_summary":             (3, "top_n=3"),
        "absent_characters":            (3, "top_n=3"),
        "qa_feedback":                  (3, "keep"),
        "skill_context":                (3, "truncate_quarter"),
        "thread_dashboard":             (3, "top_n=5"),

        # ── Tier 4: 预算允许时保留 ──
        "overall_summary":              (4, "truncate_half"),
        "writer_notes":                 (4, "keep"),
        "plan_rejection_feedback":      (4, "keep"),
    }

    def budget_planner_context(self, raw: dict) -> dict:
        """裁剪 Planner 上下文，返回裁剪后的副本。"""
        ...

    def budget_writer_context(self, raw: dict) -> dict:
        """裁剪 Writer 上下文。"""
        ...

    def _estimate_tokens(self, text: str) -> int:
        """粗略估算中文 token 数: len(text) * 1.3。"""
        return int(len(text) * 1.3)

    def _apply_strategy(self, value: str, strategy: str, budget_left: int) -> str:
        """按策略裁剪文本。"""
        ...
```

### 裁剪策略细节

| 策略 | 行为 |
|------|------|
| `keep` | 完整保留 |
| `top_n=N` | 只保留前 N 条（适用于列表类内容） |
| `truncate_half` | 截断到原长度一半 |
| `truncate_quarter` | 截断到原长度 1/4 |
| `drop` | 超预算时直接删除，替换为简短占位符 |

### 集成方式

在 `context.py` 和 `writer_context.py` 的 `build_*_context()` 方法末尾：

```python
# 原有代码
context = {...}  # 构建完整 context

# 新增：预算裁剪（try/except 包裹，失败返回原始 context）
try:
    budgeter = ContextBudgeter(config)
    context = budgeter.budget_planner_context(context)
except Exception:
    logger.warning("上下文预算裁剪失败，使用原始上下文", exc_info=True)

return context
```

### 配置项

```yaml
# config.yaml 新增
generation:
  context_budget_planner: 6000    # Planner prompt token 上限, 0=不限制
  context_budget_writer: 8000     # Writer prompt token 上限, 0=不限制
  context_trim_log: false         # 是否在日志中输出裁剪详情
```

### 需要修改的文件

| 文件 | 改动 |
|------|------|
| `novel_agent/context/budget.py` | **新增** |
| `novel_agent/agent/context.py` | `build_planner_context()` 末尾集成 |
| `novel_agent/agent/writer_context.py` | `build_writer_context()` 末尾集成 |
| `novel_agent/configs/constants.py` | 新增预算常量 |

---

## Phase 2: 场景分类 + 稀疏更新

**目标**：根据场景类型决定更新哪些实体类别，避免每个场景都全量执行后处理管线。

**借鉴 A.U.T.O**：变量体系规划（Step 17）— 先判断"这次变化影响哪个变量组"，再定点更新。

### 新增: `novel_agent/memory/sparse_update.py`

```python
class SceneClassifier:
    """基于 Plan 字段的确定性场景分类器（不调用 LLM）。

    根据 scene_mode + key_change 的关键词做规则判断。
    返回受影响的实体类别集合。
    """

    CATEGORY_KEYWORDS = {
        "emotion":      ["对话", "独白", "回忆", "反思", "告别", "重逢",
                         "dialogue", "monologue", "reflection"],
        "location":     ["移动", "旅行", "到达", "离开", "转移",
                         "travel", "movement", "transition", "arrival"],
        "relationship": ["冲突", "对抗", "和解", "合作", "背叛", "告白",
                         "conflict", "confrontation", "reconciliation"],
        "lore":         ["揭示", "发现", "探索", "研究", "解密",
                         "revelation", "discovery", "exploration"],
        "character_new":["引入", "登场", "初遇", "遇见",
                         "introduction", "meeting", "first encounter"],
    }

    def classify(self, plan: dict) -> set[str]:
        """返回: {"emotion", "relationship", "lore"} 等。"""
        ...


class SparseUpdater:
    """稀疏更新器 — 跳过与当前场景无关的后处理步骤。"""

    def update_from_scene(
        self, scene_text, scene_id, tick, state, memory, llm, config, plan
    ):
        categories = SceneClassifier().classify(plan)

        # 事实提取+实体更新：只在有角色或情绪变化时执行
        if categories & {"character_new", "emotion", "relationship"}:
            _extract_and_update(...)
        else:
            logger.debug("tick %d: 无角色变化，跳过事实提取", tick)

        # 世界观提取：只在有 lore 变化时执行
        if "lore" in categories:
            _extract_lore(...)
        else:
            logger.debug("tick %d: 无世界观引入，跳过世界观提取", tick)

        # 角色检测始终执行（极轻量，正则匹配）
        _detect_characters(...)
```

### 分类决策表

| scene_mode 关键词 | emotion | location | relationship | lore | char_new |
|---|---|---|---|---|---|
| 对话/独白/回忆 | ✅ | | ✅ | | |
| 旅行/移动/到达 | | ✅ | | | |
| 冲突/对抗/和解 | ✅ | | ✅ | ✅ | |
| 揭示/发现/探索 | ✅ | | | ✅ | |
| 引入/初遇/登场 | | | | | ✅ |
| 无法判断（默认） | ✅ | ✅ | ✅ | ✅ | ✅ |

### 需要修改的文件

| 文件 | 改动 |
|------|------|
| `novel_agent/memory/sparse_update.py` | **新增** |
| `novel_agent/memory/update.py` | 添加 `update_from_scene_v2()` 入口 |
| `novel_agent/agent/agent.py` | Tick 管线传入 plan 给 update |

---

## Phase 3: 定期一致性检查

**目标**：在特定 tick 触发独立的 LLM 检查任务，发现长期漂移问题。

**借鉴 A.U.T.O**：副 AI 任务清单（Step 25-29）— 独立提示词 + 周期性触发 + 不阻塞主流程。

### 新增: `novel_agent/agent/periodic.py`

```python
PERIODIC_TASKS = [
    {
        "name": "角色一致性审计",
        "interval": 5,
        "prompt": """检查 {char_name} 在最近 5 幕中的行为和语言。
对比其原始性格设定 ({personality_traits})，判断是否存在 OOC 漂移。
如有漂移，描述具体表现并建议修正方向。不直接修改角色数据。""",
        "action": "log_warnings",
    },
    {
        "name": "世界观冲突检测",
        "interval": 10,
        "prompt": """检查最近新增的世界观条目是否与已有规则存在逻辑冲突。
只检查过去 10 幕内新增的条目。如有冲突，标记双方的 lore_id。""",
        "action": "flag_contradictions",
    },
    {
        "name": "支线进度评估",
        "interval": 5,
        "prompt": """评估所有活跃故事支线的进展：
- 哪些支线在正常推进？
- 哪些支线停滞超过 5 幕？
- 是否有被完全遗忘的支线？
给出建议但不强制执行。""",
        "action": "update_thread_status",
    },
    {
        "name": "角色出场平衡",
        "interval": 8,
        "prompt": """检查所有活跃角色的出场频率。标记超过 8 幕未出场的角色，
分析其回归的最佳时机和方式。不强制要求回归。""",
        "action": "log_warnings",
    },
]

class PeriodicTaskRunner:
    """定期任务执行器。

    设计原则：
    - 所有任务 try/except 包裹，失败只记日志
    - 结果写入 memory metadata（如 _audit_log），不影响核心实体
    - 默认关闭，用户手动开启
    """

    def run_due_tasks(self, tick: int, memory, llm, config) -> list:
        """执行所有到期任务。返回执行结果列表。"""
        ...
```

### 配置项

```yaml
generation:
  enable_periodic_tasks: false          # 默认关闭
  periodic_task_intervals:              # 可覆盖默认间隔
    character_audit: 5
    lore_conflict_check: 10
    thread_progress: 5
    character_balance: 8
```

### 需要修改的文件

| 文件 | 改动 |
|------|------|
| `novel_agent/agent/periodic.py` | **新增** |
| `novel_agent/agent/agent.py` | Finalize 阶段调用 `periodic.run_due_tasks()` |

---

## 实施优先级

| Phase | 影响面 | 复杂度 | 风险 | 建议时机 |
|-------|--------|--------|------|----------|
| Phase 1 | 🔴 高 — 直接影响长篇小说质量 | 中 | 低 — try/except 兜底 | 优先实施 |
| Phase 2 | 🟡 中 — 减少约 30% LLM 调用 | 低 | 低 — 默认全量兜底 | Phase 1 之后 |
| Phase 3 | 🟢 低 — 锦上添花 | 中 | 中 — 增加 LLM 调用 | 用户反馈需要时 |

## 设计原则

全部优化遵循同一原则：
1. **低耦合** — 新增模块通过 try/except 注入，失败不影响核心管线
2. **渐进增强** — 默认行为不变（全量加载、全量更新），用户通过配置开启优化
3. **确定性兜底** — 所有分类/路由逻辑优先用规则，LLM 只做真正需要判断力的部分

## 参考

- A.U.T.O Step 16-19: 变量体系规划 → 分组路由
- A.U.T.O Step 20-21: 条件显示配置 → 动态内容注入
- A.U.T.O Step 25-29: 副 AI 任务清单 → 异步周期性检查
- A.U.T.O Step 28-29: 世界书重组 → Token 优化
