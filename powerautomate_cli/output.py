"""Output formatting utilities for Power Automate CLI."""
import json
import re
from typing import Any, Dict, Optional
from functools import wraps
from rich.console import Console
from rich.table import Table
from rich.json import JSON
import typer


console = Console()


# Shared file output option that can be added to any command
file_option = typer.Option(
    None,
    "--file",
    "-f",
    help="Save JSON output to file instead of printing to console",
    show_default=False,
)


def output_json(data: Any, ctx: Optional[typer.Context] = None, file: Optional[str] = None, indent: int = 2):
    """
    Output data as formatted JSON to console or file.

    Checks multiple sources for file output preference:
    1. Direct file parameter (highest priority)
    2. Context object (for global --file parameter)

    Args:
        data: Data to output as JSON
        ctx: Optional Typer context
        file: Optional file path to save JSON to (overrides context)
        indent: Number of spaces for indentation
    """
    # Determine output file (direct parameter takes precedence)
    output_file = file

    # Fall back to context if no direct file parameter
    if output_file is None and ctx and ctx.obj:
        output_file = ctx.obj.get('output_file')

    # Convert data to JSON string
    if isinstance(data, str):
        json_str = data
    else:
        # Use ensure_ascii=True to properly escape control characters (U+0000-U+001F)
        # This ensures valid JSON output even when API responses contain invalid characters
        json_str = json.dumps(data, indent=indent, default=str, ensure_ascii=True)

    # Output to file or console
    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_str)
        print_success(f"JSON saved to {output_file}")
    else:
        # Print JSON string directly without Rich formatting
        # Rich's JSON() class re-parses JSON which causes issues with control characters
        # json.dumps() with ensure_ascii=True properly escapes them, so we print directly
        print(json_str)


# Backwards compatibility alias
print_json = output_json


def print_table(data: list[Dict[str, Any]], columns: list[str]):
    """
    Print data as a formatted table.

    Args:
        data: List of dictionaries to display
        columns: Column names to display
    """
    if not data:
        console.print("[yellow]No data found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")

    for col in columns:
        table.add_column(col, no_wrap=False, overflow="fold")

    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_success(message: str):
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str):
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


class ClientError(Exception):
    """Exception raised for client initialization or API errors."""
    pass


def handle_api_error(error: Exception) -> int:
    """
    Handle API errors and print appropriate messages.

    Args:
        error: Exception to handle

    Returns:
        Exit code (1 for API errors, 2 for client errors)
    """
    if isinstance(error, ClientError):
        print_error(str(error))
        return 2
    elif isinstance(error, ValueError):
        print_error(f"Invalid input: {error}")
        return 1
    else:
        print_error(f"Unexpected error: {error}")
        return 1


def format_response(data: Any) -> Any:
    """
    Format API response for display.

    Removes metadata and cleans up response.

    Args:
        data: Raw API response

    Returns:
        Cleaned response data
    """
    if isinstance(data, dict):
        # Remove metadata
        cleaned = {k: v for k, v in data.items() if not k.startswith("@")}

        # If there's a 'value' key (list response), return that
        if "value" in cleaned and isinstance(cleaned["value"], list):
            return cleaned["value"]

        return cleaned
    return data
