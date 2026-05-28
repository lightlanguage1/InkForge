# StoryDaemon 前端架构

## 分层

```
pages/          页面 — 调 API、组合组件、处理交互
components/     组件 — 纯展示，props 进 JSX 出
api/            端点 — fetch 封装，按域分文件
types/          类型 — TS 接口，按域分文件
```

## 文件树

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
│
├── src/
│   ├── main.tsx
│   ├── App.tsx                       # 路由
│   │
│   ├── types/                        # 按域分文件（10个域，对应后端全部端点）
│   │   ├── project.ts
│   │   ├── generation.ts
│   │   ├── entities.ts
│   │   ├── status.ts
│   │   ├── compile.ts
│   │   ├── plot.ts
│   │   ├── checkpoint.ts
│   │   ├── skill.ts
│   │   └── reference.ts
│   │
│   ├── api/                          # 按域分文件（10个域 + client）
│   │   ├── client.ts                 # fetch 封装 + ApiError
│   │   ├── projects.ts
│   │   ├── generation.ts
│   │   ├── entities.ts
│   │   ├── status.ts
│   │   ├── compile.ts
│   │   ├── plot.ts
│   │   ├── checkpoints.ts
│   │   ├── skills.ts
│   │   └── references.ts
│   │
│   ├── components/                   # 展示组件，按职责分目录
│   │   ├── ui/                       # 原子 UI 组件
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Badge.tsx
│   │   │   ├── Spinner.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Table.tsx
│   │   │   └── ProgressBar.tsx
│   │   │
│   │   ├── Layout.tsx                # 全局壳（header + Outlet）
│   │   ├── Sidebar.tsx               # 项目侧边栏
│   │   ├── StatGrid.tsx              # 统计卡片网格
│   │   ├── EntityList.tsx            # 通用实体列表
│   │   └── EntityDetail.tsx          # 通用实体详情面板
│   │
│   └── pages/
│       ├── Dashboard.tsx             # 项目列表 + 新建 + 恢复
│       ├── ProjectLayout.tsx         # 侧边栏 + <Outlet/>
│       ├── Overview.tsx              # 项目仪表盘
│       ├── Writing.tsx               # 写作界面
│       ├── Characters.tsx            # 角色（列表 + 侧边详情）
│       ├── Locations.tsx             # 地点（列表 + 侧边详情）
│       ├── Scenes.tsx                # 场景（列表 + 弹窗正文）
│       ├── Loops.tsx                 # 线索列表
│       ├── Factions.tsx              # 势力（列表 + 侧边详情）
│       ├── Goals.tsx                 # 目标层级
│       ├── Lore.tsx                  # 世界观
│       ├── Plot.tsx                  # 节拍管理
│       ├── Checkpoints.tsx           # 存档管理
│       ├── Skills.tsx                # 技能管理
│       ├── References.tsx            # 参考库（导入 + 搜索）
│       └── Compile.tsx               # 编译输出
│
└── styles/
    └── tokens.css                    # CSS 变量
```

**48 个源文件**（未计 styles/tokens.css），按功能域清晰划分。

## 各层详设

### api/ — 端点层

`client.ts` — fetch 基座：
```typescript
const BASE = "http://localhost:8221";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
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

`entities.ts` — 例：
```typescript
import { request } from "./client";
import type { CharacterItem, CharacterDetail, LocationItem, SceneItem, LoopItem, FactionItem } from "../types/entities";

export function getCharacters(projectId: string, verbose = false) {
  return request<{ characters: CharacterItem[] }>(
    `/api/v1/project/${projectId}/characters?verbose=${verbose}`
  );
}
export function getCharacter(projectId: string, charId: string) {
  return request<CharacterDetail>(`/api/v1/project/${projectId}/characters/${charId}`);
}
// locations, scenes, loops, factions 同理
```

`generation.ts` — 包含 SSE：
```typescript
export function tickStream(projectId: string): EventSource {
  return new EventSource(`${BASE}/api/v1/project/${projectId}/tick/stream`);
}
```

