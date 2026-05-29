# InkForge 前端架构

> 基于实际代码探索，日期：2026-05-28。

---

## 一、分层设计

```
pages/          页面层 — 调 API、组合组件、处理交互（18 个页面）
components/     展示层 — 纯展示，props 进 JSX 出（17 个组件）
api/            端点层 — fetch 封装，按域分文件（10 个域 + client）
types/          类型层 — TS 接口，按域分文件（10 个域）
utils/          工具层 — 前端日志 → 后端转发
styles/         样式层 — CSS 变量主题令牌
```

**核心原则：** 业务逻辑在页面层，组件只负责渲染。不做 hooks 过度抽象。

---

## 二、文件树

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── docs/
│   └── ARCHITECTURE.md            # 本文档
│
└── src/
    ├── main.tsx                    # React 入口
    ├── App.tsx                     # 路由定义（18 个路由）
    ├── ThemeContext.tsx            # 主题上下文（明/暗模式）
    │
    ├── types/                      # 类型层（10 个域文件）
    │   ├── project.ts              ProjectSummary, ProjectCreateRequest
    │   ├── generation.ts           TickRequest, TickResponse
    │   ├── entities.ts             CharacterItem/Detail, LocationItem/Detail,
    │   │                           SceneItem, LoopItem, FactionItem,
    │   │                           GraphNode, GraphEdge
    │   ├── status.ts               项目状态接口
    │   ├── compile.ts              编译接口
    │   ├── plot.ts                 情节节拍接口
    │   ├── checkpoint.ts           存档接口
    │   ├── skill.ts                技能接口
    │   ├── reference.ts            参考库接口
    │   └── theme.ts                主题类型 (WritingTheme)
    │
    ├── api/                        # 端点层（10 个域 + client）
    │   ├── client.ts               fetch 基座 + ApiError 类
    │   ├── projects.ts             create(), list(), resume()
    │   ├── generation.ts           tick(), tickStream() (SSE), run()
    │   ├── entities.ts             characters/locations/scenes/loops/factions
    │   │                           + 详情 + relationships 图数据
    │   ├── status.ts               get(), goals(), lore()
    │   ├── compile.ts              run(), summarize(), titles()
    │   ├── plot.ts                 status(), generate(), clear()
    │   ├── checkpoints.ts          create(), list(), restore(), delete()
    │   ├── skills.ts              importSkill(), list(), apply(), delete()
    │   └── references.ts          importNovel(), search()
    │
    ├── components/                 # 展示层
    │   ├── ui/                     # 原子 UI 组件（14 个）
    │   │   ├── Button.tsx          按钮 (variant/size/disabled/loading)
    │   │   ├── Input.tsx           文本输入 + label + error
    │   │   ├── Select.tsx          下拉选择器
    │   │   ├── Textarea.tsx        多行文本输入
    │   │   ├── ThemedSelect.tsx    主题感知选择器
    │   │   ├── ThemedTextarea.tsx  主题感知文本区域
    │   │   ├── Modal.tsx           弹窗
    │   │   ├── Badge.tsx           彩色标签 (success/warning/danger/default)
    │   │   ├── Spinner.tsx         加载动画
    │   │   ├── Card.tsx            卡片容器
    │   │   ├── Table.tsx           数据表格 (columns[]/data[]/onRowClick?)
    │   │   ├── ProgressBar.tsx     进度条 (value 0-1 + label)
    │   │   ├── Checkbox.tsx        复选框
    │   │   └── Toggle.tsx          开关
    │   │
    │   ├── Layout.tsx              全局壳（header + 主题切换按钮 + Outlet）
    │   ├── Sidebar.tsx             项目侧边栏（4 组导航 + 主题切换）
    │   ├── StatGrid.tsx            统计卡片网格
    │   ├── EntityList.tsx          通用实体列表（标题 + Table + Spinner）
    │   ├── EntityDetail.tsx        通用实体详情面板（侧边滑出）
    │   ├── ProjectCard.tsx         项目卡片（Dashboard 用）
    │   ├── NewProjectModal.tsx     新建项目弹窗
    │   ├── WritingControls.tsx     写作控制面板
    │   └── WritingOutput.tsx       写作输出区域（流式文本显示）
    │
    ├── pages/                      # 页面层（18 个文件）
    │   ├── Dashboard.tsx           项目列表 + 新建 + 恢复
    │   ├── ProjectLayout.tsx       侧边栏 + <Outlet/> 布局壳
    │   ├── Overview.tsx            项目仪表盘（统计概览）
    │   ├── Read.tsx                阅读场景
    │   ├── Writing.tsx             核心写作界面（SSE 流式）
    │   ├── Characters.tsx          角色列表 + 侧边详情
    │   ├── Locations.tsx           地点列表 + 侧边详情
    │   ├── Scenes.tsx              场景列表 + 弹窗正文
    │   ├── Loops.tsx               线索列表
    │   ├── Factions.tsx            势力列表 + 侧边详情
    │   ├── Relationships.tsx       角色关系图（力导向可视化）
    │   ├── Goals.tsx               目标层级
    │   ├── Lore.tsx                世界观浏览（可筛选）
    │   ├── Plot.tsx                节拍管理
    │   ├── Checkpoints.tsx         存档管理
    │   ├── Skills.tsx              技能管理
    │   ├── References.tsx          参考库管理
    │   └── Compile.tsx             编译输出
    │
    ├── utils/                      # 工具层
    │   └── logger.ts               前端日志收集 + 发送到后端 /api/v1/log
    │
    └── styles/
        └── tokens.css              CSS 变量主题令牌（Literary Night 设计系统）
