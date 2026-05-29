# InkForge 优化方案

## 原则

- **不改现有流水线** — 所有新增都是"外层"或"插件"，现有 tick 循环不受影响
- **一个模块做一件事** — 每个新模块职责单一、可独立测试、可单独禁用
- **配置驱动** — 新功能默认关闭，项目级 config.yaml 按需启用

---

## 一、故事结构层：Tick → Scene → Chapter → Act

### 问题

当前只有 flat tick 序列。没有"章"和"卷"的概念，长期剧情靠逐幕涌现，跨度不可控。

### 方案

新增 `novel_agent/structure/` 包，三文件：

```
structure/
  arc_planner.py     StoryArcPlanner: LLM 生成大綱
  chapter_manager.py ChapterManager: Chapter CRUD + 状态
  entities.py        Act / Chapter 数据类
```

**StoryArcPlanner**：
- 在 tick=0 之后、tick=1 之前调用一次（或 CLI `novel outline` 手动触发）
- 输入：故事基础设定 + 角色列表
- 输出：3-5 幕大纲，每幕含 3-8 章的里程碑描述
- 只规划"关键节点"，不写死细节——tick 级规划器在框架内自由发挥
- 存储为 `story_arc.json`

**ChapterManager**：
- 追踪当前 chapter 进度：哪些 scene 属于本章、本章是否完成
- 每章结束时自动触发 chapter 摘要 + 角色状态检查点
- 提供 `get_chapter_context()` 给规划器："你在第 2 卷第 7 章，本章目标是 X，距完成还有 Y 个场景"
- 存储为 `chapters.json`

**entities.py 数据结构**：
```python
@dataclass
class Chapter:
    id: str              # "CH01"
    title: str
    volume: int
    milestone: str       # 本章要达到的里程碑
    scene_ids: List[str]
    status: str          # planned | writing | completed
    summary: str

@dataclass  
class Act:
    id: str              # "ACT1"
    title: str
    theme: str           # 本幕主题
    chapter_ids: List[str]
    arc_type: str        # setup | rising | climax | falling | resolution
```

### 改动范围

| 文件 | 改动 |
|------|------|
| `structure/` (新增) | arc_planner / chapter_manager / entities |
| `agent.py` | tick 检查章边界，章末触发检查点 |
| `context.py` | 注入 chapter_context 到规划器 |
| `config.py` | `story_structure.enabled` (默认 true) |

---

## 二、可插拔质量管线

### 问题

评估器只检查 POV + 连续性。对话重复、逻辑漏洞、角色不一致、世界观矛盾都无法检测。

### 方案

将 `evaluator.py` 重构为 **插件管线**：

```
SceneEvaluator
  ├─ POVChecker         (已有)
  ├─ ContinuityChecker   (已有)
  ├─ DialogueRepeatChecker  (新增)
  ├─ PlotLogicChecker    (新增)
  └─ WorldConsistencyChecker (新增)
```

**Checker 接口**（`evaluator.py` 新增基类）：
```python
class Checker(ABC):
    name: str
    requires_llm: bool = False
    
    @abstractmethod
    def check(self, scene_text: str, context: dict) -> CheckResult:
        ...
    
    def fast_path(self, scene_text: str, context: dict) -> bool:
        """Return True if this check can be skipped (no keywords triggered)."""
        return False

@dataclass
class CheckResult:
    passed: bool
    issues: List[str]
    warnings: List[str]
```

**新增 Checker**：

| Checker | 检测方式 | LLM | 说明 |
|---------|---------|-----|------|
| DialogueRepeatChecker | 启发式 | 否 | 相同对话模式出现 3+ 次 → warning |
| PlotLogicChecker | LLM | 是 | "角色的行动是否与其已知信息一致？" |
| WorldConsistencyChecker | LLM | 是 | "场景中的世界观细节是否与已建立的 lore 矛盾？" |

**配置**：
```yaml
evaluation:
  checkers:
    pov: true
    continuity: true
    dialogue_repeat: true
    plot_logic: false      # LLM 调用，按需开启
    world_consistency: false
```

### 改动范围

| 文件 | 改动 |
|------|------|
| `evaluator.py` | 新增 Checker 基类 + 管线调度逻辑 |
| `evaluator.py` | 现有 POV/Continuity 提取为 Checker 子类 |
| `evaluator.py` | 新增 3 个 Checker |
| `config.py` | 新增 `evaluation.checkers` 配置 |

---

## 三、人物出场追踪完善

### 问题

`Scene.characters_present` 字段存在但未填充，角色出场依赖 fact_extractor 间接判断。

### 方案

**直接填充，不靠推断。**

在 `SceneCommitter.commit_scene()` 中，从 plan 和 execution_results 提取明确出场的角色：

```python
def _extract_characters_present(self, plan, execution_results, scene_text):
    appeared = set()
    # 1. POV 角色
    pov = plan.get("pov_character", "")
    if pov: appeared.add(pov)
    # 2. 对话目标中的角色
    dt = plan.get("dialogue_targets", {})
    for p in dt.get("participants", []):
        if p.startswith("C"): appeared.add(p)
    # 3. fact_extractor 更新的角色
    ...
    return list(appeared)
```