### types/ — 类型层

镜像后端 Pydantic 模型，只保留前端实际用到的字段。

```typescript
// types/entities.ts
export interface CharacterItem {
  id: string; name: string; role: string; status: string;
}

export interface CharacterDetail {
  id: string; first_name: string; family_name: string;
  title: string; nicknames: string[]; role: string;
  description: string; backstory: string;
  personality: { core_traits: string[]; fears: string[]; desires: string[]; flaws: string[] };
  physical_traits: { age: number | null; appearance: string; distinctive_features: string[] };
  current_state: {
    location_id: string | null; emotional_state: string; physical_state: string;
    emotion: { dominant: string; valence: number; arousal: number; intensity: number };
    inventory: string[]; goals: string[]; beliefs: string[];
  };
  relationships: { character_id: string; relationship_type: string; status: string; description: string }[];
  history: { tick: number; scene_id: string; summary: string }[];
  appearance_ticks: number[]; last_scene_tick: number; pov_count: number;
}

// LocationItem, SceneItem, LoopItem, FactionItem 同理
```

```typescript
// types/generation.ts
export interface TickRequest {
  project_path?: string; save_prompts?: boolean;
  llm_backend?: string; llm_model?: string; notes?: string;
}
export interface TickResponse {
  success: boolean; tick: number; scene_id: string;
  scene_file: string; word_count: number; actions_executed: number;
  tension?: { level: number; category: string };
}
```

### components/ — 展示层

**约束**：只接收 props，渲染 JSX。不调 API，不写业务逻辑。

| 组件 | 输入 | 输出 |
|------|------|------|
| `Button` | variant, size, disabled, loading, onClick, children | `<button>` |
| `Input` | label, value, error, placeholder, onChange | `<input>` + `<label>` |
| `Select` | label, value, options, onChange | `<select>` |
| `Textarea` | label, value, rows, onChange | `<textarea>` |
| `Modal` | open, title, onClose, children | 弹窗 |
| `Badge` | variant(success/warning/danger/default) | 彩色标签 |
| `Spinner` | — | 加载动画 |
| `Card` | children, className | 卡片容器 |
| `Table` | columns[], data[], onRowClick? | `<table>` |
| `ProgressBar` | value(0-1), label | 进度条 |
| `Layout` | children | 全局 header + 主区域 |
| `Sidebar` | projectName, navItems, currentPath | 侧边导航 |
| `StatGrid` | stats: {label, value}[] | 统计卡片网格 |
| `EntityList` | title, columns[], data[], loading, onRowClick | 带标题的 Table + Spinner |
| `EntityDetail` | data, onClose | 侧边详情面板 |

### pages/ — 页面层

**约束**：调 API、拿数据、处理交互、传给组件。业务逻辑就在这里，不再抽到 hooks 层。

典型页面结构（Characters.tsx）：
```tsx
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCharacters, getCharacter } from "../api/entities";
import { EntityList, EntityDetail } from "../components/EntityDetail";

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

  const columns = [
    { key: "name", header: "名称" },
    { key: "role", header: "角色" },
    { key: "status", header: "状态", render: (c) => <Badge>{c.status}</Badge> },
  ];

  return (
    <div className="flex gap-6 h-full">
      <EntityList title="角色" columns={columns} data={list?.characters ?? []}
                   loading={isLoading} onRowClick={(c) => setSelected(c.id)} />
      {detail && <EntityDetail data={detail} onClose={() => setSelected(null)} />}
    </div>
  );
}
```

### pages/Writing.tsx — 核心写作界面

```
┌──────────────────────────────────────────────┐
│  写作界面                        第 15 幕     │
├───────────────────┬──────────────────────────┤
│  控制面板（左侧）  │  输出区域（右侧）         │
│                   │                          │
│  场景方向指导:     │  SSE 流式逐字追加渲染     │
│  ┌─────────────┐  │                          │
│  │ 让主角在月光 │  │  生成完成后展示：         │
│  │ 下与小师妹... │  │  字数 | 动作数 | 张力    │
│  └─────────────┘  │                          │
│                   │                          │
│  后端: [api ▾]    │                          │
│  模型: [deepseek▾]│                          │
│                   │                          │
│  [▶ 生成一幕]     │                          │
│  [▶ 连续 5 幕]    │                          │
│  ☐ 保存 prompt    │                          │
└───────────────────┴──────────────────────────┘
```

