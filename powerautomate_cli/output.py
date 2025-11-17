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


def _clean_metadata(data: Any) -> Any:
    """
    Recursively remove @odata metadata fields from response data.

    Args:
        data: Data to clean (dict, list, or primitive)

    Returns:
        Cleaned data with @odata fields removed
    """
    if isinstance(data, dict):
        # Remove @odata fields and recursively clean nested objects
        cleaned = {}
        for k, v in data.items():
            if not k.startswith("@odata"):
                cleaned[k] = _clean_metadata(v)
        return cleaned
    elif isinstance(data, list):
        # Recursively clean list items
        return [_clean_metadata(item) for item in data]
    else:
        # Return primitives unchanged
        return data


def _infer_columns(data: list[Dict[str, Any]]) -> list[str]:
    """
    Infer column names from a list of dictionaries.

    Args:
        data: List of dictionaries

    Returns:
        List of column names (keys from first item)
    """
    if not data or not isinstance(data, list) or not isinstance(data[0], dict):
        return []
    return list(data[0].keys())


def format_response(data: Any, ctx: typer.Context, columns: Optional[list[str]] = None):
    """
    Universal output function for all Power Automate CLI commands.

    Handles:
    - Raw vs cleaned output (--raw flag)
    - JSON vs table format (--table flag)
    - File vs console output (--file flag)
    - Recursive metadata removal

    Args:
        data: Raw API response data
        ctx: Typer context containing global flags
        columns: Optional column list for table output (auto-inferred if not provided)
    """
    # Get flags from context
    output_raw = ctx.obj.get('output_raw', False) if ctx and ctx.obj else False
    output_table = ctx.obj.get('output_table', False) if ctx and ctx.obj else False
    output_file = ctx.obj.get('output_file') if ctx and ctx.obj else None

    # Step 1: Clean metadata (unless --raw flag is set)
    if not output_raw:
        data = _clean_metadata(data)

    # Step 2: Determine output format and generate output
    if output_table:
        # Table output
        # Ensure data is a list for table display
        if isinstance(data, dict) and "value" in data:
            table_data = data["value"]
        elif isinstance(data, list):
            table_data = data
        else:
            # Single item - wrap in list
            table_data = [data] if isinstance(data, dict) else []

        # Infer columns if not provided
        if not columns:
            columns = _infer_columns(table_data)

        if not table_data:
            output_text = "No data found"
        else:
            # Generate table
            table = Table(show_header=True, header_style="bold magenta")
            for col in columns:
                table.add_column(col, no_wrap=False, overflow="fold")

            for row in table_data:
                table.add_row(*[str(row.get(col, "")) for col in columns])

            # Output table
            if output_file:
                # For file output, convert table to text representation
                # Rich doesn't have great file export, so convert to JSON instead
                output_text = json.dumps(table_data, indent=2, default=str, ensure_ascii=True)
            else:
                # Print table to console
                console.print(table)
                return
    else:
        # JSON output
        if isinstance(data, str):
            output_text = data
        else:
            output_text = json.dumps(data, indent=2, default=str, ensure_ascii=True)

    # Step 3: Output to file or console
    if output_file:
        with open(output_file, 'w') as f:
            f.write(output_text)
        print_success(f"Output saved to {output_file}")
    else:
        print(output_text)
