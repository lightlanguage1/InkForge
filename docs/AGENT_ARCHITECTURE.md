# InkForge 智能体完整架构文档

> 生成时间：2026-05-30 | 基于 beta 分支 cb06b07

---

## 目录

1. [总览：一次 tick 的完整生命周期](#1-总览一次-tick-的完整生命周期)
2. [记忆存储架构](#2-记忆存储架构)
3. [上下文构建：Planner](#3-上下文构建planner)
4. [上下文构建：Writer](#4-上下文构建writer)
5. [场景生成与评估](#5-场景生成与评估)
6. [场景提交与保存](#6-场景提交与保存)
7. [场景后处理：记忆更新](#7-场景后处理记忆更新)
8. [关系网判定与维护](#8-关系网判定与维护)
9. [支线/主线追踪](#9-支线主线追踪)
10. [故事目标自动浮现](#10-故事目标自动浮现)
11. [Skill 笔风系统](#11-skill-笔风系统)
12. [已知缺陷](#12-已知缺陷)

---

## 1. 总览：一次 tick 的完整生命周期

```
                    ┌──────────────────────────────────────────────┐
                    │              tick() 入口                       │
                    │   tick=0 → _first_tick()                      │
                    │   tick≥1 → _normal_tick()                     │
                    └──────────────────┬───────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                    _normal_tick()                          │
         │                                                            │
         │  ┌─────────────────────────────────────────────────────┐  │
         │  │ Phase 1: PLAN                                         │  │
         │  │                                                       │  │
         │  │ _resolve_plot_beat(tick)                              │  │
         │  │   → plot_outline.json → 取出下一个 pending beat       │  │
         │  │   → 如果不足则 LLM 自动生成新节拍                      │  │
         │  │                                                       │  │
         │  │ build_planner_context(state, beat, notes, feedback)   │  │
         │  │   → 构造 23+ 字段的上下文字典                          │  │
         │  │   → format_planner_prompt() → 拼接成完整 LLM prompt   │  │
         │  │                                                       │  │
         │  │ _generate_plan(context)                               │  │
         │  │   → LLM 生成 JSON plan（rationale/intention/key_change│  │
         │  │     /actions/beat_target/threads_addressed...）       │  │
         │  │                                                       │  │
         │  │ validate_plan + _enforce_beat_target + _enforce_pacing│  │
         │  │ + _enforce_threads                                    │  │
         │  │   → 校验必填字段 + 节拍对齐 + 节奏不重复 + 支线强制    │  │
         │  │   → 失败则带 rejection_feedback 重试（最多3次）        │  │
         │  │                                                       │  │
         │  │ executor.execute_plan(plan, tick)                     │  │
         │  │   → 执行 tools: memory.search / character.generate    │  │
         │  │     / location.generate / relationship.create 等       │  │
         │  │   → 返回 {actions_executed, errors, success}          │  │
         │  │                                                       │  │
         │  │ plan_manager.save_plan(tick, plan, results, context)  │  │
         │  │   → plans/plan_NNN.json                               │  │
         │  └─────────────────────────────────────────────────────┘  │
         │                                                            │
         │  ┌─────────────────────────────────────────────────────┐  │
         │  │ Phase 2: WRITE + EVALUATE (retry loop, max 3 tries)   │  │
         │  │                                                       │  │
         │  │ build_writer_context(plan, exec_results, state,       │  │
         │  │                      eval_feedback, notes)            │  │
         │  │   → 构造 20+ 字段的上下文字典                          │  │
         │  │   → format_writer_prompt() → 拼接成完整 LLM prompt   │  │
         │  │                                                       │  │
         │  │ writer.write_scene(writer_context)                    │  │
         │  │   → LLM 生成场景正文（中文散文）                       │  │
         │  │   → 返回 {text, word_count, title}                    │  │
         │  │                                                       │  │
         │  │ evaluator.evaluate_scene(text, writer_context)        │  │
         │  │   → POV 检查（全知叙述/视角跳跃）                      │  │
         │  │   → 连续性检查（角色状态与行动矛盾）                    │  │
         │  │   → Logic QA（时间/年龄/逻辑谬误，每5幕一次）           │  │
         │  │   → 返回 {passed, issues, warnings, checks}           │  │
         │  │                                                       │  │
         │  │   passed=false → 带 eval_feedback 重试                │  │
         │  └─────────────────────────────────────────────────────┘  │
         │                                                            │
         │  ┌─────────────────────────────────────────────────────┐  │
         │  │ Phase 3: COMMIT                                        │  │
         │  │                                                       │  │
         │  │ tension_evaluator.evaluate_tension(text, context)     │  │
         │  │   → 关键词密度 + 句型分析 + 情感强度 + 开放线索贡献     │  │
         │  │   → 返回 {tension_level: 0-10, category: calm/...}   │  │
         │  │                                                       │  │
         │  │ committer.commit_scene(scene_data, tick, plan)        │  │
         │  │   → 保存 scenes/scene_NNN.md                          │  │
         │  │   → LLM 生成摘要（5条要点）                             │  │
         │  │   → 创建 Scene 实体 → 保存 metadata + 向量索引         │  │
         │  └─────────────────────────────────────────────────────┘  │
         │                                                            │
         │  ┌─────────────────────────────────────────────────────┐  │
         │  │ Phase 4: POST-COMMIT                                   │  │
         │  │                                                       │  │
         │  │ _save_qa(tick, eval_result, plan) → qa/scene_NNN.json │  │
         │  │ _verify_beat(scene_id, plan, beat, scene_data)         │  │
         │  │   → 语义相似度比对 + 标记 beat 完成                      │  │
         │  │ _save_tension(scene_id, tension) → Sxxx.json metadata  │  │
         │  │                                                       │  │
         │  │ _update_memory(text, scene_id, tick)                   │  │
         │  │   → update_from_scene():                               │  │
         │  │     ├─ FactExtractor → 提取事实（角色/地点/关系/线索）  │  │
         │  │     ├─ EntityUpdater → 写入角色/关系/open_loops/json   │  │
         │  │     ├─ LoreExtractor → 提取世界观 → 写入+向量索引       │  │
         │  │     └─ CharacterDetector → 发现新角色名                 │  │
         │  │                                                       │  │
         │  │ _check_goal_promotion(tick)                            │  │
         │  │   → 10-15幕窗口内，主角相关loop≥5次提及 → 浮现为故事目标│  │
         │  │                                                       │  │
         │  │ _maybe_audit_threads(tick)                             │  │
         │  │   → 每5幕，LLM审计 → 发现新支线 → 创建 pending thread  │  │
         │  └─────────────────────────────────────────────────────┘  │
         │                                                            │
         │  current_tick += 1 → _save_state() → 返回 result           │
         └────────────────────────────────────────────────────────────┘
```

---

## 2. 记忆存储架构

### 2.1 文件系统布局

```
work/users/{user_id}/novels/{project_name}_{uuid}/
├── state.json                 ← 全局状态
├── plot_outline.json          ← 情节节拍列表
├── scenes/
│   ├── scene_000.md           ← 正文（markdown）
│   └── scene_001.md
├── memory/
│   ├── characters/
│   │   ├── C000.json          ← 角色实体（每人一个文件）
│   │   └── C001.json
│   ├── locations/
│   │   ├── L000.json          ← 地点实体
│   │   └── L001.json
│   ├── scenes/
│   │   ├── S000.json          ← 场景元数据
│   │   └── S001.json
│   ├── factions/
│   │   └── F000.json          ← 势力/组织
│   ├── story_threads/
│   │   └── ST000.json         ← 支线（主线/子线/角色弧线）
│   ├── relationships.json     ← 全部关系图（聚合文件）
│   ├── open_loops.json        ← 全部开放线索（聚合文件）
│   ├── lore.json              ← 全部世界观条目（聚合文件）
│   ├── qa/
│   │   └── scene_NNN.json     ← 各场景评估结果
│   ├── index/                 ← ChromaDB 向量数据库
│   │   └── chroma.sqlite3
│   └── counters.json          ← ID 计数器
├── plans/
│   └── plan_NNN.json          ← 每幕的计划 JSON
└── errors/
    └── error_NNN.json + .log  ← 错误日志
```

### 2.2 关键实体的数据结构

**Character** (`memory/entities.py:261`)
```
id, first_name, family_name, title, nicknames, role,
physical_traits (age, appearance, distinctive_features),
personality (core_traits, fears, desires, flaws),
relationships[], current_state (location_id, emotional_state,
  physical_state, emotion{dominant,valence,arousal,intensity},
  inventory, goals, beliefs),
backstory, history[{tick, scene_id, summary, changes}],
immediate_goals, arc_goal, story_goal, goal_progress,
status (active/sidelined/departed/deceased/returning),
last_scene_tick, appearance_ticks, off_screen_note,
pov_count
```

**Scene** (`memory/entities.py:434`)
```
id, tick, title, pov_character_id, location_id,
markdown_file, word_count, summary[], characters_present[],
key_events[], entities_created[], entities_updated[],
open_loops_created[], open_loops_resolved[],
tension_level, tension_category
```

**OpenLoop** (`memory/entities.py:475`)
```
id, created_in_scene, status (open/resolved/abandoned),
category, description, importance, related_characters[],
related_locations[], notes, resolved_in_scene,
scenes_mentioned, last_mentioned_tick, is_story_goal
```

**RelationshipGraph** (`memory/entities.py:512`)
```
id, character_a, character_b, relationship_type, status,
perspective_a{description, emotion}, perspective_b{...},
intensity (0-10), history[{tick, scene_id, change, summary}]
```

**StoryThread** (`memory/entities.py:703`)
```
id, name, description, category (main/subplot/relationship/
  mystery/character_arc), status (pending/active/dormant/
  resolved/rejected), importance, introduced_tick,
last_advanced_tick, advancement_history[],
related_characters[], related_scenes[], related_loops[]
```

**PlotBeat** (`memory/entities.py:608`)
```
id, description, characters_involved[], location,
plot_threads[], tension_target, prerequisites[],
status (pending/in_progress/completed/skipped),
executed_in_scene, execution_notes, verification_score,
verification_method, advances_character_arcs[],
resolves_loops[], creates_loops[]
```

---

## 3. 上下文构建：Planner

### 3.1 数据来源

`agent/context.py` → `build_planner_context()` 返回 23 个字段：

| 字段 | 数据来源 | 数量限制 |
|------|---------|---------|
| `story_foundation_summary` | `state.json` → `story_foundation` | 5 行 |
| `novel_name` | `state.json` | — |
| `current_tick` | `state.json` | — |
| `active_character_id/name` | `memory/characters/{id}.json` | 1 个（主角） |
| `active_character_details` | 角色完整档案（名字/角色/描述/目标/情绪/位置） | 1 个 |
| `overall_summary` | 全部场景摘要（每幕取第一条），可关闭 | 所有场景 |
| `recent_scenes_summary` | 最近 `recent_scenes_count` 个场景摘要 | **3 幕** |
| `open_loops_list` | `open_loops.json` → 按 relevance_score 排序 | **top 10** |
| `tension_history` | 最近 5 场景的 `tension_level/category` | 5 幕 |
| `qa_feedback` | `qa/scene_NNN.json` → 仅 `change=yes/no` 一行 | 3 条 |
| `next_plot_beat` | `plot_outline.json` → 下一个 pending beat | 1 条 |
| `beat_enforcement_instructions` | 配置决定 mode（soft_hint/guided/strict） | — |
| `character_relationships` | `relationships.json` → 过滤出主角的关系 | 全部主角关系 |
| `pov_candidates` | role=protagonist/supporting 的角色 | 全部 |
| `pov_history` | 最近 8 幕的 POV 角色 | **8 幕** |
| `factions_summary` | `memory/factions/*.json` → 按 importance 排序 | **top 8** |
| `relevant_lore` | ChromaDB 语义搜索（用上一幕 summary 查询） | **top 5** |
| `existing_characters_summary` | status=active/returning + 1 个 sidelined | 活跃+1 |
| `absent_characters` | last_scene_tick 距当前 ≥5 幕的角色 | 全部缺席 |
| `thread_dashboard` | `story_threads/*.json` → ThreadManager.format_dashboard | 全部活跃 |
| `available_tools_description` | ToolRegistry → 全部注册工具的参数说明 | 全部工具 |
| `writer_notes` | 用户输入或 `generation.writer_notes` 配置 | — |
| `plan_rejection_feedback` | 仅重试时有值 | — |

### 3.2 prompt 模板

`data/templates/planner_prompt.md` — 使用 `{field_name}` 插值上述所有字段。

**输出格式**：LLM 必须输出 JSON：
```json
{
  "rationale": "...",
  "scene_intention": "...",
  "key_change": "...",
  "progress_milestone": "...",
  "progress_step": "setup|complication|reversal|revelation|decision|resolution",
  "scene_mode": "...",
  "palette_shift": "...",
  "transition_path": "...",
  "dialogue_targets": "...",
  "beat_target": {"beat_id": "PB003", "strategy": "direct|setup|followup|skip"},
  "loops_addressed": ["OL4"],
  "threads_addressed": ["ST001"],
  "pov_character": "C000",
  "target_location": "L001",
  "actions": [{"tool": "memory.search", "args": {...}, "reason": "..."}],
  "expected_outcomes": ["...", "..."],
  "metadata": {"scene_length": "brief|short|long|extended"}
}
```

### 3.3 Planner 的 Token 估算

总计约 **5000-12000 字符 ≈ 2000-5000 tokens**（中文字符约 1.5-2 tokens/字）

---

## 4. 上下文构建：Writer

### 4.1 数据来源

`agent/writer_context.py` → `build_writer_context()` 返回 20 个字段：

| 字段 | 数据来源 | 说明 |
|------|---------|------|
| `novel_name` | `state.json` | 小说标题 |
| `current_tick` | `state.json` | 当前幕数 |
| **`recent_context`** | **三部分组合** | |
| └─ transition_tail | `scenes/scene_{N-1}.md` | 上一幕最后 ~500 字符 |
| └─ recent summaries | `memory/scenes/Sxxx.json` | 最近 5 幕的摘要 |
| └─ state snapshot | 实时从 memory 构建 | 全部角色+关系+地点+线索 |
| `scene_intention` | plan | Planner 的场景意图 |
| `key_change` | plan | 本幕必须完成的改变 |
| `progress_milestone` | plan | 进展里程碑 |
| `plot_beat_section` | ⚠️ `_format_plot_beat_section(plan)` | 查 `plan.get("plot_beat")` — **永远为空！** |
| `scene_mode` | plan | 叙事模式 |
| `palette_shift` | plan | 调色板转换 |
| `transition_path` | plan | 过渡路径 |
| `dialogue_targets` | plan | 对话目标 |
| `skill_context` | `state.json → active_skills` → `SKILL.yaml` | 笔风参考 |
| `reference_context` | ReferenceIndexer 搜索 | 外部参考文本 |
| `world_rules` | `lore.json` → 按 importance 过滤 | **top 5** |
| `writer_notes` | 用户输入或 config | 场景方向指导 |
| `pov_character_details` | `memory/characters/{id}.json` | POV 角色完整档案 |
| `location_details` | `memory/locations/{id}.json` | 场景地点详情 |
| `eval_feedback` | 仅重试时有值 | 上一版的修正意见 |
| `scene_length_guidance` | config | 字数指导 |

### 4.2 ⚠️ Plot Beat 断裂

`writer_context.py:436` — `_format_plot_beat_section(plan)` 查找 `plan.get("plot_beat")`。  
但 Planner 输出的是 `plan.beat_target = {beat_id: "PB003", strategy: "direct"}`。  
**两套键名不匹配 → `plot_beat_section` 永远为空字符串 → Writer 不知道要执行哪个节拍。**

### 4.3 ⚠️ Writer 缺少的关键信息

| 缺失项 | 说明 |
|--------|------|
| `story_foundation_summary` | Writer 不知道类型/前提/主角/基调 |
| `thread_dashboard` | Writer 不知道当前活跃支线 |
| `story_goal` | Writer 不知道浮现的故事目标 |
| `next_plot_beat` | Writer 不知道要执行的节拍（L1 断裂） |

### 4.4 Writer 的 Token 估算

总计约 **5000-13000 字符 ≈ 2500-6000 tokens**

---

## 5. 场景生成与评估

### 5.1 Writer (`agent/writer.py`)

```
write_scene(writer_context)
  ├─ _format_writer_prompt(context)
  │   → 加载 writer_prompt.md 模板 → str.format(**context)
  ├─ _call_llm(prompt, max_tokens, llm)
  │   ├─ anthropic → chat(system=SYSTEM_WRITER, user=prompt)
  │   └─ 其他 → generate(prompt)
  ├─ _detect_refusal(text)
  │   → 检查前 400 字符有无拒绝关键词（英文+中文）
  │   → 触发 → 切换到 fallback_llm 重试
  ├─ _parse_scene_response(text)
  │   ├─ 跳过元推理头部（META_MARKERS 匹配）
  │   ├─ _extract_title() → 取首行或 scene_intention 截断
  │   ├─ _strip_llm_header() → 移除 # Title / *Metadata* / ---
  │   └─ 计算字数（中文按字符，英文按空格分词）
  └─ 返回 {text, word_count, title}
```

### 5.2 Evaluator (`agent/evaluator.py`)

```
evaluate_scene(text, context)
  ├─ _check_pov()
  │   ├─ 快速路径：无关键词 → 直接通过（tick>2 跳过）
  │   └─ LLM 路径：全场景扫描 → 检测全知叙述/视角跳跃
  │
  ├─ _check_continuity()
  │   ├─ 关键词："wounded"+"leaped" 等
  │   └─ 触发 LLM 确认是否真矛盾
  │
  ├─ _check_logic()  ⚠️ 仅每 5 幕一次
  │   ├─ LLM 扫描：时间矛盾、年龄冲突、逻辑谬误
  │   └─ severity=error → issues, severity=warning → warnings
  │
  ├─ _compute_qa_metrics()
  │   ├─ 关键变化强度、里程碑清晰度、转场清晰度
  │   ├─ 模式多样性、新颖度、对话目标达成率
  │   └─ beat_hint_alignment（节拍对齐度）
  │
  └─ passed = all(checks) and len(issues) == 0
     → passed=false → Writer 重试（max 3 次，带修正反馈）
```

### 5.3 TensionEvaluator (`agent/tension_evaluator.py`)

```
evaluate_tension(text, context)
  ├─ _analyze_keywords()    (权重 0.4) → 高/中/低紧张度关键词密度
  ├─ _analyze_structure()   (权重 0.2) → 句子长度分布
  ├─ _analyze_emotion()     (权重 0.3) → 标点+情感动词
  └─ _analyze_loops()       (权重 0.1) → 创建 vs 解决线索
  → {tension_level: 0-10, tension_category: calm/rising/high/climactic}
```

---

## 6. 场景提交与保存

### 6.1 SceneCommitter (`agent/scene_committer.py`)

```
commit_scene(scene_data, tick, plan)
  ├─ generate_id("scene") → Sxxx
  ├─ 保存 scenes/scene_NNN.md
  │   → "# 第N章 {title}\n\n{text}\n"
  ├─ summarizer.summarize_scene(text, max_bullets=5)
  │   → LLM 生成 5 条要点摘要
  ├─ _extract_characters(plan)
  │   → 仅取 plan.pov_character → ⚠️ 只有 POV 一人
  ├─ 创建 Scene 实体 → memory.save_scene()
  └─ vector.index_scene()
```

### 6.2 PlanManager (`agent/plan_manager.py`)

```
save_plan(tick, plan, execution_results, context)
  → plans/plan_NNN.json
  → {tick, timestamp, plan, execution{actions_executed,errors}, context_used}

save_error(tick, error, plan, execution_results)
  → errors/error_NNN.json + errors/error_NNN.log
```

---

## 7. 场景后处理：记忆更新

### 7.1 流程

`agent.py:463` → `_update_memory()` → `memory/update.py:update_from_scene()`

```
update_from_scene(text, scene_id, tick, state, memory, llm, config)
  │
  ├─ Phase 1: _extract_and_update()
  │   ├─ FactExtractor.extract_facts(text, context)
  │   │   → LLM 提取结构化事实 JSON：
  │   │     {
  │   │       "character_updates": [{character_id, pov_name?, changes: {field: value,...}}],
  │   │       "location_updates": [{location_id, changes: {field: value,...}}],
  │   │       "open_loops_created": [{category, description, importance, related_characters}],
  │   │       "open_loops_resolved": [{loop_id, resolution_summary}],
  │   │       "relationship_changes": [{character_a, character_b, changes: {type,status,intensity,...}}]
  │   │     }
  │   │
  │   └─ EntityUpdater.apply_updates(facts, tick, scene_id, state)
  │       ├─ _update_character() → 更新角色状态/目标/情绪/位置/历史
  │       ├─ _update_location() → 更新地点特征/状态
  │       ├─ _create_open_loop() → 创建新 OpenLoop
  │       ├─ _resolve_open_loop() → 标记已解决
  │       ├─ _update_relationship() → 创建/更新关系（RelationshipGraph）
  │       └─ _track_appearances() → 更新角色 last_scene_tick + appearance_ticks
  │                              → departed → returning 自动转换
  │
  ├─ Phase 2: _extract_lore()
  │   ├─ LoreExtractor.extract_lore(text, context, tick)
  │   │   → LLM 提取世界观规则
  │   │   → 返回 [{type, category, content, importance, tags}]
  │   ├─ 创建 Lore 实体 → memory.save_lore() → lore.json
  │   ├─ vector.index_lore() → ChromaDB
  │   └─ LoreContradictionDetector.update_contradictions()
  │       → 对新 lore 搜索相似项 → 如矛盾则标记
  │
  └─ Phase 3: _detect_characters()
      ├─ CharacterDetector.find_new_characters(text)
      │   → LLM 在文本中发现未注册的中文名字
      └─ 如 auto_create_minor_characters=True → 自动创建占位角色
```

### 7.2 EntityUpdater 的详细逻辑

**角色更新** (`_update_character`):
- 位置变化 → 写入 `current_state.location_id`
- 情绪变化 → 映射到 `EmotionState`（valence/arousal/intensity 三轴）
- 目标变化 → 追加到 `current_state.goals`
- 身体状态 → 覆盖 `current_state.physical_state`
- 历史记录 → 追加 `HistoryEntry{tick, scene_id, summary, changes}`

**关系更新** (`_update_relationship`):
- 新关系 → 创建 `RelationshipGraph` → `memory.add_relationship()`
- 已有关系 → 更新 type/status/intensity/perspectives → 追加 `RelationshipHistoryEntry`

**Open Loop 追踪**:
- 创建 → OpenLoop(status=open, category, description, importance, created_in_scene)
- 解决 → status=resolved, resolved_in_scene=scene_id

---

## 8. 关系网判定与维护

### 8.1 写入路径

```
场景文本 → FactExtractor → LLM 提取 relationship_changes
  → [{character_a: "C000", character_b: "C001",
      changes: {relationship_type: "师徒", status: "active", intensity: 7}}]
  → EntityUpdater._update_relationship()
    ├─ 验证两个角色都存在
    ├─ 查 relationships.json 是否已有关系
    ├─ 新关系 → memory.add_relationship() → 追加到聚合数组
    ├─ 已有 → memory.update_relationship() → 原地修改
    └─ 追加 RelationshipHistoryEntry{tick, scene_id, change, summary}
```

也可以从 Planner 直接调用 tool：
- `relationship.create(char_a, char_b, type, status, ...)` → `memory_tools.py:RelationshipCreateTool`
- `relationship.update(id, changes)` → `memory_tools.py:RelationshipUpdateTool`

### 8.2 读取路径

**Planner 上下文**：`context.py → _format_relationships(active_char_id)`
- `memory.get_character_relationships(char_id)` → `load_relationships()` → 过滤 `involves_character(id)`
- ⚠️ `load_relationships()` **无缓存**，每次磁盘 I/O

**Writer 上下文**：`writer_context.py → _build_state_snapshot()`
- 遍历全部角色 → `get_character_relationships(cid)`
- 每个角色显示 top 5 条关系

---

## 9. 支线/主线追踪

### 9.1 完整生命周期

```
【创建】3 个入口：
  1. Planner 调用 thread.create 工具 → MemoryTools → ThreadManager.create_thread()
  2. LLM 审计 → thread_manager.run_audit(tick)
     → 构造 prompt（最近 10 幕摘要 + 已有支线列表）
     → LLM 提取 → 创建 ≤3 个 pending StoryThread
  3. API → POST /api/v1/project/{id}/threads

【状态流转】:
  pending → (confirm) → active → (advance) → ... → resolved
  pending → (reject)  → rejected

【注入 Planner】:
  每 tick 从 context.py → _format_thread_dashboard(current_tick)
  → ThreadManager.format_dashboard(tick)
    → 列出 active 支线，计算停滞章数
    → 标记：正常(▂) / 需推进(▄, >4章) / 必须(█, >8章)
    → 如存在必须推进的支线 → "叙事债务"警告

【强制推进】:
  agent.py → _enforce_threads(plan, tick)
  → get_forced_ids(tick) → 返回停滞>8章的支线 ID
  → 检查 plan.threads_addressed 是否包含这些 ID
  → ⚠️ 只检查 JSON 字段，不验证场景内容

【⚠️ 不进 Writer】:
  thread 信息只给 Planner，Writer 完全不知道活跃支线
```

### 9.2 支线推进标记——不工作

`last_advanced_tick` 应该每次支线相关场景后更新，但当前代码中：
- `advance_thread()` 方法存在但**从未被自动调用**
- 没有任何代码在 commit_scene 后更新 thread 的 `last_advanced_tick`
- 导致所有支线都在"累积停滞"，即使已经写了好几幕

---

## 10. 故事目标自动浮现

`agent.py:848` → `_check_goal_promotion(tick)`

```
触发条件：tick ∈ [10, 15]
  1. 检查 state.story_goals.primary 是否已存在
  2. 获取主角 ID
  3. 遍历 open_loops → 过滤 related_characters 包含主角的
  4. 找 scenes_mentioned ≥ 5 的 loop
  5. 设为 story_goal → 写入 state.json

⚠️ scenes_mentioned 永远不会达到 5：
  创建时 scenes_mentioned=1
  FactExtractor 的提取模板中没有 "increment scenes_mentioned" 的指令
  EntityUpdater 没有递增逻辑
  → 故事目标永远不会自动浮现
```

---

## 11. Skill 笔风系统

### 11.1 导入

```
POST /api/v1/skills/import {file_path: "小说.txt"}
  → SkillImporter.import_novel(file_path)
    ├─ extract_chapters() → 分章
    ├─ analyze_style() → StyleProfile（句长/对话比/词汇丰富度）
    ├─ 分层抽样 → 批次 LLM 提取
    │   ├─ NarrativePattern[]（张力弧/对话模式/转场方式/描写层次…）
    │   ├─ CharacterArchetype[]（角色原型）
    │   └─ tags[]（风格标签）
    └─ SkillStore.save_skill() → data/skills/{slug}/SKILL.yaml
```

### 11.2 激活

```
POST /api/v1/project/{id}/skills/apply {skill_ids: ["381bbebb"], mode: "reference"}
  → SkillInjector.inject(skills, mode)
  → 写入 state.json: {active_skills: [{id, name, mode}]}
  → ⚠️ 只存引用，不存完整数据
```

### 11.3 渲染到 Prompt

```
writer_context.py → _build_skill_context(state, store_path)
  → 从 SKILL.yaml 按 ID 加载完整数据
  → 格式化为：
    ## 写作风格要求
    标签: 史诗叙事, 神话重构...
    均句长: 29.5字 (波动: 19.1)
    对话占比: 0.534
    均段长: 84字
    叙事技法:
    - [tension_arc] 角色从绝望低谷升至决断高潮... (17%)
    - [dialogue_pattern] 通过对话揭示冲突... (17%)
  → {skill_context} → writer_prompt.md

⚠️ 不进 Planner — 只有 Writer 收到笔风参考
```

---

## 12. 已知缺陷

### 🔴 P0 — 阻断性

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | **Plot Beat 到 Writer 断裂** | `writer_context.py:436` 查 `plan.plot_beat`，但 Planner 输出的是 `plan.beat_target` | Writer 不知道要执行哪个节拍 |
| 2 | **Writer 缺少故事设定** | `writer_context.py:86-118` 没有 `story_foundation_summary` | 场景可能和基础设定矛盾 |
| 3 | **open_loop scenes_mentioned 不递增** | `entity_updater.py` 没有递增逻辑 | 故事目标永远不会浮现 |

### 🟡 P1 — 严重影响

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 4 | **QA 反馈不穿透** | `context.py:181` 只给 Planner "change=yes/no" 一行 | Planner 不知道上一幕的具体错误 |
| 5 | **Scene 角色列表只有 POV** | `scene_committer.py:119` 只取 `plan.pov_character` | 支线/关系判定缺少角色 |
| 6 | **Thread 信息不进 Writer** | `writer_context.py` 没有 thread_context 字段 | Writer 不知道要写支线内容 |
| 7 | **支线 last_advanced_tick 不更新** | `agent.py` 和 `memory/update.py` 都没有调用 `advance_thread()` | 支线追踪形同虚设 |

### 🟠 P2 — 中度影响

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 8 | **Beat 强制默认关闭** | `agent.py:261` beat_mode=soft_hint → 直接 return | 节拍不强制对齐 |
| 9 | **Thread 验证只查 JSON 字段** | `agent.py:324` 只查 `threads_addressed` 列表 | 支线假推进 |
| 10 | **上下文窗口仅 3-5 幕** | `context.py:159` + `writer_context.py:74` | 长故事一致性差 |
| 11 | **Story goals 不进任何上下文** | `agent.py:865` 写入了但无人读取格式化 | Llama 不知道故事目标 |

### 🟢 P3 — 低影响

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 12 | **Logic QA 每 5 幕一次** | `evaluator.py:258` `tick % 5 != 0` → 跳过 | 80% 的幕不检测逻辑谬误 |
| 13 | **load_relationships 无缓存** | `memory/manager.py:638` 不走 `_cache_get` | 每个 tick 重复磁盘 I/O |
| 14 | **POV 检查 2 幕后就跳过** | `evaluator.py:156` `tick>2` → 快速路径通过 | 中后期 POV 违规不检测 |
| 15 | **Skill 不进 Planner** | 只有 writer_context 注入 | Planner 不知道要规划什么风格 |
