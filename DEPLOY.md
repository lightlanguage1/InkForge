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

## 前端部署

只改了前端文件时：

```powershell
# 1. 本地构建
cd F:\StoryDaemon\frontend
npm run build

# 2. 打包
tar -czf F:\StoryDaemon\frontend-dist.tar.gz -C F:\StoryDaemon\frontend\dist .

# 3. 上传
scp -i C:\Users\lightlanguage\.ssh\inkforge.pem F:\StoryDaemon\frontend-dist.tar.gz ubuntu@106.54.6.71:/tmp/inkforge-dist.tar.gz

# 4. 注入容器
ssh -i C:\Users\lightlanguage\.ssh\inkforge.pem ubuntu@106.54.6.71 "docker exec ubuntu-frontend-1 sh -c 'rm -rf /usr/share/nginx/html/assets'; docker cp /tmp/inkforge-dist.tar.gz ubuntu-frontend-1:/tmp/dist.tar.gz; docker exec ubuntu-frontend-1 sh -c 'cd /usr/share/nginx/html && tar xzf /tmp/dist.tar.gz && rm /tmp/dist.tar.gz'; rm /tmp/inkforge-dist.tar.gz; echo OK"
```

## 后端部署

只改了后端 Python 文件时，逐个文件注入并重载：

```powershell
$KEY = "C:\Users\lightlanguage\.ssh\inkforge.pem"
$SERVER = "ubuntu@106.54.6.71"
$REMOTE = "/home/ubuntu/InkForge"

# 1. 传文件 + 注入容器（以 entities.py 为例）
$f = "novel_agent/api/routers/entities.py"
scp -i $KEY "F:\StoryDaemon\$f" ${SERVER}:$REMOTE/$f
ssh -i $KEY $SERVER "docker cp $REMOTE/$f ubuntu-backend-1:/app/$f"

# 2. 对照 git diff 列出所有改动文件，逐个执行上面两步
#    可用 git diff --name-only main..HEAD 看改了哪些

# 3. 重载 uvicorn（SIGHUP 不重启进程，不断 SQLite）
ssh -i $KEY $SERVER "docker exec ubuntu-backend-1 sh -c 'kill -HUP \$(pgrep -f uvicorn | head -1)'"

# 4. 验证日志
ssh -i $KEY $SERVER "docker logs --tail=5 ubuntu-backend-1"
```

## 完整重建

仅改 Dockerfile / requirements.txt 时需要：

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

# 后端日志
ssh InkForge "docker logs --tail=30 ubuntu-backend-1"

# 错误日志
ssh InkForge "docker logs ubuntu-backend-1 2>&1 | grep -i error"

# 健康检查
curl -s -o /dev/null -w '%{http_code}' https://inkforge.irynekoneko.club/api/v1/projects
```

## 注意事项

- `docker cp` 注入的文件在 `docker compose down && up` 后会丢失，需重新注入
- `docker restart` 保留注入文件，是日常更新正确方式
- SIGHUP 重载 uvicorn 不重启进程，SQLite 连接不断
- `/app/work/` 是 volume，项目数据不会丢失
- 不要为了更新代码而 `docker compose build`——会走完整 pip install + apt 流程
