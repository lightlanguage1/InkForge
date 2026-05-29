# InkForge 接口文档（API Reference）

> 版本：基于当前代码库  
> 更新日期：2026-04-17

---

## 目录

1. [CLI 命令接口](#1-cli-命令接口)
2. [Agent 工具接口（Tool API）](#2-agent-工具接口)
3. [内存管理接口（Memory API）](#3-内存管理接口)
4. [LLM 后端接口](#4-llm-后端接口)
5. [配置系统](#5-配置系统)
6. [数据模型（Data Models）](#6-数据模型)
7. [项目文件结构](#7-项目文件结构)

---

## 1. CLI 命令接口

所有命令通过 `python -m novel_agent.cli.main <命令>` 或安装后的 `novel <命令>` 调用。

---

### `novel new` — 创建新项目

```
novel new <name> [OPTIONS]
```

| 参数/选项 | 类型 | 必填 | 默认 | 说明 |
|-----------|------|------|------|------|
| `name` | Argument | ✅ | — | 小说名称 |
| `--dir / -d` | Option | ❌ | `~/novels` | 项目存放目录 |
| `--interactive / --no-interactive` | Flag | ❌ | `True` | 使用交互式向导 |
| `--foundation / -f` | Option | ❌ | — | 从 YAML 文件加载基础设定 |
| `--genre` | Option | ❌ | — | 故事类型（如：仙侠、科幻） |
| `--premise` | Option | ❌ | — | 故事前提（1-2句） |
| `--protagonist` | Option | ❌ | — | 主角性格/定位 |
| `--setting` | Option | ❌ | — | 故事背景（时代/地点/世界观） |
| `--tone` | Option | ❌ | — | 基调（氛围/风格） |
| `--themes` | Option | ❌ | — | 主题，逗号分隔 |

**输出**：项目目录路径、项目 ID

**创建的文件结构**：
```
novels/<name>_<uuid8>/
  state.json、config.yaml、memory/、scenes/、plans/
```

---

### `novel tick` — 执行单幕生成

```
novel tick [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--save-prompts` | Flag | ❌ | `False` | 保存提示词到 `prompts/` 目录 |
| `--llm-backend` | Option | ❌ | 读 config | `ollama\|codex\|api\|gemini-cli\|claude-cli` |
| `--llm-model` | Option | ❌ | 读 config | 模型名称 |
| `--codex-bin` | Option | ❌ | `codex` | Codex 二进制路径 |

**返回信息**：
```
✅ 第 N 幕生成完成！
   📋 计划：plans/plan_NNN.json
   📝 场景：scenes/scene_NNN.md
   📊 字数：<n>
   🔧 动作：<n>
```

---

### `novel run` — 连续生成多幕

```
novel run [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--n / -n` | Option | ❌ | `5` | 要生成的幕数 |
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--checkpoint-interval` | Option | ❌ | `10` | 每 N 幕自动存档 |
| `--llm-backend` | Option | ❌ | 读 config | LLM 后端 |
| `--llm-model` | Option | ❌ | 读 config | 模型名称 |
| `--codex-bin` | Option | ❌ | `codex` | Codex 二进制路径 |

---

### `novel status` — 查看项目状态

```
novel status [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--json` | Flag | ❌ | `False` | 输出为 JSON |

**JSON 输出格式**：
```json
{
  "novel_name": "仙剑奇侠传",
  "current_tick": 10,
  "active_character": "C000",
  "scenes_written": 10,
  "characters": 5,
  "locations": 3,
  "open_loops": 2,
  "tension_history": [
    {"tick": 8, "level": 6, "category": "action"}
  ],
  "story_foundation": {
    "genre": "仙侠",
    "setting": "1023年 仙侠大陆"
  }
}
```

---

### `novel list` — 列出实体

```
novel list <entity_type> [OPTIONS]
```

| 参数/选项 | 类型 | 必填 | 默认 | 说明 |
|-----------|------|------|------|------|
| `entity_type` | Argument | ✅ | — | `characters\|locations\|loops\|scenes\|factions` |
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--verbose / -v` | Flag | ❌ | `False` | 显示详细信息 |
| `--json` | Flag | ❌ | `False` | JSON 输出 |

**示例**：
```bash
novel list characters
novel list locations --verbose
novel list loops --json
```

---

### `novel inspect` — 查看实体详情

```
novel inspect [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--id` | Option | ❌ | — | 实体 ID（C000、L0、S001 等） |
| `--file` | Option | ❌ | — | 直接文件路径 |
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--raw` | Flag | ❌ | `False` | 输出原始 JSON |
| `--history-limit` | Option | ❌ | `5` | 显示最后 N 条历史 |

**示例**：
```bash
novel inspect --id C000
novel inspect --id L0 --raw
```

---

### `novel goals` — 查看目标层级

```
novel goals [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--json` | Flag | ❌ | `False` | JSON 输出 |

**输出内容**：故事主要目标、次要目标、主角即时/弧线/故事目标、已完成目标

---

### `novel lore` — 查看世界观规则

```
novel lore [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--group-by / -g` | Option | ❌ | `category` | `category\|type\|none` |
| `--category / -c` | Option | ❌ | — | 按类别筛选（magic、politics 等） |
| `--type / -t` | Option | ❌ | — | `rule\|fact\|constraint\|capability\|limitation` |
| `--importance / -i` | Option | ❌ | — | `critical\|important\|normal\|minor` |
| `--stats / -s` | Flag | ❌ | `False` | 仅显示统计信息 |
| `--json` | Flag | ❌ | `False` | JSON 输出 |

---

### `novel compile` — 编译手稿

```
novel compile [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--output / -o` | Option | ❌ | `manuscript.md` | 输出文件路径 |
| `--format` | Option | ❌ | `markdown` | `markdown\|html\|prose\|txt` |
| `--include-metadata / --no-metadata` | Flag | ❌ | `True` | 包含附录 |
| `--scenes` | Option | ❌ | 全部 | 场景范围，如 `1-10` 或 `5,7,9` |

**格式说明**：
- `markdown`：带标题和元数据附录
- `html`：完整可打印 HTML 文档（含样式）
- `prose` / `txt`：纯文本，无标题，场景间用 `* * *` 分隔

**示例**：
```bash
novel compile --output 小说.txt --format txt
novel compile --output manuscript.html --format html --scenes 1-20
```

---

### `novel plot` — 情节管理

#### `novel plot status`
```
novel plot status [--project/-p PATH] [--detailed/-d]
```
显示情节节拍列表，包含执行状态（pending / executing / completed / skipped）

#### `novel plot next`
```
novel plot next [--project/-p PATH]
```
显示下一个待执行的情节节拍

#### `novel plot generate`
```
novel plot generate [--count/-n N] [--project/-p PATH]
```
使用 LLM 生成 N 个情节节拍并追加到大纲（默认 N=5）

#### `novel plot clear`
```
novel plot clear [--project/-p PATH] [--yes/-y]
```
清空情节大纲（生成时会自动重建）

---

### `novel plan` — 预览下一幕计划

```
novel plan [OPTIONS]
```

| 选项 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `--project / -p` | Option | ❌ | 当前目录 | 项目路径 |
| `--save` | Option | ❌ | — | 保存计划到文件 |
| `--verbose / -v` | Flag | ❌ | `False` | 显示完整上下文 |

**计划 JSON 格式**：
```json
{
  "rationale": "为什么这个计划合理",
  "scene_intention": "这个场景要发生什么",
  "key_change": "场景结束后根本性的变化",
  "pov_character": "C000",
  "target_location": "L0",
  "actions": [
    {"tool": "memory.search", "args": {"query": "..."}, "reason": "..."},
    {"tool": "character.generate", "args": {"name": "...", "role": "..."}}
  ],
  "expected_outcomes": ["结果1", "结果2"]
}
```

---

### `novel checkpoint` — 存档管理

```
novel checkpoint <action> [OPTIONS]
```

| 动作 | 说明 |
|------|------|
| `create` | 创建当前状态快照 |
| `list` | 列出所有存档 |
| `restore --id <id>` | 恢复到指定存档（自动备份当前状态） |
| `delete --id <id>` | 删除指定存档 |

**示例**：
```bash
novel checkpoint create --message "第一章完成"
novel checkpoint list
novel checkpoint restore --id checkpoint_tick_010
novel checkpoint delete --id checkpoint_tick_005
```

---

### `novel recent` — 最近项目

```
novel recent [--limit/-n N]
```
显示最近访问的 N 个项目（默认 10）

---

### `novel resume` — 恢复最近项目

```
novel resume [--n/-n TICKS] [--uuid/-u UUID]
```

| 选项 | 说明 |
|------|------|
| `--n` | 自动继续生成的幕数（默认 1） |
| `--uuid` | 按 UUID 恢复特定项目 |

---

### `novel titles` — 生成标题建议

```
novel titles [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--project / -p` | 项目路径 |
| `--count / -n` | 生成数量（默认 10） |
| `--output / -o` | 输出到文件 |

---

### `novel summarize` — 生成摘要文档

```
novel summarize [--project/-p PATH]
```
从所有场景文件生成摘要文档。

---

## 2. Agent 工具接口

这些工具在规划器（Planner）生成的 `plan.actions` 中调用，也可通过 `ToolRegistry` 直接调用。

---

### `memory.search` — 语义搜索

```python
memory.search(
    query: str,                         # 搜索查询
    entity_type: str = None,            # characters|locations|loops（不填则全搜）
    top_k: int = 5                      # 返回结果数
) -> List[Dict]
```

**返回**：按相关性排序的实体列表（包含 id、type、内容摘要、相似度分数）

---

### `character.generate` — 创建角色

```python
character.generate(
    name: str,                          # 角色姓名（必填）
    role: str,                          # protagonist|antagonist|supporting|minor
    description: str,                   # 角色描述（必填）
    appearance: str = None,             # 外观描述
    personality_traits: list = None,    # 性格特点列表
    goals: list = None,                 # 初始目标列表
    backstory: str = None,              # 背景故事
    gender: str = None                  # 性别
) -> Dict
```

**返回**：
```json
{"character_id": "C004", "name": "林月如", "success": true}
```

**注意**：如果同名角色已存在会返回已有角色，不会重复创建。

---

### `location.generate` — 创建地点

```python
location.generate(
    name: str,                          # 地点名称（必填）
    type: str,                          # city|building|room|natural|abstract
    atmosphere: str,                    # 氛围描述（必填）
    description: str = None,            # 详细描述
    sensory_details: dict = None,       # 感官细节
    significance: str = None            # 地点的重要性
) -> Dict
```

**返回**：
```json
{"location_id": "L003", "name": "仙灵岛", "success": true}
```

---

### `relationship.create` — 创建关系

```python
relationship.create(
    character_id_1: str,                # 第一个角色 ID（必填）
    character_id_2: str,                # 第二个角色 ID（必填）
    relationship_type: str,             # friend|enemy|mentor|student|rival|family|lover
    description: str,                   # 关系描述（必填）
    perspective_1: str = None,          # 角色1视角描述
    perspective_2: str = None,          # 角色2视角描述
    intensity: int = 5                  # 关系强度 0-10
) -> Dict
```

**返回**：
```json
{"relationship_id": "R001", "success": true}
```

---

### `relationship.update` — 更新关系

```python
relationship.update(
    character_id_1: str,                # 第一个角色 ID（必填）
    character_id_2: str,                # 第二个角色 ID（必填）
    new_status: str = None,             # 新状态描述
    event_description: str = None,      # 触发变化的事件
    intensity_delta: int = None,        # 强度变化（+/-）
    tick: int = None                    # 自动注入
) -> Dict
```

---

### `relationship.query` — 查询关系

```python
relationship.query(
    character_id: str                   # 角色 ID（必填）
) -> Dict
```

**返回**：该角色的所有关系列表

---

### `faction.generate` — 创建派系/组织

```python
faction.generate(
    name: str,                          # 组织名称（必填）
    org_type: str,                      # corporate|government|guild|criminal|religious|military
    summary: str,                       # 组织概述（必填）
    objectives: list = None,            # 目标列表
    methods: list = None,               # 行动方式
    importance: str = "medium"          # low|medium|high|critical
) -> Dict
```

**返回**：
```json
{"faction_id": "F000", "name": "拜月教", "success": true}
```

---

### `faction.update` — 更新派系

```python
faction.update(
    id: str,                            # 派系 ID（必填，必须是已存在的真实 ID）
    summary: str = None,
    objectives: list = None,
    stance_change: dict = None          # {"character_id": "hostile"}
) -> Dict
```

⚠️ **注意**：`id` 必须是 `faction.generate` 返回的真实 ID，不可自行编造。

---

### `faction.query` — 查询派系

```python
faction.query(
    name: str = None,                   # 按名称搜索
    org_type: str = None                # 按类型筛选
) -> List[Dict]
```

---

## 3. 内存管理接口

`MemoryManager` 在 `novel_agent/memory/manager.py`，可通过 `agent.memory` 访问。

---

### 角色操作

```python
manager.load_character(character_id: str) -> Optional[Character]
manager.save_character(character: Character) -> None
manager.list_characters() -> List[str]              # 返回 ID 列表
manager.get_character_by_name(name: str) -> Optional[Character]
manager.get_all_characters() -> List[Character]
manager.get_active_character() -> Optional[str]     # 返回当前 POV 角色 ID
manager.set_active_character(character_id: str) -> None
manager.generate_id(entity_type: str) -> str        # 生成下一个 ID（C004 等）
```

---

### 地点操作

```python
manager.load_location(location_id: str) -> Optional[Location]
manager.save_location(location: Location) -> None
manager.list_locations() -> List[str]
manager.get_all_locations() -> List[Location]
```

---

### 场景操作

```python
manager.load_scene(scene_id: str) -> Optional[Scene]
manager.save_scene(scene: Scene) -> None
manager.list_scenes() -> List[str]                  # 按顺序排列
manager.save_scene_qa(scene_id, tick, eval_result) -> None
```

---

### 开放线索操作

```python
manager.add_open_loop(loop_data: dict) -> OpenLoop
manager.load_open_loops() -> List[OpenLoop]
manager.get_open_loops() -> List[OpenLoop]           # 仅未解决的
manager.resolve_loop(loop_id: str, resolved_in_scene: str) -> None
```

---

### 世界观操作

```python
manager.save_lore(lore: Lore) -> None
manager.load_all_lore() -> List[Lore]
manager.get_lore_by_category(category: str) -> List[Lore]
manager.get_lore_by_importance(importance: str) -> List[Lore]
```

---

### 关系操作

```python
manager.create_relationship(rel_data: dict) -> Relationship
manager.get_relationships_for_character(char_id: str) -> List[Relationship]
manager.update_relationship(rel_id: str, updates: dict) -> None
manager.save_relationships(relationships: dict) -> None
```

---

### 派系操作

```python
manager.create_faction(faction_data: dict) -> Faction
manager.load_faction(faction_id: str) -> Optional[Faction]
manager.list_factions() -> List[str]
manager.save_faction(faction: Faction) -> None
```

---

### 检查点操作

```python
# 在 novel_agent/memory/checkpoint.py
create_checkpoint(project_dir: Path, tick: int, created_by: str = "manual") -> Path
list_checkpoints(project_dir: Path) -> List[CheckpointManifest]
restore_checkpoint(project_dir: Path, checkpoint_id: str, backup_current: bool = True) -> None
delete_checkpoint(project_dir: Path, checkpoint_id: str) -> None
```

---

## 4. LLM 后端接口

所有 LLM 后端实现相同的方法签名：

```python
class LLMBackend:
    def generate(self, prompt: str, max_tokens: int = 2000) -> str
    def generate_with_retry(self, prompt: str, max_tokens: int = 2000,
                            max_retries: int = 3) -> str
```

| 后端标识 | 类 | 适用场景 |
|---------|-----|---------|
| `ollama` | `OllamaInterface` | 本地模型（qwen3、llama 等） |
| `codex` | `CodexInterface` | Codex CLI |
| `api` | `MultiProviderInterface` | OpenAI / Anthropic / Google API |
| `gemini-cli` | `GeminiCliInterface` | Gemini CLI |
| `claude-cli` | `ClaudeCliInterface` | Claude Code CLI |

### 初始化

```python
from novel_agent.tools.llm_interface import initialize_llm

llm = initialize_llm(
    backend="ollama",       # 后端标识
    model="qwen3:8b",       # 模型名
    codex_bin="codex"       # 仅 codex 后端使用
)
```

---

## 5. 配置系统

### config.yaml 完整字段表

```yaml
llm:
  backend: "ollama"                   # ollama|codex|api|gemini-cli|claude-cli
  codex_bin_path: "codex"
  model: "qwen3:8b"
  planner_max_tokens: 1500            # 规划器 token 限制
  writer_max_tokens: 4000             # 写作器 token 限制
  extractor_max_tokens: 2000          # 提取器 token 限制
  timeout: 120                        # 请求超时（秒）

generation:
  # 上下文窗口
  recent_scenes_count: 3              # 上下文中的最近场景数
  full_text_scenes_count: 2           # 作为完整文本的场景数
  summary_scenes_count: 3             # 作为摘要的场景数
  include_overall_summary: true

  # 功能开关
  enable_fact_extraction: true
  enable_entity_updates: true
  enable_tension_tracking: true       # Phase 7A.3
  enable_lore_tracking: true          # Phase 7A.4
  use_multi_stage_planner: true       # Phase 7A.5

  # 角色检测 (Phase 6)
  auto_detect_characters: true
  auto_create_minor_characters: false
  prompt_for_character_creation: true

  # 字数目标
  target_word_count_min: null         # 最小字数（null=不限）
  target_word_count_max: null         # 最大字数（null=不限）

  # 情节优先模式
  use_plot_first: false
  plot_first_start_tick: 2            # 从第几幕开始使用情节节拍
  plot_beats_ahead: 5                 # 一次生成节拍数
  plot_regeneration_threshold: 2      # 待执行节拍<此数时重新生成
  verify_beat_execution: true         # 验证节拍是否被执行
  allow_beat_skip: false              # 允许跳过未完成的节拍
  fallback_to_reactive: false         # 节拍失败时回退到反应模式

lore:
  contradiction_threshold: 0.5       # 矛盾检测相似度阈值

paths:
  novels_dir: "~/novels"
```

### state.json 完整结构

```json
{
  "novel_name": "小说名称",
  "project_id": "abc12345",
  "current_tick": 10,
  "active_character": "C000",
  "created_at": "2024-01-15T10:00:00",
  "last_updated": "2024-01-20T15:30:00Z",
  "story_foundation": {
    "genre": "仙侠修真",
    "premise": "故事前提描述...",
    "protagonist_archetype": "主角性格描述",
    "setting": "1023年 仙侠大陆",
    "tone": "仙侠",
    "themes": ["仙侠", "爱情"],
    "primary_goal": null
  },
  "story_goals": {
    "primary": null,
    "secondary": [],
    "promotion_candidates": [],
    "promotion_tick": null
  }
}
```

---

## 6. 数据模型

### Character

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | C000、C001... |
| `first_name` | `str` | 名 |
| `family_name` | `str` | 姓 |
| `title` | `str` | 头衔（可选） |
| `role` | `str` | protagonist / antagonist / supporting / minor |
| `description` | `str` | 角色描述 |
| `physical_traits` | `PhysicalTraits` | age, appearance, distinctive_features |
| `personality` | `Personality` | core_traits, fears, desires, flaws |
| `current_state` | `CurrentState` | location_id, emotional_state, goals, inventory |
| `relationships` | `List[Relationship]` | 关系列表 |
| `immediate_goals` | `List[str]` | 即时目标 |
| `arc_goal` | `str` | 角色发展弧目标 |
| `story_goal` | `str` | 与故事主目标的关联 |
| `goal_progress` | `Dict[str, float]` | 目标进度 0.0-1.0 |
| `backstory` | `str` | 背景故事 |
| `history` | `List[HistoryEntry]` | 历史记录 |

### Location

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | L000、L001... |
| `name` | `str` | 地点名称 |
| `type` | `str` | city / building / room / natural / abstract |
| `atmosphere` | `str` | 氛围描述 |
| `description` | `str` | 详细描述 |
| `sensory_details` | `SensoryDetails` | visual, auditory, olfactory, tactile |
| `current_state` | `LocationState` | tension_level, time_of_day, occupants |
| `connections` | `List[LocationConnection]` | 到其他地点的连接 |

### Scene

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | S000、S001... |
| `tick` | `int` | 幕号（从 0 开始） |
| `title` | `str` | 场景标题 |
| `pov_character` | `str` | POV 角色 ID |
| `location` | `str` | 地点 ID |
| `word_count` | `int` | 字数 |
| `summary` | `List[str]` | 3-5 个要点 |
| `key_events` | `List[str]` | 重要事件 |
| `characters_present` | `List[str]` | 出现角色 ID |
| `tension_level` | `int` | 张力 0-10 |
| `tension_category` | `str` | emotional / action / psychological 等 |

### OpenLoop（悬念线索）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | OL000、OL001... |
| `description` | `str` | 线索描述 |
| `category` | `str` | mystery / character / plot / world / relationship |
| `importance` | `str` | critical / important / normal / minor |
| `is_story_goal` | `bool` | 是否为故事主要目标 |
| `status` | `str` | open / resolved / abandoned |
| `created_in_scene` | `str` | 创建场景 ID |
| `resolved_in_scene` | `str` | 解决场景 ID |

### Lore（世界观规则）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | LOR000... |
| `lore_type` | `str` | rule / fact / constraint / capability / limitation |
| `category` | `str` | magic / politics / technology / biology / society 等 |
| `importance` | `str` | critical / important / normal / minor |
| `content` | `str` | 规则内容 |
| `source_scene_id` | `str` | 来源场景 |
| `tick` | `int` | 来源幕号 |
| `tags` | `List[str]` | 标签 |

### PlotBeat（情节节拍）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | PB000、PB001... |
| `description` | `str` | 节拍描述（10-20字） |
| `characters_involved` | `List[str]` | 涉及角色 ID |
| `location` | `str` | 场景地点 ID |
| `plot_threads` | `List[str]` | 相关情节线（≤3） |
| `tension_target` | `int` | 目标张力 0-10 |
| `status` | `str` | pending / executing / completed / skipped |
| `executed_in_scene` | `str` | 执行场景 ID |

---

## 7. 项目文件结构

```
novels/<name>_<uuid8>/
├── state.json                     # 项目状态（当前幕数、活跃角色等）
├── config.yaml                    # 项目配置
├── plot_outline.json              # 情节节拍大纲（启用情节优先时）
├── memory/
│   ├── characters/
│   │   ├── C000.json             # 角色实体文件
│   │   └── C001.json
│   ├── locations/
│   │   ├── L000.json             # 地点实体文件
│   │   └── L001.json
│   ├── scenes/
│   │   ├── S000.json             # 场景元数据（非正文）
│   │   └── S001.json
│   ├── factions/
│   │   └── F000.json             # 派系/组织文件
│   ├── qa/                        # 质量评估反馈
│   ├── index/                     # ChromaDB 向量索引
│   ├── open_loops.json            # 开放悬念线索列表
│   ├── relationships.json         # 角色关系图
│   ├── lore.json                  # 世界观规则库
│   └── counters.json              # ID 计数器
├── scenes/
│   ├── scene_000.md              # 第0幕完整场景文本
│   └── scene_001.md
├── plans/
│   ├── plan_000.json             # 第0幕规划 JSON
│   └── plan_001.json
├── prompts/                       # 保存的提示词（--save-prompts 时）
│   ├── planner_000.txt
│   └── writer_000.txt
├── errors/                        # 错误日志
│   └── error_5_20240115.json
└── checkpoints/                   # 存档快照
    └── checkpoint_tick_010/
        ├── memory/
        ├── scenes/
        ├── state.json
        ├── config.yaml
        └── manifest.json
```
