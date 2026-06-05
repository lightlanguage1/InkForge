# InkForge

**LLM 驱动的中文长篇小说涌现式生成系统**

InkForge 通过自治 Agent 逐幕规划、写作、评估、提交，让叙事结构在迭代中自然涌现，而非预设大纲。灵感源自作者此前的 [NovelWriter](https://github.com/EdwardAThomson/NovelWriter) 项目，但 InkForge 强调涌现优于规划。

## 视频介绍

- [InkForge: The Future of Story Generation?](https://youtu.be/vIBRLavyxbs)

## 功能特性

- 🤖 **Agent 自治架构** — LLM 驱动的 Agent 通过 10 个注册工具自主决策
- 🌐 **Web 前端** — React 18 + TypeScript + Vite，深色/浅色主题，侧边栏导航
- 👤 **用户系统** — 注册/登录/密码重置，邀请码，管理员面板，日志查看
- 📡 **SSE 流式生成** — 实时显示 Pipeline 各阶段（规划→写作→评估→记忆→定稿）
- 📖 **深度 POV 写作** — 严格视点规范，双模型混跑（写作/评估分派不同 LLM）
- 🧠 **演化记忆系统** — 9 种实体类型（角色/地点/场景/线索/世界观/阵营/关系/节拍/存档），随故事推进动态更新
- 🎯 **情节节拍** — Plot-First 模式，LLM 生成节拍 → 执行 → 语义验证
- ⚡ **张力追踪** — 自动评估每幕张力（0-10 分）
- 🔍 **语义搜索** — ChromaDB 向量索引，跨实体自然语言检索
- 🎨 **角色肖像** — 点云自由生成 + 硅基流动 API
- 📝 **设定导入** — 粘贴 MD/TXT 文档，LLM 识别角色/地点/阵营，预览确认后导入
- 💾 **存档系统** — 自动存档（每 3 幕）+ 手动存档（时间戳），支持回滚恢复
- 🌳 **时间线** — SVG 大树视图，主干+分支，点击节点查看详情/回滚
- 📚 **手稿编译** — 导出完整 Markdown
- 📊 **写作技能** — 从已有小说提取风格/模式，注入到新项目
- 🐳 **Docker 部署** — docker compose 一键启动，Nginx 反向代理

## 快速开始

### 零配置启动（推荐）

```bash
# Windows: 双击 start.bat
# macOS/Linux:
chmod +x start.sh && ./start.sh
```

脚本自动完成：检查 Python → 创建虚拟环境 → 安装依赖 → 启动。选择一个后端即可开始。

### 手动安装

```bash
git clone https://github.com/lightlanguage1/InkForge.git
cd InkForge

# 安装
pip install -e .

# 启动 Web 界面
novel serve

# 或直接用 CLI
novel new 我的故事
novel tick
```

### 配置 LLM 后端

至少配置一个 API Key（复制 `.env.example` 为 `.env` 填入），或使用本地 Ollama：

```bash
# DeepSeek（推荐，性价比最高）
export DEEPSEEK_API_KEY=sk-your-key

# 或 Ollama 本地模型（免费，无需 API Key）
ollama pull qwen3:8b
novel tick --llm-backend ollama --llm-model qwen3:8b
```

### 创建第一部小说

```bash
# 推荐：交互式创建（引导填写类型/背景/主角/基调等）
novel new 我的故事 --dir work/novels

# 跳过向导，创建空项目
novel new 我的故事 --dir work/novels --no-interactive

# 从 YAML 文件加载设定
novel new 我的故事 --foundation foundation.yaml

# 命令行参数直接指定
novel new 我的故事 \
  --genre "科幻" \
  --premise "一名孤独的工程师发现了一个外星信号" \
  --protagonist "好奇心强、技术精湛但孤僻" \
  --setting "近未来火星殖民地" \
  --tone "沉思、神秘"

# 生成第一幕
cd work/novels/我的故事_*
novel tick

# 从任意位置指定项目生成
novel tick --project work/novels/我的故事_a1b2c3d4

# 查看项目状态
novel status

# 查看目标层级
novel goals

# 连续生成多幕（自动存档）
novel run --n 10 --checkpoint-interval 10

# 回到最近项目
novel resume

# 查看创建的内容
novel list characters
novel list locations
novel list scenes
novel list loops

# 深入查看角色
novel inspect --id C0

# 编译手稿
novel compile --output draft.md

# 指定 LLM 后端
novel tick --llm-backend api --llm-model deepseek-chat
novel tick --llm-backend api --llm-model gpt-5.1
novel tick --llm-backend api --llm-model claude-4.5
novel tick --llm-backend gemini-cli --llm-model gemini-2.5-pro
novel tick --llm-backend claude-cli
novel tick --llm-backend ollama --llm-model qwen3:8b

# 保存发送给 LLM 的 prompt（调试用）
novel tick --save-prompts

# 注入场景方向指导
novel tick --notes "本幕描写两位主角在月光下的温泉中互诉衷肠"
```

## 工作原理

每次 Tick 生成一幕场景，完整管线（SSE 流式推送各阶段进度）：

```
第 0 幕（两阶段初始化）
├── 阶段一：生成实体（角色、地点）→ 实体先于场景存在
└── 阶段二：实体 ID 写入 Plan → 写场景正文

第 N 幕（标准管线）
├── Plan      — 上下文构建 → LLM 生成 Plan JSON → 校验 → 工具强制执行
├── Write     — Writer 上下文 → 生成正文 → 拒止回落 → 润色
├── Eval      — POV 检测 → 连续性检查 → QA 指标 → 未通过则重写
├── Commit    — 持久化场景 → 张力 0-10 → 节拍语义验证
├── Memory    — 事实提取 → 实体更新 → 世界观提取 → 冲突检测
├── Finalize  — 线索推进 → 支线审计 → 目标浮现 → 自动存档
└── Complete  — 返回结果 → 前端刷新
```

### 记忆系统

每个项目的 `memory/` 目录维护：

| 实体 | 存储位置 | 内容 |
|------|---------|------|
| 角色 | `memory/characters/C*.json` | 名字/性格/身体特征/当前状态(情绪/位置/目标)/关系/出场记录 |
| 地点 | `memory/locations/L*.json` | 名称/类型/氛围/感官细节/特征/当前状态 |
| 场景 | `memory/scenes/S*.json` | 标题/摘要/字数/张力/POV角色/关键事件 |
| 开放线索 | `memory/open_loops.json` | 描述/重要性/状态/关联角色/提及次数 |
| 世界观 | `memory/lore.json` | 规则/事实/约束/类型/来源场景/冲突检测 |
| 势力 | `memory/factions/F*.json` | 名称/组织类型/目标/影响力/立场 |
| 向量索引 | ChromaDB | 场景摘要 + 世界观语义搜索 |

## 项目结构

```
InkForge/
├── novel_agent/              # 后端核心
│   ├── agent/                # Agent 引擎（Tick 管线/写作/评估/提取）
│   │   ├── agent.py                  # StoryAgent 主编排器
│   │   ├── streaming_agent.py        # SSE 流式 Agent
│   │   ├── context.py                # ContextBuilder — Planner 上下文
│   │   ├── writer_context.py         # WriterContextBuilder — Writer 上下文
│   │   ├── writer.py                 # SceneWriter — 写作+拒止回落+润色
│   │   ├── evaluator.py              # SceneEvaluator — POV/连续性+QA
│   │   ├── prompts.py                # System Prompt + 模板加载
│   │   ├── schemas.py                # Plan JSON 校验
│   │   ├── runtime.py                # PlanExecutor — 工具调用执行
│   │   ├── scene_committer.py        # 场景提交
│   │   ├── tension_evaluator.py      # 张力评估
│   │   ├── plan_manager.py           # 计划持久化
│   │   ├── fact_extractor.py         # 事实提取
│   │   ├── entity_updater.py         # 事实→实体变更
│   │   ├── lore_extractor.py         # 世界观提取
│   │   ├── lore_contradiction_detector.py  # 设定冲突检测
│   │   └── character_detector.py     # 新角色检测
│   ├── memory/               # 持久化与向量检索
│   │   ├── manager.py                 # MemoryManager — JSON CRUD
│   │   ├── entities.py                # 数据类定义（9 个实体）
│   │   ├── vector_store.py            # ChromaDB 向量索引 + 运行时自愈
│   │   ├── update.py                  # 场景后处理管道入口
│   │   ├── summarizer.py              # 摘要生成
│   │   ├── checkpoint.py              # 项目存档
│   │   └── thread_manager.py          # 支线管理器
│   ├── plot/                 # 情节节拍管理
│   │   └── manager.py                 # PlotOutlineManager — 节拍CRUD+LLM生成
│   ├── tools/                # LLM 后端 + 工具注册
│   │   ├── registry.py                # ToolRegistry — 工具注册表
│   │   ├── memory_tools.py            # 10 个工具实现
│   │   ├── name_generator.py          # 随机中文名生成器
│   │   ├── provider.py                # LLMProvider — generate/chat 封装
│   │   ├── router.py                  # ModelRouter — 按任务路由模型
│   │   ├── multi_provider_llm.py      # 多供应商 API 注册表
│   │   ├── llm_interface.py           # 多后端统一入口
│   │   ├── ollama_stream.py           # Ollama 流式
│   │   └── llm_pool.py                # LLM 连接池
│   ├── user/                 # 用户认证
│   │   ├── db.py                      # SQLite 用户库（注册/登录/管理）
│   │   ├── auth.py                    # pbkdf2 密码哈希 + JWT
│   │   └── middleware.py              # FastAPI 认证中间件
│   ├── api/                  # REST API
│   │   ├── server.py                  # FastAPI 应用入口
│   │   ├── deps.py                    # 依赖注入（get_current_user/require_admin）
│   │   └── routers/
│   │       ├── auth.py                # 注册/登录/重置密码
│   │       ├── admin.py               # 管理员面板（用户/邀请码/统计/日志）
│   │       ├── projects.py            # 项目 CRUD
│   │       ├── entities.py            # 角色/地点/场景/线索/势力/关系/导入
│   │       ├── plot.py                # 节拍管理
│   │       ├── status.py              # 状态/目标/世界观
│   │       └── portrait.py            # 角色肖像生成
│   ├── skill/                # 写作技能系统
│   │   ├── importer.py                # 小说→SKILL.yaml
│   │   ├── injector.py                # SKILL→写作上下文注入
│   │   ├── models.py                  # 数据类
│   │   └── store.py                   # YAML 持久化
│   ├── engine/               # 常驻进程引擎
│   │   ├── core.py                    # EngineCore
│   │   └── project_manager.py         # 项目管理器
│   ├── reference/            # 外部参考小说索引
│   │   └── indexer.py                 # 分块+向量搜索
│   ├── cli/                  # 命令行界面
│   │   ├── main.py                    # 命令注册
│   │   └── commands/                  # 各命令实现
│   ├── configs/              # 配置
│   │   ├── config.py                  # 全局配置管理
│   │   ├── constants.py               # 魔法数字
│   │   └── api_keys.py                # API Key 解析
│   ├── data/                 # 静态数据
│   │   ├── names/                     # 中文姓名库
│   │   └── templates/                 # Prompt 模板（可热更新）
│   └── utils/                # 工具函数
├── frontend/                 # React 18 前端
│   ├── src/
│   │   ├── pages/                    # 页面组件
│   │   │   ├── Dashboard.tsx         #   项目仪表盘
│   │   │   ├── Overview.tsx          #   项目概览
│   │   │   ├── Writing.tsx           #   写作（SSE 流式生成+导入+重置）
│   │   │   ├── Read.tsx              #   阅读
│   │   │   ├── Characters.tsx        #   角色管理
│   │   │   ├── Locations.tsx         #   地点管理
│   │   │   ├── Scenes.tsx            #   场景列表
│   │   │   ├── Loops.tsx             #   线索管理
│   │   │   ├── Factions.tsx          #   势力管理
│   │   │   ├── Relationships.tsx     #   关系图谱
│   │   │   ├── Goals.tsx             #   目标层级
│   │   │   ├── Lore.tsx              #   世界观
│   │   │   ├── Plot.tsx              #   节拍管理
│   │   │   ├── Checkpoints.tsx       #   存档管理
│   │   │   ├── Timeline.tsx          #   🌳 时间线大树
│   │   │   ├── Skills.tsx            #   写作技能
│   │   │   ├── References.tsx        #   参考小说
│   │   │   ├── Compile.tsx           #   手稿编译
│   │   │   ├── ProtagonistSettings.tsx # 主角设定
│   │   │   ├── AdminPage.tsx         #   管理员面板
│   │   │   └── ProjectLayout.tsx     #   项目布局（侧边栏+Outlet）
│   │   ├── components/               # UI 组件
│   │   │   ├── Sidebar.tsx           #   侧边栏导航
│   │   │   ├── LoginGate.tsx         #   登录/注册门禁
│   │   │   ├── NewProjectModal.tsx   #   新建项目
│   │   │   ├── ImportModal.tsx       #   设定导入
│   │   │   ├── WritingOutput.tsx     #   流式输出显示
│   │   │   ├── GenerationContext.tsx #   生成状态管理
│   │   │   ├── PageHelp.tsx          #   页面帮助提示
│   │   │   ├── ThemeContext.tsx      #   主题切换
│   │   │   └── ui/                   #   基础组件（Card/Modal/Button/Spinner…）
│   │   ├── api/                      # API 客户端
│   │   │   ├── client.ts             #   HTTP 客户端（Bearer 认证）
│   │   │   ├── entities.ts           #   实体 CRUD
│   │   │   ├── checkpoints.ts        #   存档 API
│   │   │   ├── projects.ts           #   项目 API
│   │   │   ├── status.ts             #   状态/世界观 API
│   │   │   ├── plot.ts               #   节拍 API
│   │   │   ├── generation.ts         #   生成/SSE API
│   │   │   ├── compile.ts            #   编译 API
│   │   │   ├── references.ts         #   参考小说 API
│   │   │   └── skills.ts             #   技能 API
│   │   └── types/                    # TypeScript 类型
│   └── dist/                         # Vite 构建产物
├── docker-compose.yml
├── Dockerfile
├── nginx.conf                 # Nginx 反向代理配置
├── deploy.ps1                 # 部署脚本
├── DEPLOY.md                  # 部署文档
├── docs/                      # 设计文档
├── examples/                  # 示例项目
└── scripts/                   # 辅助脚本
```

## CLI 命令参考

### 项目生命周期

```bash
novel new <名称>                              # 创建新项目（交互式向导）
novel new <名称> --no-interactive             # 创建空项目
novel new <名称> --foundation <yaml文件>       # 从YAML加载设定
novel recent                                  # 列出最近项目
novel resume                                  # 恢复最近项目
novel resume --uuid <uuid>                    # 按UUID恢复
```

### 故事生成

```bash
novel tick                                    # 运行一幕
novel tick --notes "场景方向指导"             # 注入方向指导
novel tick --save-prompts                     # 保存prompt到文件
novel run --n 10                              # 连续运行10幕
novel run --n 10 --checkpoint-interval 5      # 每5幕存档
novel plan                                    # 预览下一次计划（不执行）
```

### 状态查看

```bash
novel status                                  # 项目仪表盘
novel list characters                         # 列出角色（-v 详细信息）
novel list locations                          # 列出地点
novel list scenes                             # 列出场景（含张力）
novel list loops                              # 列出开放线索
novel list factions                           # 列出势力
novel inspect --id C0                         # 查看角色详情（--raw 原始JSON）
novel inspect --id L0                         # 查看地点详情
novel goals                                   # 目标层级+进度条
novel lore                                    # 世界观规则浏览
novel lore --group-by type                    # 按类型分组
novel lore --category magic --importance critical  # 过滤
novel lore --stats                            # 统计概览
```

### 情节管理

```bash
novel plot status                             # 节拍状态总览
novel plot status --detailed                  # 节拍详情列表
novel plot next                               # 下一待执行节拍
novel plot generate --count 5                 # LLM生成5个新节拍
novel plot clear                              # 清空所有节拍
```

### 编译输出

```bash
novel compile --output draft.md               # 编译Markdown手稿
novel compile --format html --output manuscript.html  # HTML格式
novel compile --format prose --output story.txt      # 纯文本
novel compile --scenes 1-10                   # 场景范围筛选
novel summarize                               # 生成全文摘要
novel titles --count 15                       # LLM生成书名建议
```

### 存档管理

```bash
novel checkpoint create -m "大转折前"         # 创建存档
novel checkpoint list                         # 列出所有存档
novel checkpoint restore --id checkpoint_tick_010  # 恢复存档
novel checkpoint delete --id checkpoint_tick_005    # 删除存档
```

### 技能管理

```bash
novel skill import <小说文件> --name "名称"   # 导入小说提取写作技能
novel skill list                               # 列出已导入技能
novel skill apply <slug> --mode reference      # 注入技能到项目
novel skill apply <slug> --mode full           # 完整模式（含例句）
novel skill delete <slug>                      # 删除技能
```

### LLM 后端切换

```bash
novel tick --llm-backend codex                           # Codex CLI（默认）
novel tick --llm-backend api --llm-model deepseek-chat   # DeepSeek
novel tick --llm-backend api --llm-model gpt-5.1         # OpenAI
novel tick --llm-backend api --llm-model claude-4.5      # Claude
novel tick --llm-backend gemini-cli --llm-model gemini-2.5-pro  # Gemini CLI
novel tick --llm-backend claude-cli                      # Claude Code CLI
novel tick --llm-backend ollama --llm-model qwen3:8b     # Ollama本地
```

### 服务与其它

```bash
novel serve                                    # 启动HTTP服务（默认8221端口）
novel serve --port 9000                        # 指定端口
```

## 配置

### 全局配置

`~/.inkforge/config.yaml`：

```yaml
llm:
  backend: api                   # codex | api | gemini-cli | claude-cli | ollama
  model: deepseek-chat           # 模型名
  temperature: 0.7

router:
  enabled: true                  # 按任务路由模型（默认开启）
  writer_model: deepseek-chat    # 写作模型
  writer_backend: api
  planner_model: deepseek-chat   # 规划模型
  planner_backend: api
  extractor_model: local-llama   # 抽取模型（可走本地）
  extractor_backend: api

generation:
  use_plot_first: false          # Plot-First 模式（默认关闭）
  beat_mode: soft_hint           # off | soft_hint | guided | strict
  enable_tension_tracking: true
  enable_lore_tracking: true
  enable_fact_extraction: true
  auto_detect_characters: true
  content_safety_fallback: true  # API拒止自动回落
```

### 项目级配置

每个项目目录下有 `config.yaml`，覆盖全局配置。

### API 环境变量

```text
OPENAI_API_KEY      # OpenAI GPT-5/5.1
CLAUDE_API_KEY      # Anthropic Claude 4.5
GEMINI_API_KEY      # Google Gemini 2.5 Pro
DEEPSEEK_API_KEY    # DeepSeek
INKFORGE_API_KEY # 通用 Key（所有供应商共享）
OLLAMA_BASE_URL     # Ollama 地址（默认 http://localhost:11434）
LOCAL_LLM_URL       # 本地 llama-server 地址（默认 http://127.0.0.1:8080/v1）
```

## 开发状态

目前是一个成熟可用的端到端系统：

- **Agent 层**：四阶段 Tick 循环，两阶段初始化，双模型混跑
- **记忆层**：9 种实体类型，JSON 持久化 + ChromaDB 向量索引
- **评估层**：POV 检测（快速路径 + LLM）、连续性检查、QA 指标
- **Plot 层**：涌现式节拍生成，三种执行模式（提示/引导/强制）
- **Skill 层**：小说→风格提取→注入，6 层角色去重防线
- **API 层**：FastAPI 服务，12 端点 + SSE 流式
- **CLI 层**：25+ 命令覆盖完整写作工作流

详细设计文档见 `docs/ARCHITECTURE.md`。

## 设计哲学

- **涌现优于规划** — 发现式写作 + 结构化推理驱动
- **深度 POV 真实感** — 一切通过角色感知过滤
- **记忆演化** — 实体随故事推进自然生长变化
- **工具自治** — LLM 根据故事需求自主决定使用哪些工具
- **确定性兜底** — 所有关键决策点都尽量用确定性逻辑（角色去重、POV 快速路径、拒止检测），LLM 只负责需要创造力的环节

## 开源协议

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 灵感源自作者此前的 [NovelWriter](https://github.com/EdwardAThomson/NovelWriter) 项目
- 后端支持：Codex CLI、OpenAI、Anthropic Claude、Google Gemini、DeepSeek、Ollama
- 使用 Typer（CLI）、ChromaDB（向量存储）、FastAPI（HTTP 服务）

---

**作者：Edward A. Thomson**  
[GitHub](https://github.com/lightlanguage1/InkForge)
