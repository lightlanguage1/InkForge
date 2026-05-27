@echo off
chcp 65001 >nul
title StoryDaemon

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     StoryDaemon — 小说生成系统       ║
echo   ╚══════════════════════════════════════╝
echo.

:: -------- 检查 Python ----------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERR] 未找到 Python，请先安装 Python 3.10+
    echo       下载: https://www.python.org/downloads/
    echo       安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER%

:: -------- 创建虚拟环境 ----------
if not exist ".venv\" (
    echo.
    echo [*] 正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERR] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
)

:: -------- 激活虚拟环境 ----------
call .venv\Scripts\activate.bat

:: -------- 检查安装 ----------
pip show storydaemon >nul 2>&1
if errorlevel 1 (
    echo.
    echo [*] 正在安装依赖...
    pip install -e . -q
    if errorlevel 1 (
        echo [ERR] 依赖安装失败
        pause
        exit /b 1
    )
    echo [OK] 依赖已安装
)

:: -------- 检查配置文件 ----------
if not exist "%USERPROFILE%\.storydaemon\" mkdir "%USERPROFILE%\.storydaemon"
if not exist "%USERPROFILE%\.storydaemon\config.yaml" (
    echo.
    echo [*] 首次运行 — 使用默认配置
    echo     配置文件: %USERPROFILE%\.storydaemon\config.yaml
    echo     修改此文件可切换 LLM 后端 / 模型
)

:: -------- 选择运行模式 ----------
echo.
echo   请选择运行模式:
echo.
echo   [1] 启动 Web 界面 (推荐，浏览器操作)
echo   [2] 命令行模式 (终端操作)
echo   [3] 创建新项目 (CLI)
echo.
set /p choice="  输入选择 [1-3]: "

if "%choice%"=="1" goto web
if "%choice%"=="2" goto cli
if "%choice%"=="3" goto new
goto end

:web
echo.
echo   正在启动 Web 服务...
echo   打开浏览器访问: http://localhost:8221/docs
echo.
novel serve --host 0.0.0.0 --port 8221
goto end

:cli
echo.
echo   可用命令: novel new / novel tick / novel run / novel status / novel list ...
echo   输入 novel --help 查看全部命令
echo.
cmd /k ".venv\Scripts\activate.bat"
goto end

:new
echo.
set /p name="  项目名称: "
novel new %name%
if not errorlevel 1 (
    echo.
    echo [OK] 项目已创建
    echo   进入项目目录后运行: novel tick
)
goto end

:end
pause
