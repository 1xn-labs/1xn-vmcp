"""
vMCP SDK CLI - Command line interface for vMCP operations.

This CLI is designed for use in sandbox environments and works with the vMCP
associated with the current sandbox (detected from .vmcp-config.json).
"""

import json
import logging
import sys
import asyncio

import typer
from rich.console import Console
from rich.table import Table

from ..client import VMCPClient
from ..exceptions import (
    VMCPNotFoundError,
    VMCPToolNotFoundError,
    VMCPToolExecutionError,
)

app = typer.Typer(
    name="vmcp",
    help="vMCP SDK - Command line interface for Virtual MCP Servers",
    add_completion=False,
    invoke_without_command=True
)

console = Console()

# Global flag for debug mode
_debug_mode = False


def _run_async(coro):
    """Helper to run async functions."""
    import asyncio
    return asyncio.run(coro)


def _get_client():
    """Get VMCPClient for the current sandbox's vMCP."""
    try:
        client = VMCPClient()  # Auto-detects from sandbox config
        return client
    except VMCPNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Hint: Make sure you're in a sandbox directory with .vmcp-config.json[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error initializing vMCP client: {e}[/red]")
        console.print("[yellow]Please check your vMCP configuration[/yellow]")
        sys.exit(1)


@app.callback()
def main_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging for SDK operations"),
):
    """
    vMCP SDK - Command line interface for Virtual MCP Servers.

    This CLI works with the vMCP associated with the current sandbox.
    The vMCP is automatically detected from .vmcp-config.json in the sandbox directory.

    Example:
        vmcp_sdk_cli list-tools          # List tools in the sandbox's vMCP
        vmcp_sdk_cli list-prompts        # List prompts in the sandbox's vMCP
        vmcp_sdk_cli list-resources      # List resources in the sandbox's vMCP
        vmcp_sdk_cli --debug list-tools  # List tools with debug logging enabled
    """
    global _debug_mode
    _debug_mode = debug

    # Configure SDK logging if --debug flag is set
    if debug:
        sdk_logger = logging.getLogger('vmcp_sdk')
        sdk_logger.setLevel(logging.DEBUG)
        sdk_logger.propagate = False  # Don't propagate to root logger
        # Add a console handler if none exists
        if not sdk_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('[%(name)s] %(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            sdk_logger.addHandler(handler)
        console.print("[dim]Debug logging enabled for SDK[/dim]")

@app.command()
def show_vmcp():
    """
    Show the current active vMCP info and stats

    Example:
        vmcp_sdk_cli show-vmcp
    """
    client = _get_client()
    vmcp_config = client._vmcpconfig

    if not vmcp_config:
        console.print("[yellow]No vMCP configuration found.[/yellow]")
        return

    # Basic Info Section
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]                    vMCP Configuration                      [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    info_table = Table(show_header=False, box=None, padding=(0, 2))
    info_table.add_column("Property", style="bold yellow", width=25)
    info_table.add_column("Value", style="white")

    info_table.add_row("vMCP ID", vmcp_config.id or "N/A")
    info_table.add_row("Name", vmcp_config.name or "N/A")
    info_table.add_row("Description", vmcp_config.description or "N/A")
    info_table.add_row("User ID", vmcp_config.user_id or "N/A")

    console.print(info_table)
    console.print()

    # Feature flags section - highlighted
    metadata = vmcp_config.metadata if hasattr(vmcp_config, 'metadata') else {}
    if isinstance(metadata, dict):
        sandbox_enabled = metadata.get('sandbox_enabled', False) is True
        progressive_discovery_enabled = metadata.get('progressive_discovery_enabled', False) is True

        console.print("[bold cyan]Features:[/bold cyan]")
        features_table = Table(show_header=False, box=None, padding=(0, 2))
        features_table.add_column("Feature", style="bold yellow", width=30)
        features_table.add_column("Status", style="white")

        # Highlight enabled features
        sandbox_status = "[bold green]✓ ENABLED[/bold green]" if sandbox_enabled else "[dim red]✗ Disabled[/dim red]"
        progressive_status = "[bold green]✓ ENABLED[/bold green]" if progressive_discovery_enabled else "[dim red]✗ Disabled[/dim red]"

        features_table.add_row("Sandbox Mode", sandbox_status)
        features_table.add_row("Progressive Discovery", progressive_status)

        console.print(features_table)
        console.print()

    # Stats Section
    console.print("[bold cyan]Stats:[/bold cyan]")
    stats_table = Table(show_header=False, box=None, padding=(0, 2))
    stats_table.add_column("Metric", style="bold green", width=30)
    stats_table.add_column("Count", style="white", justify="right")

    # Count selected servers
    selected_servers = []
    if hasattr(vmcp_config, 'vmcp_config') and vmcp_config.vmcp_config:
        selected_servers = vmcp_config.vmcp_config.get('selected_servers', []) if isinstance(vmcp_config.vmcp_config, dict) else getattr(vmcp_config.vmcp_config, 'selected_servers', [])
    stats_table.add_row("Selected MCP Servers", str(len(selected_servers)))

    # Count custom items
    stats_table.add_row("Custom Prompts", str(len(vmcp_config.custom_prompts or [])))
    stats_table.add_row("Custom Tools", str(len(vmcp_config.custom_tools or [])))
    stats_table.add_row("Custom Resources", str(len(vmcp_config.custom_resources or [])))
    stats_table.add_row("Custom Resource Templates", str(len(vmcp_config.custom_resource_templates or [])))
    stats_table.add_row("Custom Resource URIs", str(len(vmcp_config.custom_resource_uris or [])))
    stats_table.add_row("Environment Variables", str(len(vmcp_config.environment_variables or [])))
    stats_table.add_row("Uploaded Files", str(len(vmcp_config.uploaded_files or [])))
    stats_table.add_row("Custom Context Items", str(len(vmcp_config.custom_context or [])))
    stats_table.add_row("Custom Widgets", str(len(vmcp_config.custom_widgets or [])))

    console.print(stats_table)
    console.print()

    # System Prompt Info
    if vmcp_config.system_prompt:
        console.print("[bold cyan]System Prompt:[/bold cyan]")
        sp = vmcp_config.system_prompt
        sp_text = sp.get('text', '') if isinstance(sp, dict) else getattr(sp, 'text', '')
        sp_vars = sp.get('variables', []) if isinstance(sp, dict) else getattr(sp, 'variables', [])

        # Truncate long system prompts
        if len(sp_text) > 200:
            console.print(f"  {sp_text[:200]}... [dim](truncated)[/dim]")
        else:
            console.print(f"  {sp_text}")

        if sp_vars:
            console.print(f"  [dim]Variables: {len(sp_vars)}[/dim]")
        console.print()

    # Selected Servers Details
    if selected_servers:
        console.print("[bold cyan]Selected MCP Servers:[/bold cyan]")
        servers_table = Table(show_header=True, header_style="bold magenta")
        servers_table.add_column("Server Name", style="cyan")
        servers_table.add_column("Server ID", style="yellow")
        servers_table.add_column("Transport", style="green")

        for server in selected_servers:
            server_name = server.get('name', 'N/A') if isinstance(server, dict) else getattr(server, 'name', 'N/A')
            server_id = server.get('server_id', 'N/A') if isinstance(server, dict) else getattr(server, 'id', 'N/A')
            transport = server.get('transport_type', 'N/A') if isinstance(server, dict) else getattr(server, 'transport_type', 'N/A')
            servers_table.add_row(server_name, server_id, transport)

        console.print(servers_table)
        console.print()

    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")
    
@app.command()
def list_tools():
    """
    List all tools available in the sandbox's vMCP.
    Includes MCP server tools and sandbox-discovered tools.
    
    Example:
        vmcp_sdk_cli list-tools
    """
    try:
        client = _get_client()
        tools = _run_async(client.list_tools())
        
        if not tools:
            console.print("[yellow]No tools found in the current vMCP.[/yellow]")
            return
        
        # Separate sandbox tools from others
        sandbox_tools = []
        other_tools = []
        
        for tool in tools:
            tool_dict = tool if isinstance(tool, dict) else tool.model_dump() if hasattr(tool, 'model_dump') else {}
            meta = tool_dict.get('meta', {})
            if meta.get('source') == 'sandbox_discovered':
                sandbox_tools.append(tool)
            else:
                other_tools.append(tool)
        
        from ..schema import normalize_name
        
        # Show other tools first
        if other_tools:
            table = Table(title="MCP Server Tools", show_header=True, header_style="bold cyan")
            table.add_column("Name", style="cyan")
            table.add_column("Python Name", style="green")
            table.add_column("Description", style="white")
            
            for tool in other_tools:
                tool_name = tool.get("name", "") if isinstance(tool, dict) else getattr(tool, "name", str(tool))
                python_name = normalize_name(tool_name)
                tool_desc = tool.get("description", "") if isinstance(tool, dict) else getattr(tool, "description", "")
                table.add_row(
                    tool_name,
                    python_name,
                    (tool_desc or "")[:80] + "..." if len(tool_desc or "") > 80 else (tool_desc or "")
                )
            
            console.print(table)
            console.print()
        
        # Show sandbox tools
        if sandbox_tools:
            table = Table(title="Sandbox-Discovered Tools", show_header=True, header_style="bold green")
            table.add_column("Name", style="cyan")
            table.add_column("Python Name", style="green")
            table.add_column("Description", style="white")
            table.add_column("Source", style="yellow")
            
            for tool in sandbox_tools:
                tool_name = tool.get("name", "") if isinstance(tool, dict) else getattr(tool, "name", str(tool))
                python_name = normalize_name(tool_name)
                tool_desc = tool.get("description", "") if isinstance(tool, dict) else getattr(tool, "description", "")
                meta = tool.get("meta", {}) if isinstance(tool, dict) else getattr(tool, "meta", {})
                source = meta.get("script_path", "unknown")
                
                table.add_row(
                    tool_name,
                    python_name,
                    (tool_desc or "")[:80] + "..." if len(tool_desc or "") > 80 else (tool_desc or ""),
                    source
                )
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing tools: {e}[/red]")
        sys.exit(1)


@app.command()
def list_prompts():
    """
    List all prompts available in the sandbox's vMCP.
    
    Example:
        vmcp_sdk_cli list-prompts
    """
    try:
        client = _get_client()
        prompts = _run_async(client.list_prompts())
        
        if not prompts:
            console.print("[yellow]No prompts found in the current vMCP.[/yellow]")
            return
        
        table = Table(title="Prompts in Current vMCP", show_header=True, header_style="bold cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        for prompt in prompts:
            prompt_name = prompt.get("name", "") if isinstance(prompt, dict) else getattr(prompt, "name", str(prompt))
            prompt_desc = prompt.get("description", "") if isinstance(prompt, dict) else getattr(prompt, "description", "")
            table.add_row(
                prompt_name,
                (prompt_desc or "")[:80] + "..." if len(prompt_desc or "") > 80 else (prompt_desc or "")
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing prompts: {e}[/red]")
        sys.exit(1)


@app.command()
def list_resources():
    """
    List all resources available in the sandbox's vMCP.
    
    Example:
        vmcp_sdk_cli list-resources
    """
    try:
        client = _get_client()
        resources = _run_async(client.list_resources())
        
        if not resources:
            console.print("[yellow]No resources found in the current vMCP.[/yellow]")
            return
        
        table = Table(title="Resources in Current vMCP", show_header=True, header_style="bold cyan")
        table.add_column("URI", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        
        for resource in resources:
            if isinstance(resource, dict):
                table.add_row(
                    resource.get("uri", ""),
                    resource.get("name", ""),
                    (resource.get("description", "") or "")[:60] + "..." if len(resource.get("description", "") or "") > 60 else (resource.get("description", "") or "")
                )
            else:
                table.add_row(
                    getattr(resource, "uri", ""),
                    getattr(resource, "name", ""),
                    (getattr(resource, "description", "") or "")[:60] + "..." if len(getattr(resource, "description", "") or "") > 60 else (getattr(resource, "description", "") or "")
                )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing resources: {e}[/red]")
        sys.exit(1)


async def async_test_sdk():
    # async def add_tool():
    #     # Auto-detect vMCP from sandbox config
    #     client = VMCPClient()

    #     async with VMCPClient() as client:
    #         # Tools are auto-loaded when entering context
    #         result = await client.allfeature_add_numbers(a=5, b=3)
    #         print(f"5 + 3 = {result.value}")
    #     # Auto cleanup when exiting context

    # asyncio.run(add_tool())
    try:
        async with _get_client() as client:
            console.print(f"[green]Executing tool 'allfeature_get_user(user_id=\"Amit\")'...[/green]")

            output = await client.allfeature_get_user(user_id="Amit")
            # Check for errors
            if output.isError:
                console.print(f"[red]Tool execution failed![/red]")
                console.print(f"[red]Error: {output.content}[/red]")
                sys.exit(1)

            # Print result
            console.print("[green]Tool executed successfully![/green]")
            result = output.result
            console.print(json.dumps(result, indent=2))

    except VMCPToolNotFoundError as e:
        console.print(f"[red]Tool not found: {e}[/red]")
        if e.available_tools:
            console.print(f"[yellow]Available tools: {', '.join(e.available_tools)}...[/yellow]")
        sys.exit(1)
    except VMCPToolExecutionError as e:
        console.print(f"[red]Tool execution error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error calling tool: {e}[/red]")
        sys.exit(1)

@app.command()
def test_sdk():
    "Test the SDK"
    asyncio.run(async_test_sdk())




@app.command()
def call_tool(
    tool_name: str = typer.Option(..., "--tool", "-t", help="Name of the tool to call"),
    payload: str = typer.Option({}, "--payload", "-p", help="JSON payload with tool arguments"),
):
    """
    Call a tool in the sandbox's vMCP.

    Example:
        vmcp_sdk_cli call-tool --tool all_feature_add_numbers --payload '{"a": 5, "b": 3}'
    """
    try:
        # Parse payload
        try:
            arguments = json.loads(payload)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON payload: {e}[/red]")
            sys.exit(1)

        # Get client and tool function
        client = _get_client()
        tool_func = client.__getattr__(tool_name)

        if not tool_func:
            raise VMCPToolNotFoundError(tool_name=tool_name)

        # Execute tool (now async)
        console.print(f"[green]Executing tool '{tool_name}'...[/green]")
        output = _run_async(tool_func(**arguments))

        # Check for errors
        if output.isError:
            console.print(f"[red]Tool execution failed![/red]")
            console.print(f"[red]Error: {output.content}[/red]")
            sys.exit(1)

        # Print result
        console.print("[green]Tool executed successfully![/green]")
        result = output.result
        console.print(json.dumps(result, indent=2))

    except VMCPToolNotFoundError as e:
        console.print(f"[red]Tool {tool_name} not found[/red]")
        if e.available_tools:
            console.print(f"[yellow]Available tools: {', '.join(e.available_tools)}...[/yellow]")
        sys.exit(1)
    except VMCPToolExecutionError as e:
        console.print(f"[red]Tool execution error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error calling tool: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()

