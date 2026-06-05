#!/usr/bin/env pwsh
# InkForge 部署脚本 — 增量构建，可靠传输
param([switch]$FrontendOnly, [switch]$BackendOnly)

$KEY = "C:\Users\lightlanguage\.ssh\inkforge.pem"
$SERVER = "ubuntu@106.54.6.71"
$REMOTE = "/home/ubuntu/InkForge"

# ── 后端 ──
if (-not $FrontendOnly) {
    Write-Host "=== 后端 ===" -ForegroundColor Cyan

    # SCP Python files (change list as needed)
    $backendFiles = @(
        "novel_agent/user/db.py",
        "novel_agent/user/auth.py",
        "novel_agent/user/middleware.py",
        "novel_agent/api/deps.py",
        "novel_agent/api/server.py",
        "novel_agent/api/routers/auth.py",
        "novel_agent/api/routers/admin.py",
        "novel_agent/api/routers/entities.py",
        "novel_agent/api/routers/projects.py",
        "novel_agent/agent/agent.py",
        "novel_agent/agent/context.py",
        "novel_agent/agent/runtime.py",
        "novel_agent/agent/streaming_agent.py",
        "novel_agent/agent/entity_updater.py",
        "novel_agent/agent/lore_extractor.py",
        "novel_agent/memory/entities.py",
        "novel_agent/memory/manager.py",
        "novel_agent/memory/vector_store.py",
        "novel_agent/tools/memory_tools.py",
        "novel_agent/tools/name_generator.py",
        "novel_agent/data/templates/planner_prompt.md"
    )

    foreach ($f in $backendFiles) {
        $localPath = "F:\StoryDaemon\$f"
        $remotePath = "$REMOTE/$f"
        $containerPath = "/app/$f"

        if (Test-Path $localPath) {
            scp -i $KEY $localPath ${SERVER}:$remotePath
            ssh -i $KEY $SERVER "docker cp $remotePath ubuntu-backend-1:$containerPath"
            Write-Host "  OK: $f" -ForegroundColor Green
        } else {
            Write-Host "  SKIP: $f (not found)" -ForegroundColor Yellow
        }
    }

    Write-Host "重载 backend（信号重载，不断 SQLite）..." -ForegroundColor Cyan
    # 用 SIGHUP 重载 uvicorn worker，不杀进程，SQLite 连接不断
    ssh -i $KEY $SERVER "
        pid=\$(docker exec ubuntu-backend-1 sh -c 'pgrep -f uvicorn | head -1' 2>/dev/null)
        if [ -n \"\$pid\" ]; then
            docker exec ubuntu-backend-1 kill -HUP \$pid 2>/dev/null
            echo \"信号重载完成\"
        else
            docker restart ubuntu-backend-1 2>/dev/null
            echo \"fallback: 全量重启\"
        fi
        sleep 2
        docker logs --tail=3 ubuntu-backend-1
    "
}

# ── 前端 ──
if (-not $BackendOnly) {
    Write-Host "=== 前端 ===" -ForegroundColor Cyan

    Set-Location F:\StoryDaemon\frontend
    npm run build 2>&1 | Select-Object -Last 5

    # 整个 dist 打包传输，不会漏文件
    $distDir = "F:\StoryDaemon\frontend\dist"
    $tarFile = "/tmp/inkforge-dist.tar"

    Write-Host "上传前端包..." -ForegroundColor Cyan
    ssh -i $KEY $SERVER "rm -f $tarFile"
    & tar -cf - -C $distDir . | ssh -i $KEY $SERVER "cat > $tarFile"

    Write-Host "部署到容器..." -ForegroundColor Cyan
    ssh -i $KEY $SERVER @"
        docker exec ubuntu-frontend-1 sh -c 'rm -rf /usr/share/nginx/html/assets'
        docker cp $tarFile ubuntu-frontend-1:/tmp/dist.tar
        docker exec ubuntu-frontend-1 sh -c 'cd /usr/share/nginx/html && tar xf /tmp/dist.tar && rm /tmp/dist.tar'
        rm $tarFile
"@

    Write-Host "前端完成" -ForegroundColor Green
}

Write-Host "`n部署完成" -ForegroundColor Cyan
