# StoryDaemon 架构设计文档

> 基于代码实际探索，非旧文档推断。日期：2026-05-19。

---

## 一、项目概述

StoryDaemon 是一个 **LLM 驱动的中文长篇小说涌现式生成系统**。核心理念：不预设大纲，让叙事结构在逐幕（Tick）迭代中自行涌现。

**技术栈：** Python 3.11+, Typer CLI, ChromaDB 向量存储, JSON 文件持久化

**关键数字：**
- 5 种 LLM 后端（codex / api / gemini-cli / claude-cli / ollama）
- 每 Tick 4 阶段（Plan → Write+Eval → Commit → Update）
- 10 个注册工具（角色/地点/势力生成、记忆搜索、关系 CRUD）
- 3 层评估（POV 检测、连续性检查、QA 指标）

---

## 二、顶层目录结构

```
novel_agent/
├── cli/                 CLI 入口 + 17 个子命令
│   ├── main.py          所有命令注册 (new/tick/run/status/plot/skill/...)
│   ├── project.py       项目创建/查找/状态读写
│   ├── foundation.py    故事基础设定交互向导
│   └── commands/        各命令实现 (plot/skill/checkpoint/compile/...)
├── agent/               核心引擎 (Tick 循环 + 写作 + 评估)
│   ├── agent.py         StoryAgent — 主编排器
│   ├── context.py       ContextBuilder — Planner 上下文构建
│   ├── writer_context.py WriterContextBuilder — Writer 上下文构建
│   ├── writer.py        SceneWriter — 场景写作 + 拒止回落
│   ├── evaluator.py     SceneEvaluator — POV/连续性 + QA 指标
│   ├── prompts.py       System Prompt + 模板加载
│   ├── schemas.py       Plan JSON 校验
│   ├── runtime.py       PlanExecutor — 工具调用执行
│   ├── plan_manager.py  计划持久化 (plans/ 目录)
│   ├── scene_committer.py 场景提交 + Q&A 保存
│   ├── tension_evaluator.py 张力评估 0-10
│   ├── character_detector.py 从正文自动检测新角色
│   ├── fact_extractor.py     从正文提取事实
│   ├── entity_updater.py     事实 → 实体更新
│   ├── lore_extractor.py     世界观规则提取
│   └── lore_contradiction_detector.py 设定冲突检测
├── memory/              持久化与向量检索
│   ├── manager.py       MemoryManager — JSON 文件 CRUD
│   ├── entities.py      数据类 (Character/Location/Scene/OpenLoop/Lore/Faction/...)
│   ├── vector_store.py  ChromaDB 向量索引
│   ├── update.py        场景后处理总入口
│   ├── summarizer.py    场景摘要生成
│   └── checkpoint.py    项目存档 (快照 + 回滚)
├── plot/                情节节拍管理
│   └── manager.py       PlotOutlineManager — beat 生成/持久化/状态
├── tools/               LLM 后端 + 工具注册
│   ├── llm_interface.py     后端初始化 + 全局接口
│   ├── multi_provider_llm.py 多供应商 API (OpenAI/Gemini/Claude/DeepSeek/Ollama/本地)
│   ├── provider.py          LLMProvider — generate/chat 统一封装
│   ├── router.py            ModelRouter — 按任务路由模型
│   ├── registry.py          ToolRegistry — 工具注册表
│   ├── memory_tools.py      角色/地点/势力/关系生成工具
│   ├── name_generator.py    随机中文名生成器
│   ├── codex_interface.py   Codex CLI 后端
│   ├── gemini_cli_interface.py Gemini CLI 后端
│   ├── claude_cli_interface.py Claude Code CLI 后端
│   ├── ollama_stream.py     Ollama 流式输出
│   └── llm_pool.py          LLM 连接池 (Engine 用)
├── skill/               写作技能导入/注入
│   ├── importer.py      小说 → SKILL.yaml (分层采样 + 角色去重)
│   ├── injector.py      SKILL → Writer/Planner 上下文注入
│   ├── models.py        Skill/StyleProfile/NarrativePattern/CharacterArchetype 数据类
│   └── store.py         SkillStore — YAML 持久化
├── engine/              常驻进程引擎
│   ├── core.py          EngineCore — LLMPool + ProjectManager + SkillStore
│   └── project_manager.py 项目管理
├── configs/             配置与常量
│   ├── config.py        全局配置加载
│   ├── constants.py     所有魔法数字 + 默认值
│   └── api_keys.py      API Key 统一解析
├── reference/           外部参考小说索引
│   └── indexer.py       ReferenceIndexer — 分块 + 向量搜索
├── api/                 REST API 服务
│   ├── __init__.py
│   └── server.py        FastAPI/Flask 服务端
├── data/
│   ├── names/           中文姓名库 (JSON)
│   ├── templates/       Prompt 模板 (Markdown)
│   └── skills/          已导入的写作技能 (YAML)
└── utils/               工具函数
    └── file_ops.py
```

---

## 三、LLM 后端体系

### 3.1 五种后端 (`tools/llm_interface.py`)

