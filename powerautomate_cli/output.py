"""Output formatting utilities for Power Automate CLI."""
import json
from typing import Any, Dict
from rich.console import Console
from rich.table import Table
from rich.json import JSON


console = Console()


def print_json(data: Any, indent: int = 2):
    """
    Print data as formatted JSON.

    Args:
        data: Data to print as JSON
        indent: Number of spaces for indentation
    """
    if isinstance(data, str):
        console.print(data)
    else:
        console.print(JSON(json.dumps(data, indent=indent, default=str)))


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
        table.add_column(col)

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
