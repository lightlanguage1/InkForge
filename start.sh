#!/usr/bin/env bash
set -e

echo
echo "  ╔══════════════════════════════════════╗"
echo "  ║     InkForge — 小说生成系统       ║"
echo "  ╚══════════════════════════════════════╝"
echo

# -------- 检查 Python ----------
if ! command -v python3 &>/dev/null; then
    echo "[ERR] 未找到 Python3，请先安装 Python 3.10+"
    exit 1
fi

PYVER=$(python3 --version 2>&1 | awk '{print $2}')
echo "[OK] Python $PYVER"

# -------- 创建虚拟环境 ----------
if [ ! -d ".venv" ]; then
    echo
    echo "[*] 正在创建虚拟环境..."
    python3 -m venv .venv
    echo "[OK] 虚拟环境已创建"
fi

# -------- 激活虚拟环境 ----------
source .venv/bin/activate

# -------- 检查安装 ----------
if ! pip show inkforge &>/dev/null; then
    echo
    echo "[*] 正在安装依赖..."
    pip install -e . -q
    echo "[OK] 依赖已安装"
fi

# -------- 检查配置文件 ----------
mkdir -p "$HOME/.inkforge"
if [ ! -f "$HOME/.inkforge/config.yaml" ]; then
    echo
    echo "[*] 首次运行 — 使用默认配置"
    echo "    配置文件: $HOME/.inkforge/config.yaml"
fi

# -------- 选择运行模式 ----------
echo
echo "  请选择运行模式:"
echo
echo "  [1] 启动 Web 界面 (推荐，浏览器操作)"
echo "  [2] 命令行模式 (终端操作)"
echo "  [3] 创建新项目 (CLI)"
echo
read -p "  输入选择 [1-3]: " choice

case $choice in
    1)
        echo
        echo "  正在启动 Web 服务..."
        echo "  打开浏览器访问: http://localhost:8221/docs"
        echo
        novel serve --host 0.0.0.0 --port 8221
        ;;
    2)
        echo
        echo "  可用命令: novel new / novel tick / novel run / novel status ..."
        echo "  输入 novel --help 查看全部命令"
        echo
        exec "$SHELL"
        ;;
    3)
        echo
        read -p "  项目名称: " name
        novel new "$name"
        echo
        echo "[OK] 项目已创建"
        echo "  进入项目目录后运行: novel tick"
        ;;
esac