| 后端标识 | 实现类 | 实际调用方式 |
|----------|--------|-------------|
| `codex` | `CodexInterface` | 调用本地 `codex` 二进制 (CLI 子进程) |
| `api` | `MultiProviderInterface` | 通过 `multi_provider_llm.py` 模型注册表路由到各供应商 HTTP API |
| `gemini-cli` | `GeminiCliInterface` | 调用本地 `gemini` 二进制 |
| `claude-cli` | `ClaudeCliInterface` | 调用本地 `claude` 二进制 |
| `ollama` | `OllamaInterface` | 通过 Ollama 原生 `/api/chat` HTTP 端点 |

### 3.2 MultiProviderInterface 模型注册表 (`tools/multi_provider_llm.py`)

`_model_config` 字典将模型名映射到具体调用函数：

```
gpt-5 / gpt-5.1 / gpt-5-mini    → OpenAI Chat API
gemini-2.5-pro                   → Google Gemini API
claude-4.5                       → Anthropic Messages API
deepseek-chat / deepseek-reasoner → DeepSeek API (OpenAI 兼容)
local-llama                      → 本地 llama-server (OpenAI 兼容，默认 http://127.0.0.1:8080/v1)
huihui_ai/qwen3-abliterated      → Ollama 原生 API
```

**设计逻辑：** 模型名直接决定供应商路由，无需额外配置。用户改一个 model 字符串即可切换供应商。新增供应商只需在 `_model_config` 加一行 lambda。

### 3.3 LLMProvider — generate/chat 统一封装 (`tools/provider.py`)

```
LLMProvider
├── generate(prompt, max_tokens)   纯文本 prompt（兼容旧接口）
├── chat(messages, max_tokens)     消息列表模式
│   ├── backend_type="anthropic" → Anthropic Messages API (含 cache_control)
│   └── 其他 backend              → 拼回字符串再 generate()
```

**设计逻辑：** `generate()` 保证所有后端都有统一入口，`chat()` 为未来迁移到 Anthropic 风格的 prompt caching 预留接口。新代码（Planner/Writer）优先用 `chat()`，旧代码（Evaluator/Extractor）继续用 `generate()`。

### 3.4 ModelRouter — 按任务路由模型 (`tools/router.py`)

```python
# config.yaml 示例
router:
  enabled: true
  planner_model: qwen3:8b        # 规划用小模型
  planner_backend: ollama
  writer_model: deepseek-chat    # 写作用大模型
  writer_backend: api
  extractor_model: qwen3:8b     # 抽取用小模型
  extractor_backend: ollama
```

**设计逻辑：** 默认关闭 (`enabled: false`)，所有任务共用一个模型。开启后规划/写作/抽取走不同后端。成本优化：小模型做规划和抽取，大模型专注写作。

### 3.5 Agent 中的双模型 (`agent/agent.py:89-106`)

```python
self.llm = LLMProvider(llm_interface, backend_type)       # 主模型（Planner + Writer）
self.agent_llm = LLMProvider(agent_raw, "api")            # 辅助模型（Evaluator + Extractor）
```

- `self.llm` → 从 CLI 的 `--llm-backend` / `--llm-model` 来，或从项目 config.yaml
- `self.agent_llm` → 仅在 `router.enabled=true` 时启用，走 `extractor` 任务配置；否则等于 `self.llm`

**设计逻辑：** Evaluator 和 Extractor 是辅助任务，不需要写作级模型。如果配置了 Router，它们可以跑在小模型上节省成本。

---

## 四、CLI 层 (`cli/main.py`)

17 个命令，基于 Typer：

```
novel new          创建新项目（交互式引导 or 命令行参数）
novel tick         运行一幕（单次 story tick）
novel run          运行多幕（批量 tick + checkpoint）
novel resume       恢复最近项目
novel status       项目状态总览
novel list         列出实体（角色/地点/线索/场景/势力）
novel inspect      查看实体详情
novel goals        目标层级展示
novel lore         世界观规则浏览
novel compile      编译场景 → 完整手稿（支持 markdown/html/prose 格式）
novel plan         预览下一次 Plan 不执行
novel titles       生成书目标题建议
novel recent       最近项目列表
novel checkpoint   存档管理（create/list/restore/delete）
novel serve        启动 HTTP 服务
novel summarize    编译场景摘要

novel plot status   情节节拍状态
novel plot next     下一待执行节拍
novel plot generate 生成新节拍
novel plot clear    清除所有节拍

novel skill import  导入小说提取写作技能
novel skill list    列出已导入技能
novel skill apply   应用技能到项目
novel skill delete  删除技能
```

---

## 五、Tick 循环 — 核心引擎

### 5.1 StoryAgent (`agent/agent.py`)

主编排器，管理整个 Tick 生命周期。

**初始化：**
1. 从 `state.json` 加载项目状态
2. 建立双模型（主 + Router 辅助）
3. 实例化所有组件：Memory, Vector, ContextBuilder, PlanExecutor, Writer, Evaluator, Committer, PlotManager

**第 0 幕 (`_first_tick`) — 两阶段初始化：**

