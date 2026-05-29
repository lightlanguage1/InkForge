"""CLI command: start InkForge server."""

import typer

from ..configs.constants import DEFAULT_HOST, DEFAULT_PORT


def start_server(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="Listen address"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Listen port"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="热重载（开发模式，默认开启）"),
):
    """Start the InkForge API server.

    Runs as a persistent process providing REST API access.
    """
    typer.echo(f"  InkForge Server starting on {host}:{port}")

    import uvicorn
    import os
    # Only watch Python source files — prevents JSON/log writes during generation
    # from triggering hot-reload and leaving orphaned processes on random ports.
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run(
        "novel_agent.api.server:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[package_dir] if reload else None,
        reload_includes=["*.py"] if reload else None,
        log_level="info",
    )