```

**总计约 65 个源文件**（未计配置文件），按功能域清晰划分。

---

## 三、主题系统

### 3.1 ThemeContext (`ThemeContext.tsx`)

React Context 作为主题状态的唯一真实来源：

```typescript
interface ThemeCtx {
  isDayMode: boolean;
  toggleTheme: () => void;
}
```

- 状态持久化到 `localStorage("theme")`
- 通过 `document.documentElement.classList.toggle("day")` 切换全局 class
- CSS 变量由 `tokens.css` 中的 `.day` / 默认（暗色）规则集控制

### 3.2 设计令牌 (`styles/tokens.css`)

"Literary Night" 双主题系统，采用 CSS 变量：

| 变量 | 暗色（默认） | 明色（.day） |
|------|------------|------------|
| `--bg-base` | 深黑褐 | 暖米白 |
| `--bg-surface` | 深紫黑 | 暖奶油 |
| `--bg-raised` | 暗紫灰 | 浅灰白 |
| `--text-1` | 米白 | 深棕 |
| `--text-2` | 暖灰 | 中灰 |
| `--text-3` | 深暖灰 | 浅灰 |
| `--accent` | 暖金色 | 琥珀色 |
| `--border` | 半透暖白 | 暖棕边框 |

**设计逻辑：** 所有组件通过 `var(--token)` 引用颜色，切换 `.day` class 即可全局换肤，无需 JS 逐组件传递。

---

## 四、入口文件 (`main.tsx`)

```tsx
<QueryClientProvider client={queryClient}>  {/* TanStack Query 全局配置 */}
  <BrowserRouter>                             {/* React Router */}
    <ThemeProvider>                            {/* 主题 Context */}
      <App />
    </ThemeProvider>
  </BrowserRouter>
</QueryClientProvider>
```

QueryClient 全局配置：`retry: 1, staleTime: 30_000`

---

## 五、路由 (`App.tsx`)

18 个路由，按 4 组组织：

```
/                             → Dashboard（项目列表）

/project/:id                  → ProjectLayout
  /project/:id                → Overview（概览，默认子路由）

  /project/:id/read           → Read        核心
  /project/:id/writing        → Writing      核心

  /project/:id/characters     → Characters   实体
  /project/:id/locations      → Locations    实体
  /project/:id/scenes         → Scenes       实体
  /project/:id/loops          → Loops        实体
  /project/:id/factions       → Factions     实体
  /project/:id/relationships  → Relationships 实体

  /project/:id/goals          → Goals        分析
  /project/:id/lore           → Lore         分析

  /project/:id/plot           → Plot         管理
  /project/:id/checkpoints    → Checkpoints  管理
  /project/:id/skills         → Skills       管理
  /project/:id/references     → References   管理
  /project/:id/compile        → Compile      管理
