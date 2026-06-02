# InkForge 内测监控

**域名**: `https://inkforge.irynekoneko.club`
**周期**: 每 30 分钟检查一次
**开始**: 2026-06-01

---

## 监控指标

| 指标 | 说明 |
|------|------|
| Health | HTTPS 健康检查，目标 <1s |
| Auth | 管理员邀请码能否正常激活 |
| Projects | 项目总数、每个项目的 tick/scenes |
| Users | 注册用户数、邀请码使用率 |
| Docker | 容器运行状态 |

---

## 记录

### #1 — 2026-06-01 10:00 UTC
- Health: ✅ 200 (5ms)
- Auth: ✅ 管理员码正常
- Projects: 多个项目运行中，有活跃 SSE 生成
- Docker: backend Up, frontend Up
- Users: 7 已注册, 15/22 码可用
- Logs: 干净，无 RuntimeError/Traceback。仅个别"编译失败，没有场景可编译"（空项目正常操作）
- 活跃项目: 转生异世界成为猫娘、重生贤者加入魔王军、哥布林之王 等

### #2 — 2026-06-01 13:35 CST (05:35 UTC)
- Health: ✅ 200 (5ms)
- Docker: ✅ backend Up 12min, frontend Up 1h
- Users: 7 已注册, 7/22 码已用
- Projects: 转生异世界成为猫娘靠哈气攻略迷宫(tick 0), 哥布林之王(已有), 茉莉花_bb6d7d58(已有)
- Logs: ✅ 干净，无异常
- ChromaDB: ✅ 模型已永久固化，0.7s 加载

### #3 — 2026-06-01 18:23 CST (10:23 UTC)
- Health: ✅ 200 (5ms)
- Docker: ✅ backend Up 2h, frontend Up 3h
- Users: 8 (+1), 8/22 码已用
- Projects: 转生异世界成为猫娘靠哈气攻略迷宫(tick 2, 在生成中), 其他项目正常
- Logs: ✅ 干净，无异常

### #4 — 2026-06-01 20:41 CST (12:41 UTC)
- Health: ✅ 200 (5ms)
- Docker: ✅ frontend Up 4h, backend Up 14min
- Users: 9 (+1), 9/22 码已用
- Projects: 1 个项目 (7017f4a1，tick=2)
- Logs: ✅ 干净，无异常

### #5 — 2026-06-02 10:27 CST (02:27 UTC)
- Health: ✅ 200 (5ms)
- Docker: ✅ frontend Up 8h, backend 刚重启
- Users: 9（未变）, 9/22 码已用
- Projects: 2 个项目（转生猫娘 tick=2, 鼠的故事）
- Portrait: GLM-4.5V + Pillow 服务端渲染 + 视觉评分校验流水线已上线
- Logs: ✅ 干净，无异常

### #6 — 2026-06-02 13:30 CST (05:30 UTC)
- Health: ✅ 200 (5ms)
- Docker: ✅ frontend Up 21h, backend Up 14min（planner prompt + 工具容错已部署）
- Users: 11 (+2), 11/22 码已用
- Projects: 13 个（青云洗剑录 tick=10, 女捕头 tick=12 最长）
- Logs: ✅ 干净，无异常（planner prompt 强制工具调用刚上线，待观察新 tick）

**智能体工具使用率分析（36 ticks / 98 次调用）：**

| 工具 | 调用 | 占比 | 状态 |
|------|------|------|------|
| location.generate | 33 | 34% | ████████ |
| character.generate | 23 | 23% | ██████ |
| relationship.create | 20 | 20% | █████ |
| relationship.update | 13 | 13% | ███ |
| memory.search | 8 | 8% | ██ |
| faction.generate | 1 | 1% | ▏ |
| character.update | 0 | 0% | ❌ 从未调用 |
| location.update | 0 | 0% | ❌ 从未调用 |
| faction.update | 0 | 0% | ❌ 从未调用 |
| lore.extract | 0 | 0% | ❌ 从未调用 |
| lore.contradiction_check | 0 | 0% | ❌ 从未调用 |
| loop.create | 0 | 0% | ❌ 从未调用 |
| loop.resolve | 0 | 0% | ❌ 从未调用 |

**使用率: 6/13 (46%) | 平均/tick: 2.7 | 已部署强制工具调用 prompt，下个监控周期对比**
