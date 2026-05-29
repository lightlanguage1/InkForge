# InkForge 架构设计文档

> 基于代码实际探索，非旧文档推断。日期：2026-05-28。

---

## 一、项目概述

InkForge 是一个 **LLM 驱动的中文长篇小说涌现式生成系统**。核心理念：不预设大纲，让叙事结构在逐幕（Tick）迭代中自行涌现。

**技术栈：** Python 3.11+, Typer CLI, FastAPI REST API, ChromaDB 向量存储, JSON 文件持久化

**前端：** React 18 + TypeScript + Vite 6 + Tailwind CSS 3 + TanStack Query 5 + React Router 6

**关键数字：**
- 5 种 LLM 后端（codex / api / gemini-cli / claude-cli / ollama）
- 每 Tick 4 阶段（Plan → Write+Eval → Commit → Update）
- 13 个 API 路由模块，35+ 个 REST 端点
- 18 个前端页面路由，覆盖全部后端端点
- 10 个注册工具（角色/地点/势力生成、记忆搜索、关系 CRUD）
- 3 层评估（POV 检测、连续性检查、QA 指标）

---

## 二、顶层目录结构

```
InkForge/
├── novel_agent/              Python 后端包（~99 个源文件）
│   ├── agent/                核心引擎（17 个文件）
│   │   ├── agent.py          StoryAgent — Tick 循环主编排器
│   │   ├── factory.py        基础设施组装工厂（CLI/API 共用）
│   │   ├── streaming_agent.py SSE 流式包装器
│   │   ├── context.py        ContextBuilder — Planner 上下文
│   │   ├── writer_context.py WriterContextBuilder — Writer 上下文
│   │   ├── writer.py         SceneWriter — 写作 + 拒止回落
│   │   ├── evaluator.py      SceneEvaluator — POV/连续性 + QA 指标
│   │   ├── prompts.py        System Prompt + 模板加载
│   │   ├── schemas.py        Plan JSON 校验
│   │   ├── runtime.py        PlanExecutor — 工具调用执行
│   │   ├── plan_manager.py   Plan 持久化 + 错误日志
│   │   ├── scene_committer.py 场景提交 + Q&A 保存
│   │   ├── tension_evaluator.py 张力 0-10 评分
│   │   ├── character_detector.py 从正文自动检测新角色
│   │   ├── fact_extractor.py     从正文提取结构化事实
│   │   ├── entity_updater.py     事实 → 实体更新
│   │   ├── lore_extractor.py     世界观规则提取
│   │   └── lore_contradiction_detector.py 设定冲突检测
│   ├── cli/                 CLI 层（20 个文件）
│   │   ├── main.py          17 个 Typer 命令注册
│   │   ├── project.py       项目管理
│   │   ├── foundation.py    故事基础设定向导
│   │   ├── server.py        API 服务器启动
│   │   ├── recent_projects.py 最近项目追踪
│   │   └── commands/        各命令实现
│   │       ├── compile.py / summarize.py / goals.py / inspect.py
│   │       ├── titles.py / checkpoint.py / lore.py / plan.py
│   │       ├── status.py / list.py / plot.py / skill.py
│   ├── api/                 REST API 服务（16 个文件）
│   │   ├── server.py        FastAPI 应用 + CORS + 13 个路由注册
│   │   ├── models.py        Pydantic 请求/响应模型
│   │   ├── deps.py          共享依赖（Engine 单例 + Agent 创建）
│   │   └── routers/         13 个路由模块
│   │       ├── health.py / projects.py / generation.py / entities.py
│   │       ├── status.py / compile.py / plot.py / checkpoints.py
│   │       ├── skills.py / references.py / log.py / threads.py
│   ├── memory/              持久化与向量检索（10 个文件）
│   │   ├── manager.py       MemoryManager — JSON 文件 CRUD
│   │   ├── entities.py      数据类 (Character/Location/Scene/OpenLoop/Lore/Faction/StoryThread/...)
│   │   ├── vector_store.py  ChromaDB 向量索引
│   │   ├── update.py        场景后处理总入口
│   │   ├── summarizer.py    场景摘要生成
│   │   ├── checkpoint.py    项目存档（快照 + 回滚）
│   │   └── thread_manager.py 叙事支线生命周期管理
│   ├── tools/               LLM 后端 + 工具系统（15 个文件）
│   │   ├── llm_interface.py     后端初始化 + 全局接口
│   │   ├── multi_provider_llm.py 多供应商 API 注册表
│   │   ├── provider.py          LLMProvider — generate/chat 统一封装
│   │   ├── router.py            ModelRouter — 按任务路由模型
│   │   ├── registry.py          ToolRegistry — 工具注册表
│   │   ├── memory_tools.py      10 个工具的实现
│   │   ├── name_generator.py    随机中文名生成器
│   │   ├── codex_interface.py   Codex CLI 后端
│   │   ├── gemini_cli_interface.py Gemini CLI 后端
│   │   ├── claude_cli_interface.py Claude Code CLI 后端
│   │   ├── ollama_stream.py     Ollama 流式输出
│   │   └── llm_pool.py          LLM 连接池（Engine 用）
│   ├── skill/               写作技能导入/注入（4 个文件）
│   │   ├── importer.py      小说 → SKILL.yaml（6层角色去重）
│   │   ├── injector.py      SKILL → Writer/Planner 上下文注入
│   │   ├── models.py        Skill/StyleProfile/NarrativePattern
│   │   └── store.py         SkillStore — YAML 持久化
│   ├── engine/              常驻进程引擎（2 个文件）
│   │   ├── core.py          EngineCore — LLMPool + ProjectManager + SkillStore
│   │   └── project_manager.py 项目实例管理
│   ├── plot/                情节节拍管理
│   │   └── manager.py       PlotOutlineManager
│   ├── reference/           外部参考小说索引
│   │   └── indexer.py       ReferenceIndexer — 分块 + 向量搜索
│   ├── configs/             配置与常量
│   │   ├── config.py        全局配置加载
│   │   ├── constants.py     所有魔法数字 + 默认值
│   │   └── api_keys.py      API Key 统一解析
│   ├── utils/               工具函数
│   │   ├── file_ops.py      文件 I/O
│   │   └── log_manager.py   统一日志管理
│   └── data/
│       ├── names/           中文姓名库 (JSON)
│       ├── templates/       Prompt 模板 (Markdown)
│       └── skills/          已导入的写作技能 (YAML)
├── frontend/                 React 前端（~65 个源文件）
│   └── src/
│       ├── api/             10 个域 + client.ts
│       ├── types/           10 个域类型文件
│       ├── components/      17 个组件（12 个 UI 原子 + 5 个复合组件）
│       ├── pages/           18 个页面
│       ├── utils/           logger.ts（前端日志 → 后端）
│       └── styles/          tokens.css（CSS 主题变量）
├── docs/                    项目文档（8 个 .md）
├── example/                 示例小说
├── scripts/                 辅助脚本
├── start.bat / start.sh     一键启动器
├── requirements.txt
├── setup.py
└── config.example.yaml
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

### 3.5 Agent 中的双模型 (`agent/agent.py`)

```python
self.llm = LLMProvider(...)       # 主模型（Planner + Writer）
self.agent_llm = LLMProvider(...) # 辅助模型（Evaluator + Extractor）
```

- `self.llm` → 从 CLI 的 `--llm-backend` / `--llm-model` 来，或从项目 config.yaml
- `self.agent_llm` → 仅在 `router.enabled=true` 时启用，走 `extractor` 任务配置；否则等于 `self.llm`

---

## 四、基础设施组装工厂 (`agent/factory.py`)

CLI 和 API 共用的唯一入口点。消除 `cli/main.py` 和 `api/deps.py` 中的重复初始化逻辑。

```python
def create_agent(project_dir, config, llm_backend=None, llm_model=None, ...) -> StoryAgent:
    # 1. 解析 LLM 后端和模型 (CLI 参数 > config > 默认)
    # 2. initialize_llm() → LLMProvider
    # 3. 创建 ToolRegistry + MemoryManager + VectorStore
    # 4. 注册 10 个工具
    # 5. 返回 StoryAgent 实例