```
阶段一：实体生成
  1. ContextBuilder 收集上下文
  2. LLM 生成 Plan JSON
  3. validate_plan() 校验
  4. 仅执行 entity 类工具 (character.generate / location.generate / name.generate)
     → 不执行其他工具，确保实体先于场景存在
  5. 将真实 entity ID 写回 plan

阶段二：场景写作
  6. 执行剩余工具
  7. WriterContextBuilder → SceneWriter → SceneEvaluator（可重试）
  8. SceneCommitter 提交
  9. update_from_scene() 记忆更新
  10. VectorStore 索引
```

**第 N 幕 (`_normal_tick`) — 四阶段标准循环：**

```
Phase 1 — Plan (规划)
  ├── _resolve_plot_beat()      Plot-First 模式下获取当前节拍
  ├── ContextBuilder.build_planner_context()
  │    收集：故事基础设定 + 活跃角色/地点 + 近期摘要 + 开放线索
  │          + 张力历史 + 势力 + 世界观 + POV候选 + 缺席角色 + QA反馈
  ├── _generate_plan()          LLM 生成 JSON plan
  │    如果 backend_type="anthropic" → 走 chat() 带 cache_control
  │    否则 → generate()
  ├── validate_plan()           JSON Schema 校验
  ├── _enforce_beat_target()    Plot-First 严格模式：Plan 必须指定当前 beat
  ├── _enforce_pacing()         节奏约束：连续3幕不能相同 progress_step
  │     备选建议：revelation→decision/setup, complication→decision/resolution ...
  └── PlanExecutor.execute_plan()
        遍历 plan.actions → 调用 ToolRegistry 中对应工具

Phase 2 — Write + Evaluate (写作+评估，可重试)
  ├── WriterContextBuilder.build_writer_context()
  │    收集：POV 角色详情 + 地点详情 + 近期上下文(过渡尾+摘要+状态快照)
  │          + 工具执行结果 + 技能注入 + 参考搜索 + 节拍信息
  ├── SceneWriter.write_scene()
  │    ├── prefer_local_writer? → 主模型=本地, 回落=API
  │    │   否则 → 主模型=API, 回落=本地
  │    ├── _call_llm(prompt, max_tokens, primary)
  │    ├── _detect_refusal() → 触发了? → _call_llm(prompt, fallback)
  │    ├── _strip_llm_header() 去除 LLM 自生成的标题/元数据
  │    └── _polish_scene_text() 段落间距标准化 + 重复句子检测
  ├── SceneEvaluator.evaluate_scene()
  │    ├── _check_pov()      快速关键词跳过 → LLM 全场景扫描 (前2500字)
  │    ├── _check_continuity()  身体状态 vs 动作矛盾检测 → LLM 确认
  │    └── _compute_qa_metrics() 非致命质量信号
  │          key_change 关键词命中率 / 对话轮数 / 模式多样性 / 新颖度 / 节拍对齐
  └── 未通过 + 未达最大重试次数 → eval_feedback写回 → 重写

Phase 3 — Commit (提交)
  ├── TensionEvaluator.evaluate_tension()  → 张力 0-10 + 分类
  ├── SceneCommitter.commit_scene()        → 保存 scenes/scene_XXX.md
  ├── _save_qa()       保存场景 Q&A 评估结果
  ├── _verify_beat()   语义相似度验证节拍是否执行（<阈值 → 保持 pending）
  └── _save_tension()  张力写入场景对象

Phase 4 — Update (记忆更新)
  ├── update_from_scene()
  │    ├── FactExtractor + EntityUpdater     事实 → 实体状态更新
  │    ├── LoreExtractor + ContradictionDetector  世界观 + 冲突检测
  │    └── CharacterDetector                 从正文检测新角色
  ├── _check_goal_promotion()  第10-15幕之间，最活跃线索 → 自动提升为故事目标
  ├── state["current_tick"] += 1
  └── _save_state()
```

### 5.2 为什么这样设计

**两阶段初始化（Tick 0）：** 角色和地点必须先于场景存在。如果 LLM 在同一个 Plan 里既生成角色又写场景，可能出现"场景中引用了一个还没生成的角色"。分离实体生成和场景写作消除了这个竞态。

**Plan 重试（最多 3 次）：** `_enforce_beat_target` 和 `_enforce_pacing` 会 raise ValueError 拒绝不合格的 Plan。LLM 收到 rejection_feedback 后重新生成。这比事后修补更可靠——LLM 看到"上一版被拒原因"后能自我修正。

**写后评估（可重试）：** 写作和评估分离。评估不通过 → 反馈写回 Writer Prompt → 重写。避免了"生成后再修修补补"的复杂性——直接让 LLM 重新来，带着明确的修正方向。

**POV 检测快速路径：** 前 2 幕 + 包含全知关键词（"殊不知"/"他不知道的是"/...）的场景走 LLM 检测，其他场景直接跳过。因为 LLM 检测有 token 成本，而大多数场景不会出现 POV 违规。