```

**Sidebar 导航分组（`components/Sidebar.tsx`）：**

| 分组 | 导航项 |
|------|--------|
| 核心 | 概览、阅读、写作 |
| 实体 | 角色、地点、场景、线索、势力、关系图 |
| 分析 | 目标、世界观 |
| 管理 | 节拍、存档、技能、参考、编译 |

---

## 六、各层详设

### 6.1 api/ — 端点层

**`client.ts`** — fetch 基座：

```typescript
const BASE = "http://localhost:8221";

class ApiError extends Error {
  status: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

**`generation.ts`** — 含 SSE 流式：

```typescript
export function tickStream(projectId: string): EventSource {
  return new EventSource(`${BASE}/api/v1/project/${projectId}/tick/stream`);
}
```

**`entities.ts`** — 新增 relationships 端点：

```typescript
export function getRelationships(projectId: string) {
  return request<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
    `/api/v1/project/${projectId}/relationships`
  );
}
```

### 6.2 types/ — 类型层

镜像后端 Pydantic 模型，只保留前端实际用到的字段。

```typescript
// types/entities.ts — GraphNode / GraphEdge（关系图专用）
export interface GraphNode {
  id: string; name: string; role: string;
}
export interface GraphEdge {
  source: string; target: string; type: string;
}

// types/theme.ts — WritingTheme
export interface WritingTheme {
  key: string; label: string;
  bg: string; surface: string; raised: string;
  text1: string; text2: string; text3: string;
  accent: string; border: string;
}
```

### 6.3 components/ — 展示层

**约束：** 只接收 props，渲染 JSX。不调 API，不写业务逻辑。

| 组件 | 输入 | 输出 |
|------|------|------|
| `Button` | variant, size, disabled, loading, onClick, children | `<button>` |
| `Input` | label, value, error, placeholder, onChange | `<input>` + `<label>` |
| `Select` | label, value, options, onChange | `<select>` |
| `Textarea` | label, value, rows, onChange | `<textarea>` |
| `ThemedSelect` | (同 Select) + CSS 变量感知 | 主题感知 `<select>` |
| `ThemedTextarea` | (同 Textarea) + CSS 变量感知 | 主题感知 `<textarea>` |
| `Modal` | open, title, onClose, children | 弹窗 |
| `Badge` | variant(success/warning/danger/default) | 彩色标签 |
| `Spinner` | — | 加载动画 |
| `Card` | children, className | 卡片容器 |
| `Table` | columns[], data[], onRowClick? | `<table>` |
| `ProgressBar` | value(0-1), label | 进度条 |
| `Checkbox` | label, checked, onChange | 复选框 |
| `Toggle` | label, checked, onChange | 开关 |
| `Layout` | children | 全局 header + 主题切换按钮 + 主区域 |
| `Sidebar` | projectName, tick | 侧边导航 + 主题切换 |
| `StatGrid` | stats: {label, value}[] | 统计卡片网格 |
| `EntityList` | title, columns[], data[], loading, onRowClick | 带标题的 Table + Spinner |
| `EntityDetail` | data, onClose, title? | 侧边详情面板 |
| `ProjectCard` | project (ProjectSummary), onClick | 项目卡片（名称/幕数/字数） |
| `NewProjectModal` | open, onClose, onCreate | 新建项目弹窗 |
| `WritingControls` | (生成相关 props) | 写作控制面板 |
| `WritingOutput` | text, stats | 输出区域 |

### 6.4 pages/ — 页面层

**约束：** 调 API、拿数据、处理交互、传给组件。业务逻辑就在这里，不再抽到 hooks 层。

典型页面结构（Characters.tsx）：

```tsx
export function CharactersPage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string | null>(null);

  const { data: list, isLoading } = useQuery({
    queryKey: ["characters", id],
    queryFn: () => getCharacters(id!),
  });
  const { data: detail } = useQuery({
    queryKey: ["character", id, selected],
    queryFn: () => getCharacter(id!, selected!),
    enabled: !!selected,
  });

  return (
    <div className="flex gap-6 h-full">
      <EntityList title="角色" columns={columns} data={list?.characters ?? []}
                   loading={isLoading} onRowClick={(c) => setSelected(c.id)} />
      {detail && <EntityDetail data={detail} onClose={() => setSelected(null)} />}
    </div>
  );
}
```

---

## 七、页面功能表

### 项目域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Dashboard** | `api.projects.list()` `api.projects.resume()` | 新建弹窗、点卡片进项目、继续上次 |
| **Overview** | `api.status.get(id)` | 统计概览、跳转写作/阅读 |
| **Writing** | `api.generation.tick(id,req)` + SSE 流式 | 控制面板 + 流式输出、切换后端/模型 |
| **Read** | `api.entities.scenes(id)` | 场景浏览阅读 |

### 实体域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Characters** | `api.entities.characters(id)` `api.entities.character(id,cid)` | 列表点击→侧边详情面板 |
| **Locations** | `api.entities.locations(id)` `api.entities.location(id,lid)` | 同上 |
| **Scenes** | `api.entities.scenes(id)` `api.entities.scene(id,sid)` | 列表点击→弹窗正文 |
| **Loops** | `api.entities.loops(id)` | 纯列表 |
| **Factions** | `api.entities.factions(id)` `api.entities.faction(id,fid)` | 列表点击→侧边详情面板 |
| **Relationships** | `api.entities.relationships(id)` + `api.entities.character(id,cid)` | 力导向图可视化：拖拽节点、平移缩放、悬停高亮、点击看详情 |

### 分析域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Goals** | `api.status.goals(id)` | 纯展示（目标层级树） |
| **Lore** | `api.status.lore(id, params)` | 筛选（category/type/importance） |

### 管理域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Plot** | `api.plot.status(id)` `api.plot.generate(id,req)` `api.plot.clear(id)` | 统计+生成按钮+清空确认+列表 |
| **Checkpoints** | `api.checkpoints.list(id)` + create/restore/delete | 新建+恢复确认+删除确认+列表 |
| **Skills** | `api.skills.list()` + import/apply/delete | 导入弹窗+应用弹窗+删除确认+列表 |
| **References** | `api.references.import(req)` `api.references.search(req)` | 导入弹窗（文件路径+标题）、搜索输入+结果列表 |
| **Compile** | `api.compile.run(id,req)` `api.compile.summarize(id)` `api.compile.titles(id,req)` | 选择格式→编译→展示+复制/下载 |

---

## 八、Relationships 页面 — 力导向关系图

`pages/Relationships.tsx` 实现了完整的交互式角色关系可视化：

**布局算法：**
- 初始：节点均匀分布在圆形上
- 80 轮 Velocity Verlet 迭代：引力（向心）+ 斥力（节点间）+ 边弹力（理想长度 80+15×degree）
- 支持拖拽节点、平移画布、滚轮缩放（0.2x–3x）

**交互功能：**
- 悬停节点 → 高亮关联路径，其他边/节点淡出
- 点击节点 → 侧边滑出 EntityDetail 面板
- 颜色编码：主角（暖金）、反派（玫瑰红）、配角（蓝色）、路人（灰色）
- 图例：左上角角色类型说明

**设计逻辑：** 不用 D3/ECharts 等重型库，直接手写 SVG + 力导向布局，约 200 行完成全部可视化逻辑。

---

## 九、前端日志系统 (`utils/logger.ts`)

独立的客户端日志收集模块：

```
logger.error(source, error, context?)  → console.error + POST /api/v1/log
logger.warn(source, message, context?) → console.warn  + POST /api/v1/log
logger.info(source, message)           →               + POST /api/v1/log
```

**特性：**
- 100 条内存缓冲区（环形），`getLogBuffer()` 可读取
- 自动捕获全局 `window.onerror` 和 `unhandledrejection`
- 发送失败静默忽略，避免日志循环
- 后端 `api/routers/log.py` 接收并写入 `novel_agent.frontend` logger

---

## 十、数据流

```
用户操作 → Page（useState + useQuery/useMutation + 事件处理）
              │
              ├── useQuery → api.xxx() → fetch → Backend (:8221)
              │                  └── 返回数据 → 渲染 Component
              │
              ├── useMutation → api.xxx() → fetch → Backend
              │                   └── onSuccess → invalidateQueries → 自动刷新
              │
              └── SSE Stream → new EventSource(url)
                                 └── onmessage → setText(prev + chunk) → 实时渲染
```

---

## 十一、后端端点覆盖清单

| # | 端点 | 方法 | 前端页面 | API 函数 |
|---|------|------|---------|---------|
| 1 | `/health` | GET | —（无需前端） | — |
| 2 | `/api/v1/project` | POST | Dashboard | `api.projects.create()` |
| 3 | `/api/v1/projects` | GET | Dashboard | `api.projects.list()` |
| 4 | `/api/v1/resume` | POST | Dashboard | `api.projects.resume()` |
| 5 | `/api/v1/project/{id}/tick` | POST | Writing | `api.generation.tick()` |
| 6 | `/api/v1/project/{id}/tick/stream` | GET | Writing | `api.generation.stream()` |
| 7 | `/api/v1/project/{id}/run` | POST | Writing | `api.generation.run()` |
| 8 | `/api/v1/project/{id}/status` | GET | Overview | `api.status.get()` |
| 9-10 | `/api/v1/project/{id}/characters[/{cid}]` | GET | Characters | `api.entities.characters/character()` |
| 11-12 | `/api/v1/project/{id}/locations[/{lid}]` | GET | Locations | `api.entities.locations/location()` |
| 13-14 | `/api/v1/project/{id}/scenes[/{sid}]` | GET | Scenes | `api.entities.scenes/scene()` |
| 15 | `/api/v1/project/{id}/loops` | GET | Loops | `api.entities.loops()` |
| 16-17 | `/api/v1/project/{id}/factions[/{fid}]` | GET | Factions | `api.entities.factions/faction()` |
| 18 | `/api/v1/project/{id}/relationships` | GET | Relationships | `api.entities.relationships()` |
| 19 | `/api/v1/project/{id}/goals` | GET | Goals | `api.status.goals()` |
| 20 | `/api/v1/project/{id}/lore` | GET | Lore | `api.status.lore()` |
| 21 | `/api/v1/project/{id}/compile` | POST | Compile | `api.compile.run()` |
| 22 | `/api/v1/project/{id}/summarize` | GET | Compile | `api.compile.summarize()` |
| 23 | `/api/v1/project/{id}/titles` | POST | Compile | `api.compile.titles()` |
| 24 | `/api/v1/project/{id}/plot` | GET | Plot | `api.plot.status()` |
| 25 | `/api/v1/project/{id}/plot/generate` | POST | Plot | `api.plot.generate()` |
| 26 | `/api/v1/project/{id}/plot` | DELETE | Plot | `api.plot.clear()` |
| 27-30 | `/api/v1/project/{id}/checkpoints[/{cid}[/restore]]` | POST/GET/DELETE | Checkpoints | `api.checkpoints.*()` |
| 31-34 | `/api/v1/skills[/{slug}]` | POST/GET/DELETE | Skills | `api.skills.*()` |
| 35-36 | `/api/v1/references/*` | POST | References | `api.references.*()` |
| 37 | `/api/v1/log` | POST | (logger.ts) | (自动) |
| 38+ | `/api/v1/project/{id}/threads/*` | GET/POST | (后端内部) | — |

**38+ 个后端端点，除 `/health` 外均有前端对应，覆盖率 100%。**

---

## 十二、实现顺序

| 步 | 产出 | 关键产物 |
|----|------|---------|
| 1 | package.json + vite + tailwind + tsconfig + tokens.css + main.tsx + App.tsx | 空项目跑起来 |
| 2 | types/*（10个文件） | 类型定义完成 |
| 3 | api/client.ts + api/*（11个文件） | 全部端点可调用 |
| 4 | components/ui/*（14个）+ Layout + Sidebar | 基础 UI 库 + 布局壳 |
| 5 | ThemeContext + tokens.css | 明暗主题双模式 |
| 6 | Dashboard + ProjectLayout + Overview | 能浏览项目 |
| 7 | Writing（SSE 流式输出核心） | **能写小说了** |
| 8 | EntityList + EntityDetail + 实体页面（6个） | 能查看角色/地点/场景/关系图 |
| 9 | StatGrid + Goals + Lore | 分析功能 |
| 10 | Plot + Checkpoints + Skills + References | 管理功能 |
| 11 | Compile | 全部功能覆盖 |
| 12 | logger.ts + /api/v1/log | 前端异常可追踪 |