SSE 流式通过 `EventSource` 实现：
```tsx
const [text, setText] = useState("");
const handleStream = () => {
  const es = new EventSource(`http://localhost:8221/api/v1/project/${id}/tick/stream`);
  es.onmessage = (e) => setText(prev => prev + JSON.parse(e.data).text);
  es.onerror = () => es.close();
};
```

## 路由

```
/                             → Dashboard
/project/:id                  → ProjectLayout
  /project/:id                → Overview（默认子路由）
  /project/:id/writing        → Writing
  /project/:id/characters     → Characters
  /project/:id/locations      → Locations
  /project/:id/scenes         → Scenes
  /project/:id/loops          → Loops
  /project/:id/factions       → Factions
  /project/:id/goals          → Goals
  /project/:id/lore           → Lore
  /project/:id/plot           → Plot
  /project/:id/checkpoints    → Checkpoints
  /project/:id/skills         → Skills
  /project/:id/references     → References
  /project/:id/compile        → Compile
```

15 个页面路由，覆盖后端全部 35 个端点（除 `/health`）。`ProjectLayout` 是布局壳，`<Sidebar />` + `<Outlet />`。

## 页面功能表

### 项目域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Dashboard** | `api.projects.list()` `api.projects.resume()` | 新建弹窗、点卡片进项目、继续上次 |
| **Overview** | `api.status.get(id)` | 纯展示、点"继续写作"跳 Writing |
| **Writing** | `api.generation.tick(id,req)` SSE | 控制面板 + 流式输出、切换后端/模型 |

### 实体域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Characters** | `api.entities.characters(id)` `api.entities.character(id,cid)` | 列表点击→侧边详情面板 |
| **Locations** | `api.entities.locations(id)` `api.entities.location(id,lid)` | 同上 |
| **Scenes** | `api.entities.scenes(id)` `api.entities.scene(id,sid)` | 列表点击→弹窗正文 |
| **Loops** | `api.entities.loops(id)` | 纯列表 |
| **Factions** | `api.entities.factions(id)` `api.entities.faction(id,fid)` | 列表点击→侧边详情面板 |

### 信息域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Goals** | `api.status.goals(id)` | 纯展示（GoalTree） |
| **Lore** | `api.status.lore(id, params)` | 筛选（category/type/importance） |

### 管理域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Plot** | `api.plot.status(id)` `api.plot.generate(id,req)` `api.plot.clear(id)` | 统计+生成按钮+清空确认+列表 |
| **Checkpoints** | `api.checkpoints.list(id)` `api.checkpoints.create(id,req)` `api.checkpoints.restore(id,cid)` `api.checkpoints.delete(id,cid)` | 新建+恢复确认+删除确认+列表 |
| **Skills** | `api.skills.list()` `api.skills.import(req)` `api.skills.apply(req)` `api.skills.delete(slug)` | 导入弹窗+应用弹窗+删除确认+列表 |

### 参考域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **References** | `api.references.import(req)` `api.references.search(req)` | 导入弹窗（文件路径+标题）、搜索输入+结果列表 |

### 输出域

| 页面 | 数据来源 | 交互 |
|------|---------|------|
| **Compile** | `api.compile.run(id,req)` `api.compile.summarize(id)` `api.compile.titles(id,req)` | 选择格式→编译→展示+复制/下载 |

## 数据流

```
用户操作 → Page（useState + useQuery + 事件处理）
              │
              ├── useQuery → api.xxx() → fetch → Backend
              │                  └── 返回数据 → 渲染 Component
              │
              └── useMutation → api.xxx() → fetch → Backend
                                   └── onSuccess → invalidateQueries → 自动刷新