**记忆更新在 Commit 之后：** 确保场景已持久化再更新实体状态。如果更新过程中出现异常，场景不会被回滚（它已经写入了），但实体状态会保持旧值——下次 Tick 的 ContextBuilder 会从旧状态出发，不会产生"实体已变但场景丢失"的不一致。

---

## 六、上下文系统

### 6.1 TickContext (`agent/context.py`)

一次 Tick 需要的数据，集中构建，避免多处重复查询：

```python
@dataclass
class TickContext:
    tick: int
    novel_name: str
    foundation: dict              # 故事基础设定（类型/背景/主角/基调）
    active_char: Character        # 当前 POV 角色对象
    active_location: Location     # 当前位置对象
    recent_scenes: List[Scene]    # 最近 N 个场景
    open_loops: List[OpenLoop]    # 所有开放线索
    plot_beat: PlotBeat           # 当前情节节拍（Plot-First 模式）
    qa_feedback: str              # 最近的 Q&A 反馈
```

### 6.2 ContextBuilder — Planner 专用

`build_planner_context()` 返回一个字典（不是 TickContext），包含约 25 个字段：

| 字段 | 来源 | 说明 |
|------|------|------|
| `story_foundation_summary` | state.json | Genre/Premise/Setting/Tone |
| `active_character_details` | memory | 名字+角色+目标+情绪+位置 |
| `character_relationships` | memory | 关系网（对象+类型+状态+视角描述） |
| `existing_characters_summary` | memory | 全部角色登场表（active+returning+最可能回归的sidelined角色） |
| `overall_summary` | memory | 所有场景的一句话摘要串联 |
| `recent_scenes_summary` | memory | 最近 N 个场景的详细摘要（含 bullet points） |
| `open_loops_list` | memory | 开放线索（按 POV 角色关联度+重要性排序，top 10） |
| `tension_history` | memory | 最近 5 幕张力走势 + 节奏建议 |
| `factions_summary` | memory | 势力/组织概况 |
| `relevant_lore` | ChromaDB | 与最近场景相关的前 5 条世界观 |
| `pov_candidates` | memory | 可担任 POV 的角色列表（protagonist/supporting + POV次数） |
| `pov_history` | memory | 最近 8 幕的 POV 角色 |
| `absent_characters` | memory | 超过 5 章未出场的 sidelined 角色 |
| `qa_feedback` | memory | 最近 3 幕 Q&A（change/mode/dialogue/novelty/beat_align） |
| `next_plot_beat` | plot_outline.json | 下一待执行节拍 |
| `beat_enforcement_instructions` | config | 严格/标准/宽松模式的提示词指令 |
| `writer_notes` | CLI --notes or config | 场景方向指导 |
| `plan_rejection_feedback` | 上轮被拒原因 | Plan 重试时使用 |

**设计逻辑：**
- 角色登场表只显示 active + returning + 1 个最可能回归的 sidelined 角色，隐藏离场/已故角色。Planner 不需要看到全部 30 个角色——它只需要知道谁在活跃。
- 开放线索按 `POV关联度权重 + 紧急状态` 排序，top 10。避免 prompt 被几十条线索淹没。
- 缺席角色提示 Planner "这个角色 10 章没出现了，是否该让他回归？"——鼓励叙事多样性。

### 6.3 WriterContextBuilder — Writer 专用

`build_writer_context()` 返回一个包含约 18 个字段的字典：

