# InkForge (StoryDaemon) 后端架构深度审查报告

> **审查日期**: 2026-06-01  
> **审查范围**: `novel_agent/` 全部 76 个 Python 源文件 + 根目录配置文件  
> **审查方法**: 两轮——第一轮结构探索 + 第二轮设计意图验证  
> **审查原则**: 不以教科书模式评判，而是理解每个设计决策的业务上下文和项目阶段

---

## 目录

1. [系统概览](#1-系统概览)
2. [分层架构](#2-分层架构)
3. [核心数据流](#3-核心数据流)
4. [逐层深度分析](#4-逐层深度分析)
   - [4.1 Configs 配置层](#41-configs-配置层)
   - [4.2 Utils 工具层](#42-utils-工具层)
   - [4.3 Memory 记忆层](#43-memory-记忆层)
   - [4.4 Tools 工具层](#44-tools-工具层)
   - [4.5 Agent 智能体层](#45-agent-智能体层)
   - [4.6 Plot 情节层](#46-plot-情节层)
   - [4.7 Skill 技能层](#47-skill-技能层)
   - [4.8 Reference 参考层](#48-reference-参考层)
   - [4.9 Engine 引擎层](#49-engine-引擎层)
   - [4.10 API 接口层](#410-api-接口层)
   - [4.11 CLI 命令行层](#411-cli-命令行层)
   - [4.12 User 用户层](#412-user-用户层)
5. [跨层关注点](#5-跨层关注点)
6. [设计决策分析](#6-设计决策分析)
7. [问题清单](#7-问题清单)
8. [优化路线图](#8-优化路线图)

---

## 1. 系统概览

### 1.1 项目定位

InkForge 是一个 **LLM 驱动的长篇小说自动生成系统**，面向中文网络小说作者。核心能力：

- **Tick 循环**: 每一 tick 生成一个场景（~2000-4000 字），由 LLM 规划→执行工具→写作→评估→提交→记忆更新
- **节拍系统**: 情节节拍（plot beat）驱动故事走向，支持 strict/guided/soft_hint 三种模式
- **实体管理**: 角色、地点、场景、派系、故事线索、开放循环、世界观规则的持久化
- **语义搜索**: ChromaDB 向量存储，支持跨实体类型的语义检索
- **流式生成**: SSE（Server-Sent Events）实时推送生成进度
- **技能系统**: 从已有小说中提取叙事模式、风格画像、角色原型，注入到新项目

### 1.2 技术栈

| 层级 | 技术选型 |
|------|---------|
| Web 框架 | FastAPI + Uvicorn |
| 数据校验 | Pydantic v2 |
| 向量存储 | ChromaDB（本地嵌入，all-MiniLM-L6-v2） |
| LLM 后端 | OpenAI API / DeepSeek / Anthropic / Gemini / Ollama / Codex CLI / Gemini CLI / Claude CLI |
| 持久化 | JSON 文件系统（每实体每文件 + 集合文件） |
| 用户认证 | SQLite + JWT（纯 stdlib 实现） |
| 异步 | asyncio + ThreadPoolExecutor |
| 配置 | YAML + 环境变量 |

### 1.3 关键数据

| 指标 | 数值 |
|------|------|
| Python 源文件 | 76 个（`novel_agent/` 下） |
| 最大文件 | `agent/agent.py`（~1100 行） |
| API 路由 | 14 个模块 |
| Agent 子模块 | 20 个 |
| Tools 子模块 | 14 个 |
| 实体类型 | 12+ 个 dataclass |
| LLM 后端 | 5 种（API 多供应商 + 3 种 CLI + Ollama） |

---

## 2. 分层架构

### 2.1 分层图

```
┌─────────────────────────────────────────────────────┐
│  CLI 层 (cli/)           API 层 (api/)              │  ← 入口层
│  typer 命令               FastAPI 路由              │
├─────────────────────────────────────────────────────┤
│  User 层 (user/)                                     │  ← 横切关注点
│  JWT 认证 / SQLite / ContextVar                     │
├─────────────────────────────────────────────────────┤
│  Engine 层 (engine/)                                 │  ← 运行时生命周期
│  引擎核心 / 项目管理器 / LLM 连接池                  │
├─────────────────────────────────────────────────────┤
│  Agent 层 (agent/)                                   │  ← 业务编排核心
│  故事代理 / 上下文构建 / 写作 / 评估 / 提交          │
├──────────────────┬──────────────────────────────────┤
│  Tools 层        │  Memory 层                       │  ← 领域服务层
│  LLM 接口        │  实体 CRUD / 向量搜索             │
│  工具注册/执行   │  摘要 / 线索 / 检查点             │
├──────────────────┴──────────────────────────────────┤
│  Plot 层  │  Skill 层  │  Reference 层              │  ← 专业子系统
├─────────────────────────────────────────────────────┤
│  Configs 层  │  Utils 层                             │  ← 基础设施层
│  配置/常量   │  文件IO/日志                          │
└─────────────────────────────────────────────────────┘
```

### 2.2 依赖方向

**严格单向，无循环依赖**：

```
configs/  →  utils/  →  memory/  →  tools/  →  agent/  →  engine/  →  api/ & cli/
```

- `configs/constants.py` 零依赖（仅 stdlib）
- `configs/config.py` 仅依赖 yaml
- `memory/` 依赖 `configs/` + `utils/`
- `tools/` 依赖 `configs/` + `memory/`
- `agent/` 依赖上述所有层
- `engine/` 依赖 `agent/`、`tools/`、`cli/`
- `api/` 和 `cli/` 依赖所有层（入口层）

### 2.3 类继承体系

```
Tool (tools/base.py)                    ← 抽象基类
├── MemorySearchTool
├── CharacterGenerateTool
├── LocationGenerateTool
├── RelationshipCreateTool
├── RelationshipUpdateTool
├── RelationshipQueryTool
├── FactionGenerateTool
├── FactionUpdateTool
├── FactionQueryTool
└── NameGeneratorTool

LLM 后端（无基类，鸭子类型）
├── CodexInterface         ← subprocess
├── GeminiCliInterface     ← subprocess
├── ClaudeCliInterface     ← subprocess
├── MultiProviderInterface ← HTTP API
└── OllamaInterface        ← HTTP API

实体（dataclass，Mixin 风格继承）
├── Character  → to_dict/from_dict
├── Location   → to_dict/from_dict
├── Scene      → to_dict/from_dict
├── ...等 12+ 个
```

---

## 3. 核心数据流

### 3.1 Tick 生成管道（系统核心循环）

```
                        ┌──────────────┐
                        │  状态加载     │  state.json → self.state
                        └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │  节拍解析     │  PlotOutlineManager.get_next_beat()
                        └──────┬───────┘
                               │
              ┌────────────────▼────────────────┐
              │  Phase 1: 规划 (Plan)            │
              │  ┌────────────────────────────┐ │
              │  │ ContextBuilder              │ │  收集角色/地点/场景/循环/线索/节拍
              │  │ → 构建计划器上下文          │ │
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  ┌──────────▼─────────────────┐ │
              │  │ LLM 生成 JSON Plan          │ │  ← Planner LLM (DeepSeek)
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  ┌──────────▼─────────────────┐ │
              │  │ validate_plan (jsonschema)  │ │  结构校验
              │  │ _enforce_beat_target        │ │  节拍强制 (strict mode)
              │  │ _enforce_pacing             │ │  节奏约束 (scene_mode 轮换)
              │  │ _enforce_threads            │ │  线索推进检查
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  重试: 最多 3 次，反馈注入       │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │  Phase 1.5: 执行 (Execute)       │
              │  PlanExecutor.execute_plan()     │  ← 串行执行 tool calls
              │  → memory.search                 │    最多 MAX_TOOLS_PER_TICK=3
              │  → character.generate            │    遇错立即停止
              │  → relationship.create 等        │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │  Phase 2: 写作 (Write)           │
              │  ┌────────────────────────────┐ │
              │  │ WriterContextBuilder        │ │  构建写作上下文
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  ┌──────────▼─────────────────┐ │
              │  │ SceneWriter.write_scene()   │ │  ← Writer LLM (DeepSeek)
              │  │ (OpenAI/Anthropic API)      │ │    若 API 拒绝→Ollama 本地回退
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  ┌──────────▼─────────────────┐ │
              │  │ SceneEvaluator              │ │  ← 并行: POV + Logic QA
              │  │ → POV 检测 (快速路径+LLM)   │ │    Evaluator LLM (Ollama/Agent)
              │  │ → 连续性检测 (关键词+LLM)   │ │
              │  │ → 逻辑 QA (LLM)             │ │
              │  └──────────┬─────────────────┘ │
              │             │                    │
              │  重试: 最多 eval_max_retries+1 次│
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │  Phase 3: 提交 (Commit)          │
              │  TensionEvaluator → 张力 0-10    │  ← 关键词评分
              │  SceneCommitter → 保存 .md/.json │
              │  _save_qa → QA 指标持久化        │
              │  _verify_beat → 节拍完成度检查    │
              └────────────────┬────────────────┘
                               │
              ┌────────────────▼────────────────┐
              │  Phase 4: 记忆更新 (Memory)      │
              │  update_from_scene()             │
              │  → FactExtractor (事实提取)      │  ← Agent LLM (Ollama/低成本)
              │  → LoreExtractor (世界观提取)    │     各步骤独立 try/except
              │  → CharacterDetector (新角色)     │     失败不阻断管道
              │  → ThreadManager.advance()       │
              │  → GoalPromoter (循环→目标晋升)   │
              │  → ThreadAuditor (线索审计)       │     每 5 tick 一次
              └────────────────┬────────────────┘
                               │
                        ┌──────▼───────┐
                        │  状态保存     │  state.json + auto-checkpoint (每3tick)
                        └──────────────┘
```

### 3.2 API 请求流

```
HTTP Request
  │
  ├─ AuthMiddleware ─── 验证 Bearer Token (JWT)
  │  └─ 设置 ContextVar: user_id, user_api_key
  │
  ├─ Router Endpoint ─── 例如 POST /api/v1/project/{id}/tick/stream
  │  │
  │  ├─ deps.resolve_project(project_id)  ─── 按用户目录查找项目
  │  ├─ deps.try_lock_generation(project_id) ─── 每用户+每项目锁
  │  ├─ deps.create_agent(project_dir)    ─── 调用 factory.create_agent()
  │  ├─ StreamingStoryAgent(agent).tick_stream() ─── SSE 生成器
  │  └─ deps.release_generation(project_id)
  │
  └─ Response ─── StreamingResponse (SSE) 或 JSONResponse
```

### 3.3 LLM 双连接架构

```
                    ┌─────────────────────┐
                    │    ModelRouter      │  根据任务类型路由模型
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼──────┐  ┌─────▼──────┐  ┌──────▼────────┐
     │ Planner LLM   │  │ Writer LLM │  │ Evaluator LLM  │
     │ (DeepSeek)    │  │ (DeepSeek) │  │ (Ollama 本地)  │
     │ 高质量规划    │  │ 高质量写作 │  │ 低成本评审     │
     └───────────────┘  └────────────┘  └───────────────┘
```

---

## 4. 逐层深度分析

### 4.1 Configs 配置层

**文件**: `configs/config.py`, `configs/constants.py`, `configs/api_keys.py`, `configs/key_pool.py`

#### 设计分析

| 模块 | 职责 | 依赖 | 评价 |
|------|------|------|------|
| `constants.py` | 所有魔法数字和字符串的单一事实来源 | 零依赖 | ✅ 典范 |
| `config.py` | YAML 加载 + 点号路径访问 + 深度合并 | yaml | ✅ 实用 |
| `api_keys.py` | API 密钥解析（环境变量 > .env） | key_pool | ✅ 清晰 |
| `key_pool.py` | 多密钥轮询池（`INKFORGE_API_KEYS`） | 零依赖 | ✅ 简洁 |

#### 设计意图

`Config.get("generation.recent_scenes_count", 3)` 的点号路径语法是一个有意识的选择：YAML 文件天然嵌套，但 Python dict 没有点号访问。这个小小的 DSL 统一了两者。代价是失去了 IDE 自动补全和编译期键名校验——但对于一个单人项目，配置文件本身（`config.example.yaml`）就是文档。

`constants.py` 特意要求保持零依赖以支持极快导入——文档字符串中声明了这一点。这意味着其他模块可以安全地 `from ..configs.constants import ...` 而不会触发级联导入。

#### 可优化项

- 点号路径的拼写错误只能在运行时发现。考虑为高频键定义常量别名（如 `K = ConfigKeys`）但**不强制**迁移——渐进式采用即可
- `DEFAULT_CONFIG` 字典随着项目增长会越来越长，可考虑拆分为 `DEFAULT_LLM_CONFIG`、`DEFAULT_GENERATION_CONFIG` 等子字典

---

### 4.2 Utils 工具层

**文件**: `utils/file_ops.py`, `utils/log_manager.py`

#### 设计分析

`file_ops.py` 提供了原子化的 JSON 写入（先写临时文件再重命名）、schema 校验和 prompt 保存功能。这些都是纯工具函数，无状态，设计合理。

`log_manager.py` 提供了双通道日志（轮转文件 + 控制台），加上 Windows 兼容的 `rmtree_force`（处理 Windows 上的只读文件删除问题）。

#### 可优化项

- 缺少统一的 `extract_json_from_llm_response()` 函数（见 [5.1](#51-json-解析重复)）

---

### 4.3 Memory 记忆层

**文件**: `memory/manager.py`, `memory/entities.py`, `memory/vector_store.py`, `memory/summarizer.py`, `memory/thread_manager.py`, `memory/checkpoint.py`, `memory/update.py`

#### 4.3.1 MemoryManager (`manager.py`, ~926 行)

**核心职责**: 所有实体的持久化 CRUD。7 种实体类型各自的 load/save/list/update 方法。

**持久化策略**:

| 实体类型 | 存储方式 | 原因 |
|---------|---------|------|
| Character | `characters/{id}.json` | 每角色独立文件，O(1) 查找 |
| Location | `locations/{id}.json` | 每地点独立文件 |
| Scene | `scenes/{id}.json` + `scenes/scene_{tick:03d}.md` | 元数据 + 全文分离 |
| Faction | `factions/{id}.json` | 每派系独立文件 |
| StoryThread | `story_threads/{id}.json` | 每线索独立文件 |
| OpenLoop | `open_loops.json`（单文件） | 集合小，常整读 |
| Relationship | `relationships.json`（单文件） | 集合小，常整读 |
| Lore | `lore.json`（单文件） | 集合小，常整读 |

**为什么实体类型使用独立 CRUD 而不是泛型 Repository？**

这是经过深思熟虑的设计选择，而非疏忽。理由：

1. **实体差异大**: `Character.from_dict()` 有迁移逻辑（`name` → `first_name/family_name`），`Faction` 有 auto-create-on-update 行为，`Relationship` 是双向的——一个泛型 `save(entity)` 方法需要 isinstance 分支来处理这些差异
2. **类型安全**: `save_character(char: Character)` 提供编译期类型检查，`save_entity(entity: Any)` 做不到
3. **IDE 友好**: 自动补全列出所有可用方法
4. **自愈计数器**: `_load_counters()` 在启动时扫描磁盘文件，从实际存在的文件中推导最大 ID——如果 `counters.json` 损坏或丢失，系统可以自恢复

**Tick 级缓存**: `_cache` + `_cache_tick` 机制防止同一 tick 内多次磁盘读取（`ContextBuilder` 和 `WriterContextBuilder` 可能分别调用 `get_all_characters()`）

#### 4.3.2 实体模型 (`entities.py`)

17 个 dataclass，每个都有 `to_dict()` 和 `from_dict()` 方法。采用 dataclass 而非 Pydantic 的原因是 JSON 文件存储——dataclass 的序列化更轻量，不需要 Pydantic 的校验开销。

**值得注意的设计**:
- `Character.from_dict()` 包含向后兼容迁移（`name` → `first_name/family_name`, `aliases` → `nicknames`）——这是单人项目处理 schema 演化的务实方式
- `EMOTION_MAP` 将中文情感标签映射到维度（价态/唤醒度），为情感跟踪提供语义精度
- `Scene` 包含 `entities_created`、`open_loops_created` 等变更跟踪列表——作为结构化的操作日志

#### 4.3.3 VectorStore (`vector_store.py`)

ChromaDB 封装。每实体类型一个 collection。使用本地嵌入模型（ChromaDB 默认的 all-MiniLM-L6-v2），无需外部 API 调用。

**存在的问题**: 6 处裸 `except:` 导致删除失败静默忽略。应该至少捕获 `except Exception` 并打 warning 日志。

#### 4.3.4 场景后处理 (`update.py`)

管道式函数设计（非类），因为它是无状态的三个步骤串联。每个步骤独立 try/except——如果事实提取失败，世界观提取和角色检测仍然进行。这种弹性设计是有意的："先交付故事，记忆一致性是次要的"。

---

### 4.4 Tools 工具层

**文件**: 14 个模块，包括 `base.py`、`registry.py`、`llm_interface.py`、`provider.py`、`multi_provider_llm.py`、`router.py`、`memory_tools.py`、`name_generator.py`、`llm_pool.py` 和 3 个 CLI 接口

#### 4.4.1 工具系统

```
Tool (base.py)                    ← 抽象基类
  ├── execute(**kwargs) → dict    ← 抽象方法
  ├── get_schema() → dict         ← JSON Schema for LLM function calling
  └── validate_args(args) → None  ← 参数校验
```

10 个具体工具覆盖了角色生成、地点生成、关系管理、派系管理、名称生成和记忆搜索。`ToolRegistry` 是简单的 name→Tool 字典。

**工具链**: `PlanExecutor` 支持简单的占位符替换——如果 `character.generate` 的 `name` 参数是 `"<from name.generate>"`，则用上一个 `name.generate` 的结果替换。这是轻量级工具链，不需要复杂的 DAG 依赖解析。

#### 4.4.2 LLM 接口设计

**`llm_interface.py`** 的全局单例模式：

```python
_llm_client: Optional[LLMClient] = None  # 模块级全局

def initialize_llm(backend="codex", ...):  # 设置全局
def send_prompt(prompt, max_tokens):       # 使用全局
```

这在多线程服务器环境下看起来像反模式，但实际上：
- `StoryAgent` 构造时接受显式的 `llm_interface` 参数，**不依赖全局**
- 全局单例仅为 CLI 脚本和简单调用提供便利
- 每个 `StoryAgent` 实例有自己的 `self.llm` 和 `self.agent_llm`

**3 个 CLI 接口的重复**：`codex_interface.py`、`gemini_cli_interface.py`、`claude_cli_interface.py` 确实有相同的结构（验证→子进程→重试），但每个 CLI 的标志不同，这些差异使得提取基类的收益有限——每个文件不到 150 行，重复的总代码量约 200 行。**在当前阶段，保持独立是可以接受的**。

**`provider.py` 的 Anthropic 客户端重复**: `LLMProvider` 创建了自己的 Anthropic 客户端，而 `multi_provider_llm.py` 中也有 `_get_anthropic_client()`。这是值得统一的地方。

**`multi_provider_llm.py` 的模型注册表**: 用 lambda 注册表将模型名映射到发送函数是优雅的。添加新模型只需一个函数+一个注册表条目。

#### 4.4.3 自定义名称生成器 (`name_generator.py`)

音节级别的中文/科幻名称生成器。这是一个独立的小型专业系统，包含音节数据文件（`data/names/` 下的 JSON）。设计为 tool 以被 LLM plan 调用。

---

### 4.5 Agent 智能体层

**文件**: 20 个模块。这是系统最大的层，也是核心业务逻辑的集中地。

#### 4.5.1 StoryAgent (`agent.py`, ~1100 行)

**这是整个系统最核心的类，也是最有争议的**。它承载了 tick 管道的全部编排逻辑。

**为什么它是"上帝对象"但仍可能是合理的设计？**

1. **有状态管道的天然内聚性**: tick 的每个阶段严格依赖前一个阶段的输出。Python 的调用栈本身就是执行顺序的保证。拆分到独立服务意味着需要异步协调和持久队列——对于单人项目是过度工程。

2. **私有方法服务于重试循环**: `_enforce_beat_target`、`_enforce_pacing`、`_enforce_threads` 作为方法存在，是因为它们的 `ValueError` 被捕获后作为中文反馈注入到规划器的重试上下文——它们是重试机制的一部分，而不是独立的验证器。

3. **`_first_tick` vs `_normal_tick` 的分支**: 第 0 tick 确实不同——需要先生成实体（角色、地点），然后用真实 ID 更新计划。泛化为通用方法会增加不必要的 if/else 分支。

**但仍有可以拆分的部分**:

| 当前方法 | 行数 | 可提取为 | 优先级 |
|---------|------|---------|--------|
| `_enforce_beat_target` | ~20 | `PlanValidator` | 低 |
| `_enforce_pacing` | ~30 | `PlanValidator` | 低 |
| `_verify_beat` | ~120 | `BeatTracker` | 中 |
| `_check_goal_promotion` | ~60 | `GoalPromoter` | 中 |
| `_maybe_audit_threads` | ~40 | `ThreadAuditor` | 低 |
| `__init__` 中的 LLM 初始化 | ~30 | `LLMConnectionFactory` | 低 |

这些拆分不改变架构，只是将方法移到独立模块中。**在功能稳定后再做是合理的**。

#### 4.5.2 ContextBuilder (`context.py`, ~827 行)

构建规划器 prompt 的上下文。收集角色、地点、场景、开放循环、线索、节拍、技能等信息并格式化为 LLM 输入。

**为什么这么大？** 构建一个好的规划器 prompt 需要大量上下文工程——格式化角色仪表盘、线索仪表盘、节拍仪表盘、技能上下文、世界观规则等。每个 `_format_*` 方法都在做 prompt 工程，这是生成质量的核心。

#### 4.5.3 WriterContextBuilder (`writer_context.py`, ~589 行)

构建写作 prompt 的上下文。与 ContextBuilder 有一些相似的格式化逻辑（线索仪表盘、节拍信息），但因为写作和规划需要不同的信息呈现方式，所以分开是有意义的。

**重复检测**: `_format_thread_dashboard`（ContextBuilder）和 `_format_thread_context`（WriterContextBuilder）都调用 `ThreadManager.format_dashboard()`——这不是重复，而是对同一底层数据的两个视角。真正重复的是技能格式化——`_format_skill_context()` 的两个实现可以统一。

#### 4.5.4 SceneEvaluator (`evaluator.py`, ~496 行)

**设计精巧**。三层评估：

1. **POV 检测**: 快速关键词路径（"他不知道的是" 等 7 个标记）→ 命中时用 LLM 确认，避免误报
2. **连续性检测**: 关键词匹配（"injured"+"leaped" 等组合）→ LLM 确认
3. **逻辑 QA**: 总是用 LLM 评审时间/因果/性格/设定一致性

POV 和逻辑检查通过 `ThreadPoolExecutor(max_workers=2)` 并行执行，连续性是关键词检查（同步、快速）。

`_compute_qa_metrics` 方法计算场景的多样性指标（模式轮换检测、新颖性评分、节拍对齐度）——这些是给作者的信号，不是阻断条件。

#### 4.5.5 StreamingStoryAgent (`streaming_agent.py`)

**复制了 `StoryAgent` 的 tick 流程，在每个阶段间插入 SSE 事件**。

这看起来像代码分叉，但有充分理由：
- `StoryAgent.tick()` 是同步阻塞方法——要改成生成器需要全面重构
- 使用回调/钩子模式会在每个阶段增加 `if hooks: hooks.on_phase(...)` 的模板代码
- 包装器模式保持 `agent.py` 的纯净——对 CLI 用户零影响

**不过存在一个问题**：`_stream_normal_tick` 缺少了 `agent.py` 中的 `_enforce_beat_target`、`_enforce_pacing` 调用和评估重试循环。这需要在文档中明确标注。

#### 4.5.6 其他 Agent 子模块

| 模块 | 行数 | 职责 | 设计评价 |
|------|------|------|---------|
| `writer.py` | ~150 | LLM 写作 + API 拒绝回退 | ✅ 简洁的回退逻辑 |
| `scene_committer.py` | ~150 | 保存场景 .md/.json + 向量索引 | ✅ 单一职责 |
| `plan_manager.py` | ~100 | 计划和错误日志的持久化 | ✅ 轻量 |
| `schemas.py` | ~50 | JSON Schema 校验 | ✅ 纯校验 |
| `prompts.py` | ~200 | Prompt 模板 | ✅ 数据与逻辑分离 |
| `tension_evaluator.py` | ~80 | 关键词张力评分 | ✅ 快速路径 |
| `fact_extractor.py` | ~150 | LLM 事实提取 | ✅ 标准 LLM 调用 |
| `entity_updater.py` | ~500 | 应用提取的事实到实体 | ⚠️ 行数偏多，可拆分 |
| `lore_extractor.py` | ~200 | 世界观规则提取 | ✅ 标准 |
| `lore_contradiction_detector.py` | ~100 | 向量相似度检测矛盾 | ✅ 向量搜索应用 |
| `character_detector.py` | ~100 | LLM 新角色名识别 | ✅ 标准 |
| `runtime.py` | ~150 | 工具执行运行时 | ✅ 清晰 |

---

### 4.6 Plot 情节层

**文件**: `plot/manager.py`

管理情节节拍（plot beat）的生成和生命周期。支持三种模式：

| 模式 | 行为 |
|------|------|
| `soft_hint` | 节拍作为建议，不强制 |
| `guided` | 节拍作为引导，writer 可以偏离 |
| `strict` | 强制节拍对齐，否则拒绝 plan |

节拍支持 LLM 生成（从故事基础设定生成节拍大纲），也可以手动编辑。每个节拍有 `status`（pending/active/done/skipped）和 `confidence` 评分。

---

### 4.7 Skill 技能层

**文件**: `skill/models.py`, `skill/store.py`, `skill/importer.py` (~944 行), `skill/injector.py`

**核心设计**: 从已有小说中提取"技能"——叙事模式、风格画像、角色原型——并将其注入到新项目的上下文中。

`importer.py` 是第二大的文件，实现了分层迭代提取管道：
1. 分块阅读源小说
2. 逐块提取叙事模式（NarrativePattern）
3. 汇总为风格画像（StyleProfile）
4. 识别角色原型（CharacterArchetype）

这个管道之所以复杂，是因为它处理的是真实的文本——需要分块、去重、汇总——每一步都是 LLM 调用。944 行反映了管道的真实复杂度，而非代码膨胀。

`store.py` 使用 YAML 持久化（不是 JSON），因为技能数据更适合人类阅读和编辑。

---

### 4.8 Reference 参考层

**文件**: `reference/indexer.py`

多小说参考库，使用 ChromaDB 索引。允许作者将已有小说导入为"参考库"，在新项目生成时作为风格参考。

---

### 4.9 Engine 引擎层

**文件**: `engine/core.py`, `engine/project_manager.py`

#### 4.9.1 EngineCore (`core.py`, ~68 行)

**非常薄的初始化器**。管理 LLM 连接池、项目生命周期、技能存储的延迟加载。本质上是一个依赖注入容器。

#### 4.9.2 ProjectManager (`project_manager.py`, ~127 行)

**与 `factory.py` 存在代码重复**——两个文件各自有一套完全相同的 10 行工具注册代码。

**当前状态分析**:
- `api/deps.py` 调用 `factory.create_agent()`——**绕过** ProjectManager
- `ProjectManager.get_or_create_project()` 有自己的工具注册——但**可能未被 API 层使用**
- CLI 也可能直接调用 `factory.create_agent()`

这意味着 `ProjectManager` 的 agent 池管理功能实际上未被充分利用。这是一个**架构漂移**——两个代码路径独立演化，但功能重叠。

**处理建议**: 要么删除 `ProjectManager` 中重复的工具注册，让它委托给 `factory.create_agent()`；要么让 API 层真正使用 ProjectManager 做 agent 池管理。**当前阶段，统一到 factory 是最小成本的方案**。

---

### 4.10 API 接口层

**文件**: `api/server.py`, `api/deps.py`, `api/models.py`, `api/user_context.py`, 14 个路由器模块

#### 4.10.1 路由组织

每个业务域一个路由器文件，遵循 FastAPI 惯用模式。这是标准做法，无需改变。

#### 4.10.2 依赖注入 (`deps.py`)

| 功能 | 实现 | 评价 |
|------|------|------|
| 引擎单例 | `_engine: Optional[EngineCore]` 模块级变量 | ✅ 合理 |
| 生成锁 | `_active_generations: set[str]`（用户:项目ID 键） | ✅ 防止并发 tick |
| 项目解析 | `resolve_project()` 按用户目录+部分名称匹配 | ✅ 用户友好 |
| Agent 创建 | `create_agent()` 委托给 `factory.create_agent()` | ✅ 单一入口 |

`_lock_key` 包含 `user_id` 的设计确保不同用户的项目互不干扰。锁是进程内 set，简单有效——如果扩展到多进程部署需要用 Redis 替代。

#### 4.10.3 SSE 流式端点 (`routers/generation.py`)

SSE + `ThreadPoolExecutor` + `asyncio.Queue` 的模式是成熟的：
- Python 线程运行 `streaming_agent.tick_stream()`（生成器）
- SSE 事件通过 `queue.Queue` 传递给 asyncio 事件循环
- 客户端断开时通过 `asyncio.CancelledError` 清理

`ThreadPoolExecutor(max_workers=20)` 的 20 可能过大——实际并发受限于 LLM API 速率限制而非 CPU。

#### 4.10.4 User Context 重复

`api/user_context.py` 和 `user/context.py` 之间存在功能重叠：
- `user/context.py`: 简单的 `user_id` ContextVar + setter/getter
- `api/user_context.py`: 额外的 `user_api_key` ContextVar + `derive_user_id()`（SHA256 hash）

两个模块各自创建了**独立的 ContextVar 实例**，虽然键名不同（"user_id" vs "user_id"），但语义重叠。`api/user_context.py` 是 `user/context.py` 的超集。建议合并。

#### 4.10.5 错误处理

API 路由中三种错误处理模式并存：

```python
# 模式1: 简单映射（丢失异常类型信息）
try: ... 
except Exception: raise HTTPException(500)

# 模式2: 带日志（较好但仍丢失类型）
try: ...
except Exception: logger.exception(...); raise HTTPException(500, detail=str(e))

# 模式3: 依赖全局 handler（最干净但缺少上下文）
# 无 try/except，依赖 server.py 的 global_exception_handler
```

**建议**: 引入业务异常层次结构（`InkForgeError` → `ProjectNotFoundError`、`GenerationLockedError` 等），用 FastAPI exception handlers 映射到 HTTP 状态码。这比在每个路由中重复 try/except 更可维护。

---

### 4.11 CLI 命令行层

**文件**: `cli/main.py` (~1400 行), `cli/project.py`, `cli/foundation.py`, `cli/recent_projects.py`, `cli/server.py`, 12 个命令模块

CLI 使用 `typer` 框架，每个命令一个子模块。命令模块通过 `cli/main.py` 注册。`cli/project.py` 中的项目创建逻辑被 API 层复用。

`cli/main.py` 的 ~1400 行主要是命令路由和参数定义——typer 框架的特性使命令注册代码冗长但结构清晰。

---

### 4.12 User 用户层

**文件**: `user/auth.py`, `user/context.py`, `user/db.py`, `user/middleware.py`

**认证设计**:
- JWT 令牌（纯 stdlib 实现，无第三方依赖）
- SQLite 数据库存储用户和邀请码
- `AuthMiddleware` 在 FastAPI 中间件层验证 Bearer Token
- 激活系统：邀请码 → 激活 → API Key → JWT

`auth.py` 的 JWT 实现使用纯 Python（`hmac` + `hashlib` + `base64`），没有依赖 PyJWT。这是一个刻意的选择——减少依赖，但代价是需要自行维护 JWT 实现。

---

## 5. 跨层关注点

### 5.1 JSON 解析重复

三个模块各自实现了 `_extract_json`，功能各异：

| 位置 | 功能 | 特殊处理 |
|------|------|---------|
| `skill/importer.py:560` | 从 LLM 响应提取 JSON | trailing comma 修复、单引号→双引号 |
| `agent/evaluator.py:320` | 最简版本 | 仅 `{...}` 匹配 |
| `api/routers/portrait.py:181` | 完整版本 | `【JSON】` 标记、markdown fence 剥离 |

**影响**: evaluator 的简单版本可能在 LLM 返回嵌套 JSON 时失败（`\{[^{}]*\}` 不能匹配嵌套对象）；importer 的版本更好（`\{[\s\S]*\}` 匹配嵌套）。

**建议**: 统一到 `utils/json_parser.py`，提供分级解析策略。

### 5.2 异常处理粒度

全项目 ~80 处 `except Exception`，其中许多可以缩小到具体类型：

```python
# agent/entity_updater.py — 7 处 except Exception
# agent/agent.py — 10 处 except Exception
# agent/context.py — 8 处 except Exception
```

此外，`vector_store.py` 中有 6 处裸 `except:`（会捕获 KeyboardInterrupt/SystemExit）。

**分析**: 在 LLM 调用的上下文中，`except Exception` 有一定合理性——LLM 可能以多种方式失败（网络错误、超时、速率限制、格式错误），而调用者通常只需要"失败时继续"的行为。但这不意味着不需要具体处理。**至少要记录具体异常类型**，便于事后诊断。

**建议**: 
- 裸 `except:` → 立即修复为 `except Exception` + warning 日志
- `except Exception` → 渐进式细化，优先处理高频调用路径

### 5.3 类型注解一致性

| 风格 | 使用位置 | 建议 |
|------|---------|------|
| `Optional[X]` | 大多数代码 | 统一迁移到 `X \| None` |
| `X \| None` | `utils/log_manager.py` | ✅ Python 3.10+ 风格 |
| 缺少返回类型 | `writer_context.py` 部分方法 | 补全 |
| 缺少返回类型 | `manager.py` 多数方法 | 补全 |
| 裸 `dict` | `agent.py` 核心方法 | 考虑 TypedDict |

### 5.4 全局可变状态

| 位置 | 变量 | 风险 | 建议 |
|------|------|------|------|
| `tools/llm_interface.py` | `_llm_client` | 并发后端切换 | 标注为 legacy，新代码传参 |
| `api/deps.py` | `_config`, `_engine` | 低（初始化后不变） | ✅ 可接受 |
| `api/deps.py` | `_active_generations` | 低（set 操作原子） | ✅ 可接受（多进程需 Redis） |

---

## 6. 设计决策分析

### 6.1 为什么是 JSON 文件而不是数据库？

**决策**: 实体持久化使用 JSON 文件系统（每实体每文件 + 集合 JSON 文件）

**原因**:
1. **零运维**: 不需要安装/配置数据库
2. **可手动编辑**: 作者可以直接打开 JSON 文件修改角色属性
3. **Git 友好**: 整个项目目录就是一个 git 仓库，天然版本控制
4. **数据量小**: 一个小说项目最多几百个角色、几千个场景——远未达到需要数据库的规模
5. **快速原型**: 单人项目，不需要考虑并发写入

**适用边界**: 当出现以下信号时考虑迁移到 SQLite/PostgreSQL：
- 多个用户同时编辑同一项目
- 实体数量超过 10000+
- 需要复杂查询（按属性筛选角色等）
- ChromaDB 的向量搜索不够用

### 6.2 为什么 StreamingStoryAgent 复制流程而不是用钩子？

**决策**: `streaming_agent.py` 复制了 `agent.py` 的 tick 流程

**原因**:
1. `tick()` 是同步方法——改成生成器需要全面重构
2. 钩子/回调模式会在每个阶段增加 `if hooks:` 模板代码
3. 包装器保持 `agent.py` 对 CLI 用户的零影响
4. 只有一个流式消费者——如果出现第二个，再考虑抽象

**代价**: 对 `StoryAgent._normal_tick()` 的修改需要同步到 `StreamingStoryAgent`。当前已有微小分叉（流式版缺少 `_enforce_beat_target` 和 `_enforce_pacing`）。

### 6.3 为什么 factory.py 和 project_manager.py 有重复的工具注册？

**决策**: 两条独立的 agent 创建路径

**原因**: 这是**架构漂移**而非有意设计。`factory.py` 是为 API 快速添加的，而 `project_manager.py` 是原有的引擎层代码。两条路径尚未统一。

**建议**: 让 `ProjectManager.get_or_create_project()` 内部调用 `factory.create_agent()`。

### 6.4 为什么使用双 LLM 架构？

**决策**: Planner/Writer 使用 DeepSeek（高质量），Evaluator/Extractor 使用 Ollama 本地模型（低成本）

**原因**:
1. 规划和写作需要高质量输出 → 商业 API
2. 评估和提取是辅助任务 → 本地模型即可，降低成本
3. `ModelRouter` 允许为每个任务类型配置不同的模型和后端
4. 本地模型无网络延迟，适合高频的评估调用

### 6.5 为什么 Config 使用点号路径而不是嵌套 dict？

**决策**: `config.get("generation.recent_scenes_count", 3)`

**原因**:
1. YAML 文件天然嵌套，但 Python dict 没有点号访问
2. 点号路径比 `config["generation"]["recent_scenes_count"]` 更简洁
3. 默认值在一行内表达
4. 代价是失去 IDE 自动补全——对于单人项目可接受

---

## 7. 问题清单

### 7.1 必须修复（影响正确性）

| # | 问题 | 位置 | 修复方式 |
|---|------|------|---------|
| 1 | `StreamingStoryAgent._stream_normal_tick` 缺少 `_enforce_beat_target`/`_enforce_pacing` 调用 | `streaming_agent.py:41-104` | 对齐 `agent.py` 的 `_normal_tick` 流程 |
| 2 | 裸 `except:` 6 处 | `vector_store.py:396,401,406,551,569` | 改为 `except Exception` + logger.warning |
| 3 | `api/user_context.py` 和 `user/context.py` 的 ContextVar 重复 | 两个文件 | 合并，让 `api/user_context.py` 从 `user/context.py` 导入 |

### 7.2 应该修复（影响可维护性）

| # | 问题 | 位置 | 修复方式 |
|---|------|------|---------|
| 4 | `_extract_json` 3 个独立实现 | `importer.py`, `evaluator.py`, `portrait.py` | 提取到 `utils/json_parser.py` |
| 5 | `factory.py` 和 `project_manager.py` 工具注册重复 | 两个文件 | `project_manager.py` 委托给 `factory.create_agent()` |
| 6 | API 路由错误处理模式不一致 | 14 个路由文件 | 引入业务异常 + exception handlers |
| 7 | `provider.py` 的 Anthropic 客户端与 `multi_provider_llm.py` 重复 | 两个文件 | 统一 Anthropic 客户端创建 |
| 8 | `entity_updater.py` (~500行) 行数过大 | `agent/entity_updater.py` | 按实体类型拆分更新逻辑 |

### 7.3 可以优化（影响长期演进）

| # | 问题 | 位置 | 修复方式 |
|---|------|------|---------|
| 9 | `StoryAgent` (~1100行) 职责过多 | `agent/agent.py` | 提取 BeatTracker、GoalPromoter 等组件 |
| 10 | `MemoryManager` (~926行) CRUD 模板重复 | `memory/manager.py` | 可选地引入泛型 Repository（低优先级） |
| 11 | 3 个 CLI 接口结构相似 | `tools/*_interface.py` | 可选地提取 `SubprocessLLMInterface` 基类（低优先级） |
| 12 | 类型注解缺失 | 多个文件 | 渐进式补全 |
| 13 | 缺少 `TypedDict` 定义 | `agent/agent.py` | 定义 PlanDict、EvalResult 等 |
| 14 | `llm_interface.py` 全局单例 | `tools/llm_interface.py` | 标注为 legacy，新代码显式传参 |

---

## 8. 优化路线图

### Phase 1: 安全修复（1-2 天）

```
☐ 1.1 统一 _extract_json → utils/json_parser.py
☐ 1.2 修复 6 处裸 except:
☐ 1.3 合并 user/context.py 和 api/user_context.py
☐ 1.4 对齐 StreamingStoryAgent 与 StoryAgent 的流程差异
```

### Phase 2: 结构整理（3-5 天）

```
☐ 2.1 factory.py 作为唯一 agent 创建入口，project_manager.py 委托
☐ 2.2 统一 Anthropic 客户端创建
☐ 2.3 引入业务异常层次结构 + FastAPI exception handlers
☐ 2.4 统一 API 路由错误处理模式
```

### Phase 3: 长期演进（按需）

```
☐ 3.1 StoryAgent 拆分为更小的组件（BeatTracker、GoalPromoter、ThreadAuditor）
☐ 3.2 entity_updater.py 按实体类型拆分
☐ 3.3 为 LLM 接口引入 Protocol 类型
☐ 3.4 渐进式 TypedDict 覆盖核心数据结构
☐ 3.5 评估是否引入 SQLite 替代部分 JSON 文件存储
```

---

## 附录 A: 架构评分卡

| 维度 | 评分 | 说明 |
|------|------|------|
| 分层架构 | ★★★★☆ | 包级分层清晰，依赖方向正确 |
| 模块化 | ★★★★☆ | 大多数模块单一职责，个别文件过大 |
| 代码重复 | ★★★☆☆ | factory/project_manager、_extract_json、user context |
| 错误处理 | ★★★☆☆ | 合理的弹性设计，但粒度可细化 |
| 类型安全 | ★★★☆☆ | 新代码有注解，旧代码缺失，风格不统一 |
| 命名规范 | ★★★★☆ | 一致性好，部分模块名过于泛化（update.py） |
| 可测试性 | ★★☆☆☆ | 紧耦合使单元测试困难，无测试套件 |
| 可扩展性 | ★★★★☆ | 工具注册表、模型路由、节拍模式都支持扩展 |
| 文档化 | ★★★☆☆ | 有 docstring 但无架构文档，常量有注释 |

## 附录 B: 依赖关系完整图

```
                     ┌──────────────┐
                     │  constants   │ (零依赖)
                     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
     ┌────────▼───┐  ┌─────▼─────┐  ┌────▼─────┐
     │   config   │  │ api_keys  │  │ key_pool │
     └────────┬───┘  └──────────┘  └──────────┘
              │
     ┌────────▼───┐
     │  file_ops  │
     └────────┬───┘
              │
     ┌────────▼────────┐
     │ memory/entities │
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │ memory/manager  │──────┐
     └────────┬────────┘      │
              │               │
     ┌────────▼────────┐  ┌───▼──────────┐
     │ memory/vector   │  │ memory/other  │
     │ _store          │  │ (summarizer,  │
     └────────┬────────┘  │  checkpoint,  │
              │           │  thread_mgr,  │
     ┌────────▼────────┐  │  update)      │
     │  tools/base     │  └──────────────┘
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  tools/llm      │ (interfaces, provider, pool, router)
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  tools/memory   │ (memory_tools, name_generator)
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  agent/*        │ (agent, context, writer, evaluator, ...)
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  plot/manager   │
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  engine/*       │ (core, project_manager)
     └────────┬────────┘
              │
     ┌────────┼────────┐
     │        │        │
┌────▼──┐ ┌──▼───┐ ┌──▼────┐
│  api  │ │ user │ │  cli  │
└───────┘ └──────┘ └───────┘
```

---

> **总结**: InkForge 的架构在**包级别**展现了良好的分层意识和领域建模。在**类/函数级别**，部分文件（agent.py, manager.py, importer.py）行数偏大，但反映了业务的真实复杂度。最需要立即处理的是几个代码重复点（`_extract_json`、user context、工具注册）和 `StreamingStoryAgent` 的流程分叉。整体来说，这是一个设计清晰的、领域驱动的、务实的单人项目架构。
