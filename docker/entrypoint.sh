#!/bin/bash
set -e

echo "[entrypoint] Starting nginx + uvicorn"

# Start uvicorn on localhost only (not exposed to public)
uvicorn novel_agent.api.server:app --host 127.0.0.1 --port 9000 &
UVICORN_PID=$!

# Start nginx in foreground (nginx reverse proxies to uvicorn)
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait for either to exit
wait -n $UVICORN_PID $NGINX_PID 2>/dev/null
EXIT_CODE=$?
echo "[entrypoint] Process exited with code $EXIT_CODE, shutting down..."
kill $UVICORN_PID $NGINX_PID 2>/dev/null
exit $EXIT_CODE
