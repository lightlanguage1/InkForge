# InkForge 部署文档

**服务器**: `ssh InkForge` (ubuntu@106.54.6.71)  
**项目路径**: `/home/ubuntu/InkForge`  
**容器**: `ubuntu-backend-1` / `ubuntu-frontend-1`

## 架构

```
用户 → Nginx (:443) → /api/* → Backend Nginx (:8000) → Uvicorn (:9000)
                     → /*     → 前端静态文件

数据: inkforge_data volume → /app/work（持久化）
代码: 在 Docker 镜像内，非挂载 → 更新用 docker cp
```

## 日常部署（只改代码，不改依赖）

代码在镜像内，**不要 rebuild**，直接 `docker cp` 注入 + 重启（2秒）：

```bash
# 1. SCP 文件到服务器
scp -i ~/.ssh/inkforge.pem local.py ubuntu@106.54.6.71:/home/ubuntu/InkForge/path/to/file.py

# 2. 注入运行中的容器
ssh InkForge "docker cp /home/ubuntu/InkForge/path/to/file.py ubuntu-backend-1:/app/path/to/file.py"

# 3. 重启
ssh InkForge "docker restart ubuntu-backend-1"

# 4. 验证
ssh InkForge "docker logs --tail=5 ubuntu-backend-1"
# 看到 "Application startup complete." = 成功
```

多文件批量注入：
```bash
ssh InkForge "
  docker cp /home/ubuntu/InkForge/novel_agent/agent/agent.py ubuntu-backend-1:/app/novel_agent/agent/agent.py &&
  docker cp /home/ubuntu/InkForge/novel_agent/data/templates/planner_prompt.md ubuntu-backend-1:/app/novel_agent/data/templates/planner_prompt.md &&
  docker restart ubuntu-backend-1
"
```

## 前端更新

```bash
cd frontend && npm run build
scp -r dist/* ubuntu@106.54.6.71:/home/ubuntu/InkForge/frontend/dist/
ssh InkForge "docker cp /home/ubuntu/InkForge/frontend/dist/. ubuntu-frontend-1:/usr/share/nginx/html/"
```

## 完整重建（仅改 Dockerfile / requirements.txt 时需要）

```bash
ssh InkForge "cd /home/ubuntu/InkForge && docker compose build backend && docker compose up -d backend"
```

## 路径映射

| 容器内 | 宿主机 | 更新方式 |
|---|---|---|
| `/app/novel_agent/` | `/home/ubuntu/InkForge/novel_agent/` | `docker cp` 注入 |
| `/app/work/` | `inkforge_data` volume | 持久化，不删 |
| `/usr/share/nginx/html/` | 前端构建产物 | `docker cp` 注入 |

## 常用命令

```bash
# 容器状态
ssh InkForge "docker ps"

# 后端日志（最近30行）
ssh InkForge "docker logs --tail=30 ubuntu-backend-1"

# 错误日志
ssh InkForge "docker logs ubuntu-backend-1 2>&1 | grep -i error"

# 健康检查
curl -s -o /dev/null -w '%{http_code}' https://inkforge.irynekoneko.club/api/v1/projects
```

## 注意事项

- `docker cp` 注入的文件在 `docker compose down && up` 后会丢失（镜像恢复），需重新注入
- `docker restart` 保留注入文件，是日常更新正确方式
- `/app/work/` 是 volume，项目数据不会丢失
- 不要为了更新代码而 `docker compose build`——那会走完整 pip install + apt 流程，浪费几分钟
