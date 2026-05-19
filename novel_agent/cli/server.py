"""CLI command: start StoryDaemon server."""

import typer

from ..configs.constants import DEFAULT_HOST, DEFAULT_PORT


def start_server(
    host: str = typer.Option(DEFAULT_HOST, "--host", "-h", help="Listen address"),
    port: int = typer.Option(DEFAULT_PORT, "--port", "-p", help="Listen port"),
    reload: bool = typer.Option(False, "--reload", help="Hot reload (development only)"),
):
    """Start the StoryDaemon API server.

    Runs as a persistent process providing REST API access.
    """
    typer.echo(f"  StoryDaemon Server starting on {host}:{port}")

    import uvicorn
    uvicorn.run(
        "novel_agent.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