```

每次调用创建全新的 agent 实例（读取最新 state.json），支持 CLI `run()` 中每幕重建。

---

## 五、CLI 层 (`cli/main.py`)

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

## 六、Tick 循环 — 核心引擎

### 6.1 StoryAgent (`agent/agent.py`)

主编排器，管理整个 Tick 生命周期。

**初始化：**
1. 从 `state.json` 加载项目状态
2. 建立双模型（主 + Router 辅助）
3. 实例化所有组件：Memory, Vector, ContextBuilder, WriterContextBuilder, PlanExecutor, Writer, Evaluator, Committer, PlotManager, ThreadManager

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
  ├── _enforce_threads()        叙事支线审计：确保支线被推进
  ├── _enforce_pacing()         节奏约束：连续3幕不能相同 progress_step
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
  ├── ThreadManager.audit()                  支线审计 + 陈旧度警告
  ├── _check_goal_promotion()  第10-15幕之间，最活跃线索 → 自动提升为故事目标
  ├── state["current_tick"] += 1
  └── _save_state()
```

### 6.2 Streaming Wrapper (`agent/streaming_agent.py`)

为 API 的 SSE 端点提供流式 Tick 进度：

```python
class StreamingStoryAgent:
    def tick_stream(self) -> Generator[str]:
        yield "tick_start"      # Tick 开始
        yield "phase: context"  # 上下文构建
        yield "phase: planning" # Plan 生成
        yield "phase: execution"# 工具执行
        yield "phase: writing"  # 写作中
        yield "phase: generating" # LLM 生成中
        yield "scene_text"      # 流式场景文本
        yield "phase: eval"     # 评估中
        yield "phase: commit"   # 提交中
        yield "tick_complete"   # 完成
        yield "tick_error"      # 异常
```

