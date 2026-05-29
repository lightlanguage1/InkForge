"""统一日志管理 — 文件滚动 + 控制台双输出。"""

import logging
import os
import stat
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "novel_agent"
_FILE_FORMATTER = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_CONSOLE_FORMATTER = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def setup_logging(level: int = logging.INFO, log_dir: Path | None = None) -> None:
    """配置双输出日志（控制台 + 滚动文件）。

    Args:
        level: 日志级别，默认 INFO
        log_dir: 日志目录，默认 <cwd>/logs
    """
    root = logging.getLogger(_LOGGER_NAME)
    if root.handlers:
        return

    root.setLevel(level)

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_CONSOLE_FORMATTER)
    root.addHandler(console)

    # 文件 handler
    log_path = _resolve_log_path(log_dir)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(_FILE_FORMATTER)
        root.addHandler(file_handler)
    except OSError:
        root.warning("无法创建日志文件 %s，仅使用控制台输出", log_path)


def get_log_path(log_dir: Path | None = None) -> Path:
    return _resolve_log_path(log_dir)


def _resolve_log_path(log_dir: Path | None) -> Path:
    base = log_dir or (Path.cwd() / "logs")
    return base / "storydaemon.log"


def rmtree_force(path: Path) -> None:
    """删除目录树，兼容 Windows 只读文件。"""
    import shutil

    def _on_error(func, fpath, _exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_on_error)
