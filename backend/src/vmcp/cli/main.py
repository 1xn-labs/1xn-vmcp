"""
vMCP CLI - Command Line Interface
==================================

Provides command-line tools for managing vMCP servers and configurations.
"""

import traceback

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from vmcp.config import settings
from vmcp.utilities.logging import get_logger

app = typer.Typer(
    name="vmcp",
    help="vMCP - Virtual Model Context Protocol CLI",
    add_completion=False
)

console = Console()


# ============================================================================
# Server Commands
# ============================================================================

@app.command("run")
def run(
    host: str = typer.Option(None, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
    skip_db_check: bool = typer.Option(False, "--skip-db-check", help="Skip database connectivity check"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser after starting")
):
    """
    Run vMCP with automatic setup (single command start).

    This command:
    - Checks database connectivity
    - Runs database migrations if needed
    - Starts the FastAPI server
    - Opens the web interface in your browser

    Example:
        uvx vmcp run
        vmcp run --port 8080
        vmcp run --no-open
    """
    import time
    import webbrowser

    console.print(Panel.fit(
        "[bold green]vMCP - Virtual Model Context Protocol[/bold green]\n\n"
        "[cyan]Starting complete vMCP environment...[/cyan]",
        title="vMCP Run",
        border_style="green"
    ))

    # command line params override ENV
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port

    config_show()

    # Step 1: Check database connectivity
    if not skip_db_check:
        console.print("\n[yellow]1. Checking database connectivity...[/yellow]")
        try:
            import os
            from pathlib import Path

            from sqlalchemy import create_engine, text  # type: ignore

            # Default to SQLite for zero-config setup (like Langflow)
            default_db_dir = Path.home() / ".vmcp"
            default_db_dir.mkdir(parents=True, exist_ok=True)
            default_db_path = default_db_dir / "vmcp.db"

            db_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")

            # Handle PostgreSQL connection string format
            if db_url.startswith("postgresql://"):
                engine = create_engine(db_url.replace("postgresql://", "postgresql+psycopg2://"))
            else:
                engine = create_engine(db_url)

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            if "sqlite" in db_url:
                console.print(f"[green]✓[/green] Database ready (SQLite: {default_db_path})")
            else:
                console.print("[green]✓[/green] Database connected!")
        except Exception as e:
            console.print(f"[red]✗[/red] Database connection failed: {e}")
            console.print("\n[yellow]To use PostgreSQL instead of SQLite:[/yellow]")
            console.print("  docker run -d --name vmcp-postgres \\")
            console.print("    -e POSTGRES_USER=vmcp \\")
            console.print("    -e POSTGRES_PASSWORD=vmcp \\")
            console.print("    -e POSTGRES_DB=vmcp \\")
            console.print("    -p 5432:5432 postgres:16")
            console.print("  export DATABASE_URL=postgresql://vmcp:vmcp@localhost:5432/vmcp")
            raise typer.Exit(code=1) from e

    # Step 2: Initialize database tables
    console.print("\n[yellow]2. Initializing database...[/yellow]")
    try:
        from vmcp.storage.database import init_db
        from vmcp.storage.dummy_user import ensure_dummy_user

        # Create tables if they don't exist
        init_db()

        # Ensure dummy user exists
        ensure_dummy_user()

        console.print("[green]✓[/green] Database initialized!")

        # Always load/update the MCP registry
        console.print("\n[yellow]3. Loading preconfigured MCP servers...[/yellow]")
        from vmcp.scripts.upload_preconfigured_servers import main as upload_main

        upload_main()

        # Upload demo VMcPs
        console.print("\n[yellow]4. Loading demo VMcPs...[/yellow]")
        try:
            from vmcp.scripts.upload_all_demo_vmcps import main as upload_demo_main
            upload_demo_main()
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Warning: Could not upload demo VMcPs: {e}")
            console.print("    Continuing anyway (demo VMcPs may already exist)")

        # Upload and import 1xndemo (to public registry, then import to private)
        console.print("\n[yellow]5. Loading and importing 1xndemo vMCP...[/yellow]")
        try:
            from vmcp.scripts.upload_and_import_1xndemo import main as upload_1xndemo_main
            upload_1xndemo_main()
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Warning: Could not upload/import 1xndemo: {e}")
            console.print("    Continuing anyway (1xndemo may already exist)")

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Database initialization warning: {e}")
        console.print("    Continuing anyway (database may already be initialized)")

    # Step 6: Start the server
    console.print("\n[yellow]6. Starting vMCP server...[/yellow]")
    console.print(Panel.fit(
        f"[bold cyan]Server Configuration[/bold cyan]\n\n"
        f"URL: [green]{settings.base_url}[/green]\n"
        f"API: [green]{settings.base_url}/api[/green]\n"
        f"Docs: [green]{settings.base_url}/docs[/green]\n"
        f"Documentation: [green]{settings.base_url}/documentation[/green]",
        border_style="cyan"
    ))

    # Open browser after server health check
    if open_browser:
        def open_browser_when_ready():
            import httpx

            max_attempts = 30  # 15 seconds total (30 * 0.5s)
            for _ in range(max_attempts):
                try:
                    response = httpx.get(f"{settings.base_url}/api/mcps/health", timeout=1.0)
                    if response.status_code == 200:
                        # Server is ready!
                        time.sleep(0.5)  # Small buffer for final setup
                        webbrowser.open(f"{settings.base_url}")
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                time.sleep(0.5)
            # Fallback: open anyway after timeout
            webbrowser.open(f"{settings.base_url}")

        import threading

        browser_thread = threading.Thread(target=open_browser_when_ready, daemon=True)
        browser_thread.start()

    # Start uvicorn
    import uvicorn

    from vmcp.core.services import register_oss_services
    from vmcp.proxy_server import create_app

    # Register OSS services before creating app
    register_oss_services()
    logger = get_logger(__name__)
    logger.info("✅ OSS services registered")

    fastapi_app = create_app()

    console.print("\n[green]✓[/green] vMCP is running!\n")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        uvicorn.run(
            fastapi_app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down vMCP...[/yellow]")
        console.print("[green]✓[/green] Goodbye!")


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload (development)"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Log level (debug, info, warning, error)")
):
    """
    Start the vMCP server (without automatic setup).

    Example:
        vmcp serve
        vmcp serve --port 8080 --reload
    """
    import uvicorn

    # Register OSS services before importing proxy_server
    from vmcp.core.services import register_oss_services
    register_oss_services()

    from vmcp.proxy_server import create_app

    fastapi_app = create_app()

    console.print(Panel.fit(
        f"[bold green]Starting vMCP Server[/bold green]\n\n"
        f"Host: [cyan]{host}[/cyan]\n"
        f"Port: [cyan]{port}[/cyan]\n"
        f"Reload: [cyan]{reload}[/cyan]\n"
        f"Log Level: [cyan]{log_level}[/cyan]",
        title="vMCP Server",
        border_style="green"
    ))

    uvicorn.run(
        fastapi_app,
        host=settings.host,
        port=settings.port,
        reload=reload,
        log_level=log_level
    )


@app.command("version")
def version():
    """Show vMCP version information."""
    rprint(Panel.fit(
        "[bold cyan]vMCP - Virtual Model Context Protocol[/bold cyan]\n\n"
        "Version: [green]0.1.0[/green]\n"
        "Python Package: [green]vmcp[/green]",
        title="Version Info",
        border_style="cyan"
    ))


@app.command("info")
def info():
    """Show vMCP system information."""
    rprint(Panel.fit(
        "[bold cyan]vMCP - Virtual Model Context Protocol[/bold cyan]\n\n"
        "[bold]Features:[/bold]\n"
        "  • MCP Server Management\n"
        "  • Virtual MCP Aggregation\n"
        "  • Custom Tools (Prompt/Python/HTTP)\n"
        "  • Variable Substitution (@param, @config, @tool, @resource, @prompt)\n"
        "  • Jinja2 Templates\n"
        "  • OpenAI Apps SDK Widgets\n"
        "  • Multiple Auth Types (Bearer, API Key, Basic, Custom)\n"
        "  • Transport Types (stdio, SSE, HTTP)\n\n"
        "[bold]Documentation:[/bold] https://docs.vmcp.dev\n"
        "[bold]Repository:[/bold] https://github.com/vmcp/vmcp",
        title="System Info",
        border_style="cyan"
    ))


# ============================================================================
# Database Commands
# ============================================================================

db_app = typer.Typer(help="Database management commands")
app.add_typer(db_app, name="db")


@db_app.command("init")
def db_init():
    """
    Initialize the database schema.

    Example:
        vmcp db init
    """
    try:
        from vmcp.storage.database import init_db

        console.print("[yellow]Initializing database...[/yellow]")
        init_db()
        console.print("[green]✓[/green] Database initialized successfully!")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize database: {e}")
        raise typer.Exit(code=1) from e


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Option("head", "--revision", "-r", help="Alembic revision to upgrade to")
):
    """
    Run database migrations.

    Example:
        vmcp db upgrade
        vmcp db upgrade --revision head
    """
    try:
        import subprocess

        console.print(f"[yellow]Running database migrations to {revision}...[/yellow]")
        result = subprocess.run(
            ["alembic", "upgrade", revision],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print("[green]✓[/green] Database upgraded successfully!")
            if result.stdout:
                console.print(result.stdout)
        else:
            console.print("[red]✗[/red] Database upgrade failed:")
            console.print(result.stderr)
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to upgrade database: {e}")
        raise typer.Exit(code=1) from e


@db_app.command("status")
def db_status():
    """
    Show database migration status.

    Example:
        vmcp db status
    """
    try:
        import subprocess

        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print("[bold]Database Migration Status:[/bold]")
            console.print(result.stdout)
        else:
            console.print("[red]✗[/red] Failed to get database status:")
            console.print(result.stderr)
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get database status: {e}")
        raise typer.Exit(code=1) from e


# ============================================================================
# MCP Commands
# ============================================================================

mcp_app = typer.Typer(help="MCP server management commands")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("list")
def mcp_list():
    """
    List all installed MCP servers.

    Example:
        vmcp mcp list
    """
    try:
        from vmcp.mcps.mcp_configmanager import MCPConfigManager

        config_manager = MCPConfigManager(user_id="1")
        servers = config_manager.list_servers()

        if not servers:
            console.print("[yellow]No MCP servers installed.[/yellow]")
            return

        table = Table(title="Installed MCP Servers", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Auto-Connect", style="magenta")
        table.add_column("Tools", justify="right", style="blue")

        for server in servers:
            table.add_row(
                server.name,
                server.transport_type.value,
                server.status.value,
                "✓" if server.auto_connect else "✗",
                str(len(server.tools or []))
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list MCP servers: {e}")
        raise typer.Exit(code=1) from e


@mcp_app.command("load-registry")
def mcp_load_registry(
    force: bool = typer.Option(False, "--force", "-f", help="Force reload even if registry already populated")
):
    """
    Load preconfigured MCP servers into the global registry.

    This command reads the preconfigured-servers.json file and populates
    the global_mcp_server_registry table with publicly available MCP servers.

    Example:
        vmcp mcp load-registry
        vmcp mcp load-registry --force
    """
    try:
        from vmcp.scripts.upload_preconfigured_servers import main as upload_main

        console.print(Panel.fit(
            "[bold cyan]Loading MCP Server Registry[/bold cyan]\n\n"
            "Populating database with preconfigured MCP servers...",
            title="MCP Registry",
            border_style="cyan"
        ))

        upload_main()

        console.print("\n[green]✓[/green] MCP server registry loaded successfully!")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load MCP registry: {e}")
        traceback.print_exc()
        raise typer.Exit(code=1) from e


# ============================================================================
# vMCP Commands
# ============================================================================

vmcp_app = typer.Typer(help="Virtual MCP management commands")
app.add_typer(vmcp_app, name="vmcp")


@vmcp_app.command("list")
def vmcp_list():
    """
    List all vMCPs.

    Example:
        vmcp vmcp list
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager

        manager = VMCPConfigManager(user_id="1")
        vmcps = manager.list_available_vmcps()

        if not vmcps:
            console.print("[yellow]No vMCPs configured.[/yellow]")
            return

        table = Table(title="Configured vMCPs", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Tools", justify="right", style="blue")
        table.add_column("Resources", justify="right", style="green")
        table.add_column("Prompts", justify="right", style="yellow")

        for vmcp in vmcps:
            table.add_row(
                vmcp.get("name", ""),
                vmcp.get("description", "")[:50] + "..." if len(vmcp.get("description", "")) > 50 else vmcp.get("description", ""),
                str(vmcp.get("total_tools", 0)),
                str(vmcp.get("total_resources", 0)),
                str(vmcp.get("total_prompts", 0))
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list vMCPs: {e}")
        raise typer.Exit(code=1) from e


@vmcp_app.command("info")
def vmcp_info(
    vmcp_id: str = typer.Argument(..., help="vMCP ID")
):
    """
    Show detailed information about a vMCP.

    Example:
        vmcp vmcp info my-vmcp-id
    """
    try:
        from vmcp.vmcps.vmcp_config_manager import VMCPConfigManager

        manager = VMCPConfigManager(user_id="1", vmcp_id=vmcp_id)
        config = manager.load_vmcp_config(vmcp_id)

        if not config:
            console.print(f"[red]✗[/red] vMCP not found: {vmcp_id}")
            raise typer.Exit(code=1)

        info_text = (
            f"[bold cyan]Name:[/bold cyan] {config.name}\n"
            f"[bold cyan]ID:[/bold cyan] {config.id}\n"
            f"[bold cyan]Description:[/bold cyan] {config.description or 'N/A'}\n\n"
            f"[bold]Capabilities:[/bold]\n"
            f"  Tools: {config.total_tools}\n"
            f"  Resources: {config.total_resources}\n"
            f"  Resource Templates: {config.total_resource_templates}\n"
            f"  Prompts: {config.total_prompts}\n\n"
            f"[bold]Custom:[/bold]\n"
            f"  Custom Tools: {len(config.custom_tools or [])}\n"
            f"  Custom Prompts: {len(config.custom_prompts or [])}\n"
            f"  Custom Resources: {len(config.custom_resources or [])}\n\n"
            f"[bold cyan]Created:[/bold cyan] {config.created_at}\n"
            f"[bold cyan]Updated:[/bold cyan] {config.updated_at}"
        )

        rprint(Panel.fit(info_text, title=f"vMCP: {config.name}", border_style="cyan"))

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get vMCP info: {e}")
        raise typer.Exit(code=1) from e

# ============================================================================
# Config Commands
# ============================================================================

config_app = typer.Typer(help="Configuration management commands")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """
    Show current configuration.

    Example:
        vmcp config show
    """
    try:
        from vmcp.config import settings

        # Detect database type from connection string
        db_type = "PostgreSQL" if "postgresql" in settings.database_url else "SQLite"

        config_text = (
            f"[bold]Environment:[/bold] {settings.env}\n\n"
            f"[bold]Server:[/bold]\n"
            f"  Host: {settings.host}\n"
            f"  Port: {settings.port}\n"
            f"  Url: {settings.base_url}\n"
            f"[bold]Database:[/bold]\n"
            f"  Type: {db_type}\n"
            f"  Host: {settings.database_url}\n"
            # f"  Port: {settings.}\n"
            # f"  Name: {settings.d}\n\n"
            f"[bold]Logging:[/bold]\n"
            f"  Level: {settings.log_level}\n"
            f"  Format: {settings.log_format}"
        )

        rprint(Panel.fit(config_text, title="Configuration", border_style="cyan"))

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to show configuration: {e}")
        raise typer.Exit(code=1) from e



# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
