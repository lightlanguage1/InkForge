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
- Projects: 多个项目运行中
- Docker: backend Up, frontend Up
- Users: 7 已注册, 15/22 码可用