```

## 实现顺序

| 步 | 产出 | 做完能干嘛 |
|----|------|-----------|
| 1 | package.json + vite + tailwind + tsconfig + styles/tokens.css + main.tsx + App.tsx | 空项目跑起来 |
| 2 | types/*（10个文件） | 类型定义完成 |
| 3 | api/client.ts + api/*（11个文件） | 全部 35 个端点可调用 |
| 4 | components/ui/*（9个）+ Layout + Sidebar | 基础 UI 库 + 布局壳 |
| 5 | Dashboard + ProjectLayout + Overview | 能浏览项目 |
| 6 | Writing（SSE 流式输出核心） | **能写小说了** |
| 7 | EntityList + EntityDetail + 5个实体页面 | 能查看角色/地点/场景 |
| 8 | StatGrid + Goals + Lore | 信息查看完毕 |
| 9 | Plot + Checkpoints + Skills + References | 管理功能完毕 |
| 10 | Compile | 全部功能覆盖 |

## 后端端点覆盖清单

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
| 9 | `/api/v1/project/{id}/characters` | GET | Characters | `api.entities.characters()` |
| 10 | `/api/v1/project/{id}/characters/{cid}` | GET | Characters | `api.entities.character()` |
| 11 | `/api/v1/project/{id}/locations` | GET | Locations | `api.entities.locations()` |
| 12 | `/api/v1/project/{id}/locations/{lid}` | GET | Locations | `api.entities.location()` |
| 13 | `/api/v1/project/{id}/scenes` | GET | Scenes | `api.entities.scenes()` |
| 14 | `/api/v1/project/{id}/scenes/{sid}` | GET | Scenes | `api.entities.scene()` |
| 15 | `/api/v1/project/{id}/loops` | GET | Loops | `api.entities.loops()` |
| 16 | `/api/v1/project/{id}/factions` | GET | Factions | `api.entities.factions()` |
| 17 | `/api/v1/project/{id}/factions/{fid}` | GET | Factions | `api.entities.faction()` |
| 18 | `/api/v1/project/{id}/goals` | GET | Goals | `api.status.goals()` |
| 19 | `/api/v1/project/{id}/lore` | GET | Lore | `api.status.lore()` |
| 20 | `/api/v1/project/{id}/compile` | POST | Compile | `api.compile.run()` |
| 21 | `/api/v1/project/{id}/summarize` | GET | Compile | `api.compile.summarize()` |
| 22 | `/api/v1/project/{id}/titles` | POST | Compile | `api.compile.titles()` |
| 23 | `/api/v1/project/{id}/plot` | GET | Plot | `api.plot.status()` |
| 24 | `/api/v1/project/{id}/plot/generate` | POST | Plot | `api.plot.generate()` |
| 25 | `/api/v1/project/{id}/plot` | DELETE | Plot | `api.plot.clear()` |
| 26 | `/api/v1/project/{id}/checkpoints` | POST | Checkpoints | `api.checkpoints.create()` |
| 27 | `/api/v1/project/{id}/checkpoints` | GET | Checkpoints | `api.checkpoints.list()` |
| 28 | `/api/v1/project/{id}/checkpoints/{cid}/restore` | POST | Checkpoints | `api.checkpoints.restore()` |
| 29 | `/api/v1/project/{id}/checkpoints/{cid}` | DELETE | Checkpoints | `api.checkpoints.delete()` |
| 30 | `/api/v1/skills/import` | POST | Skills | `api.skills.import()` |
| 31 | `/api/v1/skills` | GET | Skills | `api.skills.list()` |
| 32 | `/api/v1/skills/apply` | POST | Skills | `api.skills.apply()` |
| 33 | `/api/v1/skills/{slug}` | DELETE | Skills | `api.skills.delete()` |
| 34 | `/api/v1/references/import` | POST | References | `api.references.import()` |
| 35 | `/api/v1/references/search` | POST | References | `api.references.search()` |

**35 个后端端点，34 个有前端对应（`/health` 除外），覆盖率 100%。**