保存到 `Scene.characters_present` → 角色出场追踪改为读取 Scene 数据。

### 改动范围

| 文件 | 改动 |
|------|------|
| `scene_committer.py` | `_extract_characters_present()` 实现 |
| `entity_updater.py` | `_track_appearances()` 改为优先读 Scene 数据 |

---

## 四、人工干预点

### 问题

全自动生成，紧急情况下无法干预。

### 方案

**最小化干预机制**：三个钩子，不改流水线结构。

**钩子 1：Tick 前审批（可选）**

```yaml
generation:
  review:
    enabled: false           # 默认关闭
    mode: "plan_only"        # plan_only | scene_only | both
```

- `plan_only`：规划完计划后暂停，等待用户确认再继续写作
- CLI 显示计划摘要，用户输入 y/n/edit 来继续/跳过/修改

**钩子 2：紧急回退**

```
novel rollback --project X   # 回退到上一 tick，删除场景文件
```

实现：保存 `state.json.bak` 每 tick 前快照，回退时恢复。

**钩子 3：角色手动编辑**

```
novel character edit --project X --id C003 --field status --value deceased
```

已有 `character.update` tool，加 CLI 入口即可。

### 改动范围

| 文件 | 改动 |
|------|------|
| `cli/main.py` | `tick` 命令加 `--review` flag；新增 `rollback` 命令；新增 `character edit` 子命令 |
| `agent.py` | 钩子 1 实现（plan 后暂停等待输入） |

---

## 五、输出格式标准化

### 问题

章节标题、分卷格式由 LLM 自行决定，不统一。

### 方案

**不做后处理。在 Writer Prompt 中给出精确格式要求。**

Writer Prompt 输出格式段改为：
```
**输出格式：**
第一章标题使用 `# 第X章 章节标题`。
后续场景使用 `## 场景小标题`。
```

SceneCommitter 在保存时检查并规范化标题。

### 改动范围

| 文件 | 改动 |
|------|------|
| `writer_prompt.md` | 输出格式段精确化 |
| `scene_committer.py` | `_normalize_headers()` |

---

## 六、测试框架

### 问题

tests/ 目录被删除，零覆盖。

### 方案

**只测核心路径，不追求覆盖率。** 5-8 个集成测试即可覆盖 80% 风险。

```
tests/
  conftest.py              # fixtures: 临时项目、mock LLM
  test_tick_pipeline.py    # 完整 tick 流程（mock LLM）
  test_config.py           # 配置加载/合并/保存
  test_evaluator.py        # checker 插件管线
  test_context.py          # 状态快照构建
  test_entities.py         # 序列化/反序列化/向后兼容
```

Mock LLM 策略：用一个简单的 `MockLLM` 类，返回固定的 JSON 响应。不调真实 API。

```python
class MockLLM:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []
    def generate(self, prompt, max_tokens=2000):
        self.calls.append(prompt)
        return self.responses.pop(0) if self.responses else "{}"
```

### 改动范围

| 文件 | 改动 |
|------|------|
| `tests/` (新增) | 全部文件 |

---

## 七、CLI 增强

### 问题

CLI 简陋，无 stream 模式，无进度条。

### 方案

**轻量——只加两个功能。**

**1. `--stream` flag**（已有 `StreamingStoryAgent`，加 CLI 入口）

```
novel tick --stream   # 实时输出规划/写作/评估进度
```

**2. `novel status` 增强**（已有命令，增强输出）

显示：当前卷/章、章节进度、最近张力趋势、角色登场统计。

### 改动范围

| 文件 | 改动 |
|------|------|
| `cli/main.py` | `tick --stream` 入口；`status` 输出增强 |

---

## 八、矢量搜索利用

### 问题

ChromaDB 已集成但仅用于节拍验证。

### 方案

**两个最小化用例，不改现有逻辑。**

**1. 查重（写手后处理）**

场景生成后，搜索最相似的已存在场景。相似度 > 0.85 → 警告"本场景与 scene_005 高度相似"。

**2. 参考检索（写手上下文）**

用 scene_intention 搜索最相关的 2-3 个过往场景摘要，注入写手上下文作为"前情提要"。

### 改动范围

| 文件 | 改动 |
|------|------|
| `writer.py` | `_check_similarity()` 查重警告 |
| `writer_context.py` | `_search_relevant_scenes()` 参考检索 |

---

## 实施顺序

| 优先级 | 项目 | 依赖 | 预估 |
|--------|------|------|------|
| P0 | 故事结构层 | 无 | 2h |
| P0 | 角色出场完善 | 无 | 0.5h |
| P1 | 输出格式标准化 | 无 | 0.5h |
| P1 | 人工干预点（回退+角色编辑） | 无 | 1h |
| P1 | 测试框架 | 无 | 1.5h |
| P2 | 可插拔质量管线 | 测试框架 | 2h |
| P2 | CLI 增强 | 无 | 1h |
| P2 | 矢量搜索利用 | 无 | 1h |

总计：约 9.5 小时。每个项目独立，可分批推进。
