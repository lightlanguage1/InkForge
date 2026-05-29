# 实施过程中发现的问题

> 与 `ARCHITECTURE_DEEP_ANALYSIS.md` 和 `IMPLEMENTATION_PLAN.md` 互补，本文记录实现过程中发现的未完成项、模糊点和不一致处。

## 未连线项（基础设施已就绪但未接入）

### 1. LLMProvider.chat() 未接入 agent

**位置**：`tools/provider.py` → `agent/agent.py`

**现状**：`LLMProvider` 已创建，支持 `generate()` 和 `chat()` 双接口。但 `_generate_plan()` 仍直接用 `self.llm.generate()`（旧接口），未使用 `chat()`。

**影响**：Anthropic prompt caching 虽在 `provider.py` 层支持，但实际 tick 循环中未触发。

**接入方式**（约 10 行）：

```python
# agent/agent.py -> __init__
from ..tools.provider import LLMProvider
backend_type = "anthropic" if "claude" in config.get("llm.model", "").lower() else "api"
self.llm = LLMProvider(llm_interface, backend_type)

# agent/agent.py -> _generate_plan
if self.llm.backend_type == "anthropic":
    from .prompts import split_prompt, SYSTEM_PLANNER
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
    response = self.llm.generate(prompt, max_tokens=max_tokens)
```

### 2. split_prompt() 已存在但未启用

**位置**：`agent/prompts.py` → `agent/agent.py`

**现状**：`split_prompt()` 函数已实现，可以将模板拆为 system/user 两部分。但 agent 的 `_generate_plan()` 仍调用 `format_planner_prompt()` 拼完整字符串后传给 `generate()`。

**影响**：同上，prompt caching 未生效。

**解决**：与 #1 一同处理（接入 LLMProvider.chat() 时自然使用 split_prompt）。

### 3. TickContext 已创建但未作为主要接口

**位置**：`agent/context.py` → `agent/agent.py`

**现状**：`build_tick_context()` 已实现，返回 `TickContext` dataclass。但 `_normal_tick()` 仍调用 `build_planner_context()`（兼容旧接口）。`build_planner_context()` 内部虽调用了 `build_tick_context()`，但数据流转多了一层 dict 转换。

**影响**：无功能性影响，但 writer 端仍通过 `WriterContextBuilder` 独立加载数据，未复用 TickContext。

**建议**：下一轮迭代中让 WriterContextBuilder 接收 TickContext 而非重新加载。

---

## 功能删除与行为变化

### 4. LoreContradictionDetector 不再被调用

**位置**：`memory/update.py` vs 旧 `agent/agent.py`

**现状**：旧的 `_save_lore_items()` 方法在保存 lore 后会调用 `self.lore_detector.update_contradictions(lore_id)`。新 `update_from_scene()` 中 LoreExtractor 的 `extract_lore()` 内部可能自行处理保存和索引，但不再显式调用 contradiction detection。

**影响**：lore 的矛盾检测丢失。如功能重要需加到 `LoreExtractor` 内部或 `update_from_scene` 中。

**注意**：`LoreContradictionDetector` 类本身未删除（仍在 `agent/lore_contradiction_detector.py`），只是不再被调用。

### 5. `update_from_scene()` 签名与计划不符

**位置**：`memory/update.py`

**现状**：实现签名为 `(scene_text, scene_id, tick, state, memory, llm, config)`，比计划中少了 `vector` 参数。原因是各子组件（FactExtractor、EntityUpdater 等）内部自行管理向量索引。

**影响**：无。接口比计划更简洁是好事。

### 6. 旧 entity 实例变量被移除

**位置**：`agent/agent.py` `__init__`

**现状**：`self.fact_extractor`、`self.entity_updater`、`self.character_detector`、`self.lore_extractor`、`self.lore_detector` 已从 `__init__` 中移除。这些功能现由 `memory/update.py` 的 `update_from_scene()` 内部延迟导入并创建。

**影响**：如果外部代码直接访问 `agent.fact_extractor` 等属性，会报 `AttributeError`。外部调用应改为使用 `update_from_scene()`。

---

## 悬空代码

### 7. `_verify_beat_execution()` 未被调用

**位置**：`agent/agent.py` 约 737 行

**现状**：此方法用 LLM 验证节拍是否完成，但 tick 循环中的 `_verify_beat()` 使用向量相似度（`vector.compute_semantic_similarity`）代替。`_verify_beat_execution` 已不被任何代码调用。

**建议**：保留或删除均可。如保留，可考虑作为 `_verify_beat` 的低置信度回退方案。

### 8. `_first_tick()` 中有内联字符设置逻辑重复

**位置**：`agent/agent.py` _first_tick Phase 1 末尾

**现状**：`_first_tick` 中有一段与 `_set_active_char()` 功能重复的内联代码（循环遍历 `entity_results["actions_executed"]` 找 `character.generate`）。虽然行为一致，但重复维护。

**建议**：可改为调用 `_set_active_char(entity_results, plan)`，但非必须。

---

## 设计遗留问题

### 9. PlotBeat 双重定义未解决

**位置**：`memory/entities.py` 和 `plot/entities.py`

**现状**：两份 PlotBeat 定义仍然存在。计划中的 Phase 0.1 未执行。

**影响**：当前不会产生运行时错误，因为 import 路径不同。但长期维护易混淆。

**建议**：在下次大版本中合并：
1. 给 `memory/entities.py` 中的 `PlotOutline` 类加上 `to_json()`、`from_json()`、`now_iso()` 方法
2. 将 `plot/entities.py` 改为从 memory 层 re-export

### 10. 缓存失效——`resolve_open_loop` vs `add_open_loop`

**位置**：`memory/manager.py`

**现状**：`add_open_loop()` 和 `resolve_open_loop()` 都会调用 `invalidate_cache()`，但 `resolve_open_loop` 是通过 `save_open_loop` 间接触发（`save_open_loop` 中已加 `invalidate_cache()`）。一致性无问题，但调用链不直观。

**影响**：无功能性影响。

### 11. 测试无法运行

**现状**：`tests/` 目录下 5 个测试文件均依赖 `pytest`，但环境未安装。所有测试全部因 `ModuleNotFoundError: No module named 'pytest'` 失败。

**验证状态**：仅能验证 `import` 级正确性（已通过）。无法运行单元测试验证逻辑正确性。

**解决**：安装 pytest 后运行：

```bash
pip install pytest
cd F:\InkForge
python -m pytest tests/ -v
```