### 6.3 为什么这样设计

**两阶段初始化（Tick 0）：** 角色和地点必须先于场景存在。如果 LLM 在同一个 Plan 里既生成角色又写场景，可能出现"场景中引用了一个还没生成的角色"。分离实体生成和场景写作消除了这个竞态。

**Plan 重试（最多 3 次）：** `_enforce_beat_target`、`_enforce_threads` 和 `_enforce_pacing` 会 raise ValueError 拒绝不合格的 Plan。LLM 收到 rejection_feedback 后重新生成。

**写后评估（可重试）：** 写作和评估分离。评估不通过 → 反馈写回 Writer Prompt → 重写。

**记忆更新在 Commit 之后：** 确保场景已持久化再更新实体状态。防止"实体已变但场景丢失"的不一致。

---

## 七、上下文系统

### 7.1 TickContext (`agent/context.py`)

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

### 7.2 ContextBuilder — Planner 专用

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
| `story_threads` | thread_manager | 当前活跃的所有叙事支线状态 |
| `writer_notes` | CLI --notes or config | 场景方向指导 |
| `plan_rejection_feedback` | 上轮被拒原因 | Plan 重试时使用 |

### 7.3 WriterContextBuilder — Writer 专用

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

---

## 八、Writer 系统 (`agent/writer.py`)

### SceneWriter

```python
write_scene(writer_context) → {text, word_count, title, model_used}
```

**流程：**
1. `prefer_local_writer` 配置决定主模型优先级
2. 尝试主模型生成
3. `_detect_refusal()` 检查是否拒止（前 400 字符匹配中英文拒止关键词 + 响应过短）
4. 拒止 → 切换回落模型重试
5. `_strip_llm_header()` 去掉 LLM 自生成的标题/元数据
6. `_polish_scene_text()` 段落间距标准化（单空行→双空行）+ 重复句子检测（≥20字出现≥3次）

**拒止检测：** 同时匹配中英文模式，且只在首次触发的 2 个匹配或头部匹配+过短（<500字）时才判定为拒止。避免误判角色对话中的"对不起"。

---

## 九、Evaluator 系统 (`agent/evaluator.py`)

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

