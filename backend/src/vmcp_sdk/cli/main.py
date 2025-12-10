"""
vMCP SDK CLI - Command line interface for vMCP operations.

This CLI is designed for use in sandbox environments and works with the vMCP
associated with the current sandbox (detected from .vmcp-config.json).
"""

import json
import sys

import typer
from rich.console import Console
from rich.table import Table

from ..client import VMCPClient

app = typer.Typer(
    name="vmcp",
    help="vMCP SDK - Command line interface for Virtual MCP Servers",
    add_completion=False,
    invoke_without_command=True
)

console = Console()


def _run_async(coro):
    """Helper to run async functions."""
    import asyncio
    return asyncio.run(coro)


def _get_client():
    """Get VMCPClient for the current sandbox's vMCP."""
    try:
        client = VMCPClient()  # Auto-detects from sandbox config
        if not client.vmcp_id:
            console.print("[red]Error: No vMCP found. Ensure you're in a sandbox directory with .vmcp-config.json[/red]")
            sys.exit(1)
        return client
    except Exception as e:
        console.print(f"[red]Error initializing vMCP client: {e}[/red]")
        console.print("[yellow]Make sure you're in a sandbox directory with .vmcp-config.json[/yellow]")
        sys.exit(1)


@app.callback()
def main_callback(
    ctx: typer.Context,
):
    """
    vMCP SDK - Command line interface for Virtual MCP Servers.
    
    This CLI works with the vMCP associated with the current sandbox.
    The vMCP is automatically detected from .vmcp-config.json in the sandbox directory.
    
    Example:
        vmcp-sdk list-tools          # List tools in the sandbox's vMCP
        vmcp-sdk list-prompts        # List prompts in the sandbox's vMCP
        vmcp-sdk list-resources      # List resources in the sandbox's vMCP
    """


@app.command()
def help():
    """
    Show help information and available commands for vmcp-sdk-cli.
    
    Example:
        vmcp-sdk-cli help
    """
    console.print("\n[bold cyan]vMCP SDK CLI - Help[/bold cyan]\n")
    
    console.print("[bold]Overview:[/bold]")
    console.print("  The vMCP SDK CLI provides commands to interact with your vMCP (Virtual MCP Server)")
    console.print("  from within a sandbox environment. The vMCP is automatically detected from")
    console.print("  .vmcp-config.json in the current sandbox directory.\n")
    
    console.print("[bold]Available Commands:[/bold]\n")
    
    commands_table = Table(show_header=True, header_style="bold cyan", box=None)
    commands_table.add_column("Command", style="cyan", width=20)
    commands_table.add_column("Description", style="white")
    
    commands_table.add_row("help", "Show this help message")
    commands_table.add_row("list-tools", "List all tools available in the vMCP")
    commands_table.add_row("list-prompts", "List all prompts available in the vMCP")
    commands_table.add_row("list-resources", "List all resources available in the vMCP")
    commands_table.add_row("call-tool", "Call a tool with arguments")
    
    console.print(commands_table)
    console.print()
    
    console.print("[bold]Usage Examples:[/bold]\n")
    console.print("  [cyan]vmcp-sdk-cli help[/cyan]")
    console.print("    Show this help message\n")
    console.print("  [cyan]vmcp-sdk-cli list-tools[/cyan]")
    console.print("    List all available tools (MCP server tools and sandbox-discovered tools)\n")
    console.print("  [cyan]vmcp-sdk-cli list-prompts[/cyan]")
    console.print("    List all prompts in the current vMCP\n")
    console.print("  [cyan]vmcp-sdk-cli list-resources[/cyan]")
    console.print("    List all resources in the current vMCP\n")
    console.print("  [cyan]vmcp-sdk-cli call-tool --tool tool_name --payload '{\"arg\": \"value\"}'[/cyan]")
    console.print("    Call a tool with JSON payload\n")
    
    console.print("[bold]Getting Help:[/bold]")
    console.print("  Use [cyan]--help[/cyan] or [cyan]-h[/cyan] with any command for detailed information")
    console.print("  Example: [cyan]vmcp-sdk-cli list-tools --help[/cyan]\n")
    
    console.print("[bold yellow]Note:[/bold yellow] Make sure you're in a sandbox directory with .vmcp-config.json\n")


@app.command()
def list_tools():
    """
    List all tools available in the sandbox's vMCP.
    Includes MCP server tools and sandbox-discovered tools.
    
    Example:
        vmcp-sdk list-tools
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
        vmcp-sdk list-prompts
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
        vmcp-sdk list-resources
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


@app.command()
def call_tool(
    tool_name: str = typer.Option(..., "--tool", "-t", help="Name of the tool to call"),
    payload: str = typer.Option(..., "--payload", "-p", help="JSON payload with tool arguments"),
):
    """
    Call a tool in the sandbox's vMCP.
    
    Example:
        vmcp-sdk call-tool --tool all_feature_add_numbers --payload '{"a": 5, "b": 3}'
    """
    try:
        # Parse payload
        try:
            arguments = json.loads(payload)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON payload: {e}[/red]")
            sys.exit(1)
        
        # Call tool
        client = _get_client()
        
        # Use the typed function if available
        tool_func = client.get_tool_function(tool_name)
        if tool_func:
            console.print(f"Calling tool function: {tool_name}")
            console.print(f"[yellow]Arguments: {arguments}[/yellow]")
            result = tool_func(**arguments)
        else:
            # Fallback to direct call
            from vmcp.vmcps.models import VMCPToolCallRequest
            console.print(f"Call tool directly: {tool_name}")
            console.print(f"[yellow]Arguments: {arguments}[/yellow]")
            request = VMCPToolCallRequest(
                tool_name=tool_name,
                arguments=arguments
            )
            result = _run_async(client.manager.call_tool(
                request,
                connect_if_needed=True,
                return_metadata=False
            ))
        
        # Check if result indicates an error
        is_error = False
        if isinstance(result, dict):
            is_error = result.get('isError', False)
        elif hasattr(result, 'isError'):
            is_error = result.isError
        
        # Print result
        if is_error:
            console.print("[red]Tool execution failed![/red]")
            # Extract error message from content if available
            if isinstance(result, dict):
                content = result.get('content', [])
                if content and isinstance(content, list) and len(content) > 0:
                    error_text = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
                    if error_text:
                        console.print(f"[red]{error_text}[/red]")
        else:
            console.print("[green]Tool executed successfully![/green]")
        
        console.print(json.dumps(result, indent=2, default=str))
        
    except Exception as e:
        console.print(f"[red]Error calling tool: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()

