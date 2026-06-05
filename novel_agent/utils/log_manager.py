"""统一日志管理 — 控制台 + 文件双输出，多进程安全。

使用 QueueHandler + QueueListener 模式：
- 所有 worker 进程通过队列发送日志
- 单个 Listener 线程串行写入文件，避免多进程争抢
"""

import atexit
import logging
import logging.handlers
import os
import stat
import sys
from pathlib import Path
from queue import Queue

_LOGGER_NAME = "novel_agent"
_FILE_FORMATTER = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_CONSOLE_FORMATTER = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

_queue: Queue | None = None
_listener: logging.handlers.QueueListener | None = None


def setup_logging(level: int = logging.INFO, log_dir: Path | None = None) -> None:
    """配置日志（多进程安全）。

    主进程调用一次，创建 Queue + Listener。
    Worker 进程通过 QueueHandler 发送日志，Listener 串行写入文件。

    Args:
        level: 日志级别，默认 INFO
        log_dir: 日志目录，默认 <cwd>/logs
    """
    global _queue, _listener

    root = logging.getLogger(_LOGGER_NAME)
    if root.handlers:
        return

    root.setLevel(level)

    # 控制台 handler（每个进程各自写 stdout，天然安全）
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_CONSOLE_FORMATTER)
    root.addHandler(console)

    # 文件 handler — 通过队列串行化，多进程安全
    log_path = _resolve_log_path(log_dir)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(_FILE_FORMATTER)

        _queue = Queue()
        _listener = logging.handlers.QueueListener(_queue, file_handler, respect_handler_level=True)
        _listener.start()
        atexit.register(_stop_listener)

        root.addHandler(logging.handlers.QueueHandler(_queue))
    except OSError:
        root.warning("无法创建日志文件 %s，仅使用控制台输出", log_path)


def _stop_listener():
    global _listener
    if _listener:
        _listener.stop()
        _listener = None


def get_log_path(log_dir: Path | None = None) -> Path:
    return _resolve_log_path(log_dir)


def _resolve_log_path(log_dir: Path | None) -> Path:
    base = log_dir or (Path.cwd() / "logs")
    return base / "inkforge.log"


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
