# InkForge 部署文档

**版本**: beta (内测)
**域名**: `https://inkforge.irynekoneko.club`
**服务器**: 腾讯云 106.54.6.71 (Ubuntu 24.04)
**日期**: 2026-06-01

---

## 架构

```
用户 → Nginx (:443) → /api/* → Backend Nginx (:8000) → Uvicorn (:9000, 4 workers)
                     → /*     → 静态文件 (React SPA)

数据: Docker 卷 inkforge_data (/app/work) 持久化 SQLite + 项目文件
模型: Docker 卷 chroma_cache 持久化 ChromaDB 79MB ONNX 模型
证书: Docker 卷 certs 持久化 Let's Encrypt 证书
```

## 部署命令

```bash
# 首次部署 (代码已有，镜像已构建)
cd ~ && docker compose -f docker-compose.prod.yml up -d

# 日常更新 (推代码后)
scp 改动的文件 ubuntu@106.54.6.71:/tmp/
ssh ubuntu@106.54.6.71 "docker cp /tmp/xxx.py ubuntu-backend-1:/app/... && docker restart ubuntu-backend-1"

# 完整重建 (仅当 Dockerfile 或依赖变化时)
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d
```

## 性能配置

| 配置 | 值 | 说明 |
|------|-----|------|
| uvicorn workers | 4 | 并发处理请求 |
| SSE 生成 | 线程池 (max 20) | 不阻塞 event loop |
| ChromaDB SQLite timeout | 60s | 防 upsert 超时 |
| LLM 模型 | deepseek-chat (V4 Flash) | DeepSeek API 直连 |
| API key | 见服务器 .env 文件 | 轮询池 |

## 邀请码

一码一人，max_uses=1，过期 2026-06-06。

管理员: IF-0E617B72 (咕咕嘎嘎)

已使用 (7个): IF-0E617B72, IF-4F15C8A8, IF-C7631AEF, IF-BA04D104, IF-A3E749A6, IF-01437914, IF-141FA023

未使用 (15个): IF-06F14158, IF-4BF02BCD, IF-50B4C1D2, IF-5C73868D, IF-6F1F415A, IF-84847F78, IF-98DB1AF2, IF-C4C2DEAC, IF-C5F6ED9A, IF-CB23D8F9, IF-D0212E80, IF-DDBE95E7, IF-E0BAAC06, IF-EB10A6F3, IF-F29AA375

## 监控

每 30 分钟自动检查：Health / 容器状态 / 用户数 / 项目数。记录在 BETA_MONITOR.md