---

## 十、记忆系统

### 10.1 数据实体 (`memory/entities.py`)

| 实体 | 核心字段 | 存储 |
|------|---------|------|
| `Character` | name, role, personality, current_state(goals/emotion/physical/location), backstory, relationships, status, appearance_ticks | `memory/characters/C{id:03d}.json` |
| `Location` | name, type, description, atmosphere, features, status | `memory/locations/L{id:03d}.json` |
| `Scene` | title, text summary, word_count, tension_level, tick, pov_character_id | `memory/scenes/S{id:03d}.json` |
| `OpenLoop` | description, importance, status, related_characters, scenes_mentioned, is_story_goal | `memory/loops.json` |
| `Lore` | statement, category, lore_type(rule/fact/constraint/capability/limitation), importance | `memory/lore.json` |
| `Faction` | name, org_type, summary, objectives, influence, assets, stance_by_character, relationships | `memory/factions/F{id:03d}.json` |
| `StoryThread` | name, description, category, importance, status, character_ids, scene_ids, confidence | `memory/threads.json` |

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

**设计逻辑：** `current_state` 是随着每幕更新的"可变层"，而 `personality`/`backstory`/`physical_traits` 是"不可变层"。

### 10.2 MemoryManager (`memory/manager.py`)

JSON 文件 CRUD 操作。按 ID 前缀路由：
- `C...` → `memory/characters/`
- `L...` → `memory/locations/`
- `S...` → `memory/scenes/`
- 其他 → 对应 JSON 文件

提供：`load_character()`, `save_character()`, `list_characters()`, `get_character_relationships()`, `get_open_loops()`, `get_recent_scene_qa()`, `load_all_lore()`, 等。

### 10.3 VectorStore (`memory/vector_store.py`)

基于 ChromaDB 的向量索引：
- `index_scene(scene)` — 将场景摘要向量化存入
- `search_lore(query, n_results)` — 语义搜索世界观条目
- `compute_semantic_similarity(a, b)` — 两个文本的余弦相似度（用于节拍验证）
- `search_memory(query, n_results)` — 通用记忆搜索

### 10.4 ThreadManager (`memory/thread_manager.py`)

叙事支线全生命周期管理：

```
ThreadManager
├── audit()              LLM 审计场景序列，识别新形成的叙事支线
├── list_threads()       列出所有支线（按状态筛选）
├── update_thread()      更新支线状态/进度
├── get_stale_warnings() 陈旧度检查：
│   ├── 超过 THREAD_STALE_WARN 幕未推进 → 警告
│   └── 超过 THREAD_STALE_FORCE 幕未推进 → 强制关闭
└── _enforce_threads()   Tick 中调用，确保活跃支线被推进
```

**设计逻辑：** 长篇小说的叙事支线会自然形成和消亡。ThreadManager 定期审计场景序列，自动识别"第3章开始的那个复仇线"之类的分支叙事，避免支线被遗忘或无限挂起。

### 10.5 场景后处理 (`memory/update.py`)

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

---

## 十一、Plot 系统 (`plot/manager.py`)

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

**节拍生成：** `generate_next_beats(count=5)` → LLM 根据当前故事状态（开放线索+最近场景摘要）生成候选节拍。

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

## 十二、Tool 系统

### 12.1 ToolRegistry (`tools/registry.py`)

维护工具名 → Tool 实例的映射。每个 Tool 有一个 `execute(args)` 方法。

### 12.2 已注册的 10 个工具

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

---

## 十三、Skill 系统

### 13.1 Skill Importer (`skill/importer.py`)

将一部已完成的小说提取为"写作技能"（SKILL.yaml）。

**Pipeline（944 行）：**
```
parse → index → stratified sample → batch LLM extract → merge → audit → assemble
```