| 字段 | 来源 | 说明 |
|------|------|------|
| `pov_character_details` | memory | POV 角色完整信息（名字/描述/性格/背景/目标/情绪） |
| `location_details` | memory | 地点描述/类型/氛围/特征 |
| `recent_context` | scenes/*.md | 三部分：过渡尾巴（上幕最后500字）+ 近期摘要 + 状态快照 |
| `tool_results_summary` | PlanExecutor | 本幕工具执行结果摘要 |
| `skill_context` | 已激活 skills | 风格标签 + 句长/对话占比 + 写作模式 + 例句 |
| `reference_context` | ReferenceIndexer | 外部参考小说的风格段落 |
| `plot_beat_section` | plan | 如果 Plan 指定了节拍，强制提示 THIS BEAT MUST BE ACCOMPLISHED |
| `scene_length_guidance` | plan or config | 字数区间指导 |
| `eval_feedback` | SceneEvaluator | 上一版场景的修正要求（重试轮） |
| `writer_notes` | CLI --notes or config | 场景方向指导 |

**过渡尾巴 (`_format_transition_tail`)：** 上一章最后 ~500 字符，保证场景衔接自然。不是摘要，而是原文——Writer 看到上一章的结尾句，可以直接接续。

**状态快照 (`_build_state_snapshot`)：** 所有角色的当前位置/身体状态/情绪/目标 + 关系 + 最近 3 个地点 + top 8 紧迫线索。Writer 不需要查 memory，所有信息都在 prompt 里。

---

## 七、Writer 系统 (`agent/writer.py`)

### SceneWriter

```python
write_scene(writer_context) → {text, word_count, title, model_used}
```

**流程：**
1. `prefer_local_writer` 配置决定主模型优先级
2. 尝试主模型生成
3. `_detect_refusal()` 检查是否拒止（前 400 字符匹配中英文拒止关键词 + 响应过短）
4. 拒止 → 切换回落模型重试
5. `_strip_llm_header()` 去掉 LLM 自生成的标题/元数据（避免与 Committer 的标准头重复）
6. `_polish_scene_text()` 段落间距标准化（单空行→双空行）+ 重复句子检测（≥20字出现≥3次）

**拒止检测：** 同时匹配中英文模式（"sorry"、"对不起"、"无法生成"、"违反"、"内容政策"...），且只在首次触发的 2 个匹配或头部匹配+过短（<500字）时才判定为拒止。避免误判角色对话中的"对不起"。

**设计逻辑：** 回落机制让 API 内容审核不影响写作流程。如果 DeepSeek 拒止了一段武侠打斗，会自动切换到另一个后端重写。`model_used` 记录实际使用的模型，方便后续回溯。

---

## 八、Evaluator 系统 (`agent/evaluator.py`)

### SceneEvaluator

三层检查，非致命问题记入 warnings 不阻塞流程：

**第一层 — POV 检测：**
- 快速路径：若场景不包含任何全知关键词（"殊不知"/"他不知道的是"...），且不是前 2 幕，直接跳过 LLM
- LLM 路径：取场景前 2500 字 → 发送专门的 POV Judge Prompt → LLM 找出违规点

**第二层 — 连续性检查：**
- 启发式：角色身体状态含 "injured/wounded" + 场景中出现 "leaped/sprinted/跃起/飞奔" 等剧烈动作
- 触发后 → LLM 二次确认（可能是角色尝试但失败了，不算矛盾）

**第三层 — QA 指标（非致命）：**
- `achieved_change`：Plan 的 key_change 关键词是否出现在场景文本中（≥30% 命中）
- `dialogue_count`：对话轮数统计（四种引号对）
- `mode_diversity_warning`：连续多幕 scene_mode 相同触发警告
- `novelty_score`：与上一幕的模式/对话多样性差异打分（1.0-9.0）
- `beat_hint_alignment`：场景文本与当前情节节拍的关键词重叠率

**设计逻辑：** POV 和连续性才是硬伤（会阻塞重试），QA 指标是质量信号（只记 warnings）。快速关键词路径避免了大多数场景的 LLM 调用——没有"殊不知"类关键词的场景直接通过 POV 检查。

---

## 九、记忆系统

### 9.1 数据实体 (`memory/entities.py`)

| 实体 | 核心字段 | 存储 |
|------|---------|------|
| `Character` | name, role, personality, current_state(goals/emotion/physical/location), backstory, relationships, status, appearance_ticks | `memory/characters/C{id:03d}.json` |
| `Location` | name, type, description, atmosphere, features, status | `memory/locations/L{id:03d}.json` |
| `Scene` | title, text summary, word_count, tension_level, tick, pov_character_id | `memory/scenes/S{id:03d}.json` |
| `OpenLoop` | description, importance, status, related_characters, scenes_mentioned, is_story_goal | `memory/loops.json` |
| `Lore` | statement, category, lore_type(rule/fact/constraint/capability/limitation), importance | `memory/lore.json` |
| `Faction` | name, org_type, summary, objectives, influence, assets, stance_by_character, relationships | `memory/factions/F{id:03d}.json` |

**Character.current_state** 是嵌套结构：
```
CharacterState
├── goals: List[str]          当前目标
├── emotional_state: str      文字情绪
├── emotion: EmotionVector    效价(-1~1) + 唤醒度(0~1) + dominant
├── physical_state: str       身体状态 (injured/tired/healthy/...)
├── location_id: str          当前位置
└── inventory: List[str]      持有物品
```

**设计逻辑：** `current_state` 是随着每幕更新的"可变层"，而 `personality`/`backstory`/`physical_traits` 是"不可变层"。这样记忆更新只动可变部分，不改人物基本设定。

### 9.2 MemoryManager (`memory/manager.py`)

JSON 文件 CRUD 操作。按 ID 前缀路由：
- `C...` → `memory/characters/`
- `L...` → `memory/locations/`
- `S...` → `memory/scenes/`
- 其他 → 对应 JSON 文件

提供：`load_character()`, `save_character()`, `list_characters()`, `get_character_relationships()`, `get_open_loops()`, `get_recent_scene_qa()`, `load_all_lore()`, 等。

### 9.3 VectorStore (`memory/vector_store.py`)

基于 ChromaDB 的向量索引：
- `index_scene(scene)` — 将场景摘要向量化存入
- `search_lore(query, n_results)` — 语义搜索世界观条目
- `compute_semantic_similarity(a, b)` — 两个文本的余弦相似度（用于节拍验证）
- `search_memory(query, n_results)` — 通用记忆搜索

**设计逻辑：** 向量存储是"软索引"——不依赖精确关键词匹配。节拍验证用语义相似度而非关键词匹配，因为同样的情节可以用完全不同的词表达。

### 9.4 场景后处理 (`memory/update.py`)

`update_from_scene()` — 每幕 Commit 后调用：

```
1. _extract_and_update()
   FactExtractor: LLM 从场景文本提取事实
   EntityUpdater: 事实 → 实体更新（角色状态/位置/关系/物品）

2. _extract_lore()
   LoreExtractor: LLM 提取世界观规则
   LoreContradictionDetector: 检查新 Lore 与已有 Lore 是否冲突

3. _detect_characters()
   CharacterDetector: 从正文检测未被注册的新角色名
   → 创建 stub 角色 or 提示用户手动注册
```

**设计逻辑：** 整个后处理流程是一个简单的顺序管道。三个步骤相互独立（事实提取不需要等世界观提取完成），但各自都可能调用 LLM。用 `config` 中的 `enable_*` 开关可以逐项关闭。

---

## 十、Plot 系统 (`plot/manager.py`)

### PlotOutlineManager

管理 `plot_outline.json` 中的情节节拍（PlotBeat）：

```python
PlotBeat:
    id: str                    # PB001, PB002, ...
    description: str           # "柳知画从昏迷中醒来，发现自己身处玄门禁地"
    characters_involved: list  # 涉及角色
    location: str              # 指定地点
    plot_threads: list         # 推进的情节线程
    tension_target: int        # 目标张力
    prerequisites: list        # 前置节拍 ID
    resolves_loops: list       # 解决的线索
    creates_loops: list        # 创建的新线索
    status: str                # pending → completed
    executed_in_scene: str     # 执行场景 ID
```

**节拍生成：** `generate_next_beats(count=5)` → LLM 根据当前故事状态（开放线索+最近场景摘要）生成候选节拍。返回的节拍没有 ID——由 `add_beats()` 分配 PBxxx 编号后持久化。

**节拍生命周期：**
```
generate_next_beats() → add_beats() → plot_outline.json
                                          ↓
Tick._resolve_plot_beat() → get_next_beat() (status=pending)
                                          ↓
Tick._verify_beat() → semantic similarity check
  ├── 通过 → _mark_beat_complete() (status=completed)
  └── 未通过 → 保持 pending，下个 Tick 重新分配
```

**三种执行模式（config）：**
1. **soft_hint（提示）** — 节拍显示在 Context 中，Planner 可自由决定
2. **guided（引导）** — 节拍优先，但允许跳过（需理由）
3. **strict（强制）** — `_enforce_beat_target` 拒绝不指定当前 beat 的 Plan

---

## 十一、Tool 系统

### 11.1 ToolRegistry (`tools/registry.py`)

维护工具名 → Tool 实例的映射。每个 Tool 有一个 `execute(args)` 方法。

### 11.2 已注册的 10 个工具 (`cli/main.py:460-470`)

| 工具名 | 实现类 | 功能 |
|--------|--------|------|
| `name.generate` | `NameGeneratorTool` | 随机生成中文名（姓氏+名字） |
| `memory.search` | `MemorySearchTool` | 语义搜索记忆（通过 VectorStore） |
| `character.generate` | `CharacterGenerateTool` | 创建新角色（LLM 生成性格/背景 + 名字去重 + 角色唯一性验证） |
| `location.generate` | `LocationGenerateTool` | 创建新地点（LLM 生成描述 + 去重） |
| `relationship.create` | `RelationshipCreateTool` | 创建角色间关系 |
| `relationship.update` | `RelationshipUpdateTool` | 更新已有关系状态 |
| `relationship.query` | `RelationshipQueryTool` | 查询角色关系 |
| `faction.generate` | `FactionGenerateTool` | 创建势力/组织 |
| `faction.update` | `FactionUpdateTool` | 更新势力信息 |
| `faction.query` | `FactionQueryTool` | 查询势力信息 |

**设计逻辑：** Planner 的 Plan JSON 中 `actions` 数组每项指定 `tool` 和 `args`。PlanExecutor 遍历执行，返回结果。Planner 决定"需要生成一个角色"，调用 `character.generate`，但 Planner 不控制角色的具体属性——那是工具实现的事。这种分离让 Planner 保持战略层面，工具负责战术细节。

---

## 十二、Skill 系统

### 12.1 Skill Importer (`skill/importer.py`)

将一部已完成的小说提取为"写作技能"（SKILL.yaml），供其他写作项目参考。

**Pipeline（944 行）：**
```
parse → index → stratified sample → batch LLM extract → merge → audit → assemble
```

**六层角色去重防线：**
1. **LLM 自标注** — 批次 prompt 要求 LLM 输出 `name_type` (proper/descriptor) + `name_confidence` (high/medium/low)
2. **名字匹配** — `_name_overlap()` 检查两个角色名是否有共享字符
3. **关系网重叠** — Jaccard 相似度：两个角色的关系对 `(with, type)` 交集/并集
4. **动态阈值** — `mean + 1.5σ` 的非零成对关系重叠均值，clamp [0.5, 0.9]
5. **互引用阻断** — 如果角色 A 的关系里列出了角色 B 的名字，A 和 B 不能是同一个人（纯确定逻辑）
6. **专名保护** — 两个 `name_type=proper` + `name_confidence=high` 且无名字重叠的角色，需要 ≥0.8 Jaccard 关系重叠才允许合并

**分层采样：** 按对话密度分 5 bin (dialogue_ratio 分层)，确保覆盖对话/叙事/混合文本类型。

**审计（`_final_audit`）：** 两轮结构化审计——
1. **清理轮** — 标签去重 + descriptor 角色合并/删除 + 高重叠对合并
2. **修正轮** — 返回轻量 patch 列表（只修正 role/traits/arc_type，不重建整个角色对象）

**回援采样（`_rescue_batches`）：** 低置信度无关系角色进入 `_pending` 池。批次处理完毕后，搜索全文中出现这些角色名的未采样章节，追加 ≤3 章作为回援批次。

### 12.2 Skill Injector (`skill/injector.py`)

将已导入的 SKILL 注入 Writer/Planner 上下文。三个模式：
- `reference` — 仅风格标签 + 句长/对话占比
- `style_only` — 仅风格 profile
- `full` — 全部 patterns（含模板和例句）

`build_skill_context(state)` 函数从 `state["active_skills"]` 读取已激活技能，格式化为 prompt 可用的文本段。在 WriterContextBuilder 和 ContextBuilder 的 prompt 中作为 `skill_context` 注入。

**设计逻辑：** Skill 系统让 StoryDaemon 具备"风格感知"能力。导入《琼明神女录》提取的 SKILL 后，生成其他故事时可以在 prompt 中注入该小说的风格特征（句长、对话密度、写作模式），引导 Writer 产出相似风格。

---

## 十三、Engine 层 (`engine/core.py`)

### EngineCore

常驻进程引擎，管理整个 StoryDaemon 运行时的生命周期：

```
EngineCore
├── LLMPool         LLM 连接池（多模型复用）
├── ProjectManager  项目管理（创建/加载/删除项目）
└── SkillStore      技能存储（YAML→Skill 对象）
```

**设计逻辑：** Engine 层是为 `novel serve` HTTP 服务准备的。CLI 单次命令不需要 EngineCore (`novel tick` 直接初始化 `StoryAgent`)，但常驻服务需要连接池和项目管理器。

---

## 十四、数据流全景

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI / Engine                             │
│  novel tick ──→ StoryAgent.tick()                               │
└──────────────────┬──────────────────────────────────────────────┘
                   │
    ┌──────────────▼──────────────┐
    │     state.json              │  项目状态 (current_tick, active_character, ...)
    │     config.yaml             │  项目配置 (llm backend/model, generation settings, ...)
    │     foundation.yaml         │  故事基础设定
    └──────────────┬──────────────┘
                   │
    ┌──────────────▼──────────────────────────────────────────────┐
    │                     Phase 1: Plan                           │
    │                                                             │
    │  ContextBuilder ◄── MemoryManager ◄── characters/           │
    │         │                              locations/           │
    │         │                              loops.json           │
    │         │                              lore.json            │
    │         ▼                                                   │
    │  LLM.generate() ──→ Plan JSON                               │
    │         │                                                   │
    │         ▼                                                   │
    │  validate → enforce_beat → enforce_pacing                   │
    │         │                                                   │
    │         ▼                                                   │
    │  PlanExecutor ──→ ToolRegistry ──→ MemoryManager (write)    │
    └──────────────┬──────────────────────────────────────────────┘
                   │
    ┌──────────────▼──────────────────────────────────────────────┐
    │                 Phase 2: Write + Evaluate                   │
    │                                                             │
    │  WriterContextBuilder                                        │
    │    ├── MemoryManager (state snapshot)                        │
    │    ├── scenes/*.md (transition tail)                        │
    │    ├── SkillInjector (active skills)                        │
    │    └── ReferenceIndexer (external style refs)                │
    │         │                                                   │
    │         ▼                                                   │
    │  SceneWriter ──→ LLM ──→ scene text                         │
    │    ├── refusal → fallback → LLM                             │
    │    └── polish (spacing + dup detect)                        │
    │         │                                                   │
    │         ▼                                                   │
    │  SceneEvaluator                                              │
    │    ├── POV check (fast-path or LLM)                         │
    │    ├── Continuity (keyword + LLM confirm)                   │
    │    └── QA metrics (keyword overlap, novelty, dialogue, beat)│
    │         │                                                   │
    │    failed? → eval_feedback → WriterContextBuilder (retry)   │
    └──────────────┬──────────────────────────────────────────────┘
                   │ passed
    ┌──────────────▼──────────────────────────────────────────────┐
    │                   Phase 3: Commit                           │
    │                                                             │
    │  TensionEvaluator → 0-10 + category                         │
    │  SceneCommitter                                              │
    │    ├── scenes/scene_XXX.md (正文)                            │
    │    ├── memory/scenes/SXXX.json (元数据)                     │
    │    └── qa/ (评估结果)                                       │
    │  _verify_beat() → ChromaDB semantic similarity              │
    │  _check_goal_promotion() → 线索 → 故事目标 (tick 10-15)    │
    └──────────────┬──────────────────────────────────────────────┘
                   │
    ┌──────────────▼──────────────────────────────────────────────┐
    │                   Phase 4: Update                           │
    │                                                             │
    │  update_from_scene()                                         │
    │    ├── FactExtractor → EntityUpdater                         │
    │    │     └── characters/*.json (state update)                │
    │    ├── LoreExtractor → ContradictionDetector                 │
    │    │     └── lore.json (world rules)                        │
    │    └── CharacterDetector                                     │
    │          └── new stub characters                             │
    │  VectorStore.index_scene() → ChromaDB                       │
    │  state["current_tick"] += 1 → state.json                    │
    └─────────────────────────────────────────────────────────────┘
```

---

## 十五、设计原则

### 确定性 vs 概率性边界

StoryDaemon 在所有关键决策点都尽量使用**确定性逻辑**，LLM 只用于需要创造力的环节：

| 决策点 | 方式 | 原因 |
|--------|------|------|
| 角色去重 | 确定性（6层规则） | 不能靠 LLM "觉得"两个角色是不是同一个人 |
| POV 违规检测 | 关键词快速路径 + LLM 确认 | 规则能覆盖 80% 场景，LLM 处理模糊案例 |
| 拒止检测 | 确定性关键词 | LLM 自己不会"承认"拒止 |
| Plan 校验 | JSON Schema + 节拍强制 + 节奏约束 | 结构性约束必须硬编码 |
| 角色名字生成 | 随机 + 已用名去重 | 不需要 LLM |
| 节拍验证 | 语义相似度 (ChromaDB) | 比关键字匹配更鲁棒 |
| 场景内容 | 全部 LLM 生成 | 创造力不可替代 |
| 角色性格/背景 | LLM 生成 | 需要上下文理解 |
| 世界观提取 | LLM 提取 + 确定性冲突检测 | 提取靠 LLM，检测靠规则 |

### Prompt 策略

- **System Prompt** 是稳定的（`SYSTEM_CORE` + 角色后缀），存在 `prompts.py` 中
- **模板** 是动态的（`data/templates/*.md`），运行时加载，可热更新
- **Anthropic cache_control**：System Prompt 标记为 `ephemeral` 缓存，减少重复 token
- **非 Anthropic 后端**：`chat()` 自动 fallback 为纯文本 `generate()`，对调用者透明

### 配置分层

```
CLI --llm-backend --llm-model (本次运行)
  ↓ 覆盖
项目 config.yaml (持久配置)
  ↓ 覆盖
全局 configs/config.py (默认值)
```

---

## 十六、关键文件索引

| 文件 | 行数 | 核心职责 |
|------|------|---------|
| `agent/agent.py` | 901 | StoryAgent — Tick 循环主编排 |
| `agent/context.py` | 799 | ContextBuilder — Planner 上下文（~25 字段） |
| `agent/writer_context.py` | 518 | WriterContextBuilder — Writer 上下文（~18 字段） |
| `agent/writer.py` | 289 | SceneWriter — 写作 + 拒止回落 + 润色 |
| `agent/evaluator.py` | 389 | SceneEvaluator — POV/连续性 + QA 指标 |
| `agent/prompts.py` | ~150 | System Prompt + 模板加载 + split_prompt |
| `agent/schemas.py` | ~60 | Plan JSON 校验规则 |
| `agent/runtime.py` | ~100 | PlanExecutor — 工具调用执行 |
| `agent/scene_committer.py` | ~120 | 场景提交 + Q&A 保存 |
| `memory/manager.py` | ~650 | MemoryManager — 全部实体 CRUD |
| `memory/entities.py` | ~400 | 数据类定义 (Character/Location/Scene/OpenLoop/Lore/Faction/...) |
| `memory/vector_store.py` | ~200 | ChromaDB 向量索引 + 语义搜索 |
| `memory/update.py` | ~200 | 场景后处理管道 (事实+世界观+角色检测) |
| `plot/manager.py` | 197 | PlotOutlineManager — 节拍生成/持久化/状态 |
| `tools/llm_interface.py` | 153 | 5 种后端的统一初始化入口 |
| `tools/multi_provider_llm.py` | 606 | 多供应商 API 注册表 + 各供应商调用函数 |
| `tools/provider.py` | 68 | LLMProvider — generate/chat 统一封装 |
| `tools/router.py` | 79 | ModelRouter — 按任务路由模型 |
| `tools/registry.py` | ~30 | ToolRegistry — 工具注册表 |
| `tools/memory_tools.py` | ~600 | 10 个工具的实现 |
| `skill/importer.py` | 944 | 小说 → SKILL 提取（所有去重+审计逻辑） |
| `skill/injector.py` | ~100 | SKILL → 写作上下文注入 |
| `skill/models.py` | ~60 | Skill/StyleProfile/NarrativePattern/CharacterArchetype |
| `cli/main.py` | 1652 | 17 个 CLI 命令注册 + tick/run 实现 |
| `engine/core.py` | ~60 | EngineCore — 常驻进程引擎 |
