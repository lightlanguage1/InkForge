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