**六层角色去重防线：**
1. **LLM 自标注** — 批次 prompt 要求 LLM 输出 `name_type` + `name_confidence`
2. **名字匹配** — `_name_overlap()` 检查两个角色名是否有共享字符
3. **关系网重叠** — 关系对 `(with, type)` 的 Jaccard 相似度
4. **动态阈值** — `mean + 1.5σ` 的非零成对关系重叠均值，clamp [0.5, 0.9]
5. **互引用阻断** — 如 A 的关系列出 B 的名字，A 和 B 不能是同一个人
6. **专名保护** — 两个 proper+high 角色需要 ≥0.8 Jaccard 才合并

**分层采样：** 按对话密度分 5 bin (dialogue_ratio 分层)。

**审计（`_final_audit`）：** 清理轮 + 修正轮（轻量 patch）。

**回援采样（`_rescue_batches`）：** 低置信度无关系角色 → `_pending` 池 → 回援 ≤3 章。

### 13.2 Skill Injector (`skill/injector.py`)

三个模式：
- `reference` — 仅风格标签 + 句长/对话占比
- `style_only` — 仅风格 profile
- `full` — 全部 patterns（含模板和例句）

---

## 十四、REST API 层

### 14.1 服务架构 (`api/server.py`)

FastAPI 应用，13 个路由模块：

```python
# 路由注册
health.router          # GET /health
projects.router        # POST /api/v1/project, GET /api/v1/projects, POST /api/v1/resume
generation.router      # POST /api/v1/project/{id}/tick, GET .../tick/stream, POST .../run
entities.router        # GET entities (characters/locations/scenes/loops/factions + relationships)
status.router          # GET /project/{id}/status, /goals, /lore
compile.router         # POST /project/{id}/compile, GET /summarize, POST /titles
plot.router            # GET/POST/DELETE /project/{id}/plot
checkpoints.router     # POST/GET/DELETE /project/{id}/checkpoints
skills.router          # POST /api/v1/skills/import, GET/POST/DELETE /api/v1/skills
references.router      # POST /api/v1/references/import, POST /api/v1/references/search
log.router             # POST /api/v1/log (前端日志接收)
threads.router         # StoryThread CRUD + 审计端点
```

### 14.2 关键端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/project` | POST | 创建新项目 |
| `/api/v1/projects` | GET | 列出所有项目 |
| `/api/v1/resume` | POST | 恢复最近项目 |
| `/api/v1/project/{id}/tick` | POST | 执行一幕（同步） |
| `/api/v1/project/{id}/tick/stream` | GET | 执行一幕（SSE 流式） |
| `/api/v1/project/{id}/run` | POST | 批量执行多幕 |
| `/api/v1/project/{id}/status` | GET | 项目状态总览 |
| `/api/v1/project/{id}/characters` | GET | 角色列表 |
| `/api/v1/project/{id}/characters/{cid}` | GET | 角色详情 |
| `/api/v1/project/{id}/locations` | GET | 地点列表 |
| `/api/v1/project/{id}/relationships` | GET | 角色关系图数据 |
| `/api/v1/project/{id}/compile` | POST | 编译完整手稿 |
| `/api/v1/log` | POST | 前端日志收集 |

---

## 十五、Engine 层 (`engine/core.py`)

### EngineCore

常驻进程引擎，管理整个 InkForge 运行时的生命周期：

```
EngineCore
├── LLMPool         LLM 连接池（多模型复用，含健康检查）
├── ProjectManager  项目管理（创建/加载/删除项目 + StoryAgent 实例池）
└── SkillStore      技能存储（YAML→Skill 对象）
```

**设计逻辑：** Engine 层是为 `novel serve` HTTP 服务准备的。CLI 单次命令不需要 EngineCore (`novel tick` 直接通过 `factory.create_agent()` 初始化 `StoryAgent`)，但常驻服务需要连接池和项目管理器。

---

## 十六、数据流全景

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLI / API / Engine                          │
│  novel tick ──→ factory.create_agent() → StoryAgent.tick()      │
│  POST /tick ──→ deps → factory.create_agent() → tick()         │
│  GET  /tick/stream → StreamingStoryAgent.tick_stream()          │
└──────────────────┬──────────────────────────────────────────────┘
                   │
    ┌──────────────▼──────────────┐
    │     state.json              │  项目状态 (current_tick, ...)
    │     config.yaml             │  项目配置 (llm backend/model, ...)
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
    │         │                              threads.json         │
    │         ▼                                                   │
    │  LLM.generate() ──→ Plan JSON                               │
    │         │                                                   │
    │         ▼                                                   │
    │  validate → enforce_beat → enforce_threads → enforce_pacing │
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
    │  ThreadManager.audit()                                       │
    │    └── threads.json (支线状态更新)                           │
    │  VectorStore.index_scene() → ChromaDB                       │
    │  state["current_tick"] += 1 → state.json                    │
    └─────────────────────────────────────────────────────────────┘
```

---

## 十七、设计原则

### 确定性 vs 概率性边界

| 决策点 | 方式 | 原因 |
|--------|------|------|
| 角色去重 | 确定性（6层规则） | 不能靠 LLM "觉得"两个角色是不是同一个人 |
| POV 违规检测 | 关键词快速路径 + LLM 确认 | 规则能覆盖 80% 场景，LLM 处理模糊案例 |
| 拒止检测 | 确定性关键词 | LLM 自己不会"承认"拒止 |
| Plan 校验 | JSON Schema + 节拍强制 + 支线强制 + 节奏约束 | 结构性约束必须硬编码 |
| 角色名字生成 | 随机 + 已用名去重 | 不需要 LLM |
| 节拍验证 | 语义相似度 (ChromaDB) | 比关键字匹配更鲁棒 |
| 叙事支线审计 | LLM 识别 + 确定性陈旧度检查 | 识别靠 LLM，生命周期靠规则 |
| 场景内容 | 全部 LLM 生成 | 创造力不可替代 |

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

## 十八、关键文件索引

| 文件 | 核心职责 |
|------|---------|
| `agent/agent.py` | StoryAgent — Tick 循环主编排 |
| `agent/factory.py` | 基础设施组装工厂（CLI/API 共用） |
| `agent/streaming_agent.py` | SSE 流式包装器 |
| `agent/context.py` | ContextBuilder — Planner 上下文（~25 字段） |
| `agent/writer_context.py` | WriterContextBuilder — Writer 上下文（~18 字段） |
| `agent/writer.py` | SceneWriter — 写作 + 拒止回落 + 润色 |
| `agent/evaluator.py` | SceneEvaluator — POV/连续性 + QA 指标 |
| `agent/prompts.py` | System Prompt + 模板加载 |
| `agent/schemas.py` | Plan JSON 校验规则 |
| `agent/runtime.py` | PlanExecutor — 工具调用执行 |
| `agent/scene_committer.py` | 场景提交 + Q&A 保存 |
| `memory/manager.py` | MemoryManager — 全部实体 CRUD |
| `memory/entities.py` | 数据类定义 (Character/Location/Scene/OpenLoop/Lore/Faction/StoryThread/...) |
| `memory/vector_store.py` | ChromaDB 向量索引 + 语义搜索 |
| `memory/update.py` | 场景后处理管道 (事实+世界观+角色检测) |
| `memory/thread_manager.py` | 叙事支线生命周期管理 |
| `plot/manager.py` | PlotOutlineManager — 节拍生成/持久化/状态 |
| `tools/llm_interface.py` | 5 种后端的统一初始化入口 |
| `tools/multi_provider_llm.py` | 多供应商 API 注册表 |
| `tools/provider.py` | LLMProvider — generate/chat 统一封装 |
| `tools/router.py` | ModelRouter — 按任务路由模型 |
| `tools/memory_tools.py` | 10 个工具的实现 |
| `skill/importer.py` | 小说 → SKILL 提取（6层去重+审计） |
| `skill/injector.py` | SKILL → 写作上下文注入 |
| `cli/main.py` | 17 个 CLI 命令注册 |
| `api/server.py` | FastAPI 应用 + 13 个路由注册 |
| `api/routers/log.py` | 前端日志接收端点 |
| `api/routers/threads.py` | 支线追踪 REST API |
| `engine/core.py` | EngineCore — 常驻进程引擎 |
