"""Power Automate solution commands using Power Apps API.

NOTE: Solution operations require direct Dataverse API access with appropriate permissions.
For comprehensive solution management, use the dataverse-cli tool which has full
Dataverse API support with both delegated and service principal authentication.

These commands provide basic solution querying functionality for convenience.
"""
import typer
from typing import Optional

from ..client import get_client
from ..output import (
    format_response,
    print_success,
    print_error,
    print_info,
    print_warning,
    handle_api_error,
)

app = typer.Typer(help="Manage Power Platform solutions")


@app.command("list")
def list_solutions(
    ctx: typer.Context,
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
    filter_text: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter solutions by name"),
):
    """
    List all solutions in the environment.

    Examples:
        powerautomate solution list
        powerautomate solution list --table
        powerautomate solution list --filter "Progress"
    """
    try:
        client = get_client()
        result = client.list_solutions(filter_text=filter_text)

        # Extract solutions from response
        solutions = result.get("value", [])

        if not solutions:
            print_error("No solutions found")
            return

        # Format for display
        if table_format:
            display_solutions = []
            for solution in solutions:
                props = solution.get("properties", {})
                display_solutions.append({
                    "displayName": props.get("displayName", ""),
                    "uniqueName": props.get("uniqueName", ""),
                    "id": solution.get("name", ""),
                    "version": props.get("version", ""),
                    "publisher": props.get("publisherName", ""),
                })
            format_response(display_solutions, ctx, columns=["displayName", "uniqueName", "id", "version", "publisher"])
        else:
            format_response(solutions, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("get")
def get_solution(
    ctx: typer.Context,
    solution_id: str = typer.Argument(..., help="Solution ID or unique name"),
    by_name: bool = typer.Option(False, "--name", help="Treat argument as solution unique name"),
):
    """
    Get detailed information about a specific solution.

    Examples:
        powerautomate solution get <solution-id>
        powerautomate solution get ProgressContentAutomation --name
    """
    try:
        client = get_client()

        if by_name:
            # Resolve solution name to ID
            solution_id = client.resolve_solution_id(solution_id)

        result = client.get_solution(solution_id)
        format_response(result, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("components")
def list_components(
    ctx: typer.Context,
    solution_id: str = typer.Argument(..., help="Solution ID or unique name"),
    by_name: bool = typer.Option(False, "--name", help="Treat argument as solution unique name"),
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
    component_type: Optional[str] = typer.Option(None, "--type", help="Filter by component type (e.g., 'Workflow')"),
):
    """
    List all components in a solution.

    Examples:
        powerautomate solution components <solution-id>
        powerautomate solution components ProgressContentAutomation --name --table
        powerautomate solution components <solution-id> --type Workflow
    """
    try:
        client = get_client()

        if by_name:
            # Resolve solution name to ID
            solution_id = client.resolve_solution_id(solution_id)

        result = client.get_solution_components(solution_id, component_type=component_type)

        # Extract components from response
        components = result.get("value", [])

        if not components:
            print_error("No components found")
            return

        # Format for display
        if table_format:
            display_components = []
            for component in components:
                props = component.get("properties", {})
                display_components.append({
                    "displayName": props.get("displayName", ""),
                    "type": component.get("type", ""),
                    "id": component.get("name", ""),
                    "createdTime": props.get("createdTime", ""),
                })
            format_response(display_components, ctx, columns=["displayName", "type", "id", "createdTime"])
        else:
            format_response(components, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("flows")
def list_solution_flows(
    ctx: typer.Context,
    solution_id: str = typer.Argument(..., help="Solution ID or unique name"),
    by_name: bool = typer.Option(False, "--name", help="Treat argument as solution unique name"),
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
):
    """
    List all flows in a solution.

    Examples:
        powerautomate solution flows <solution-id>
        powerautomate solution flows ProgressContentAutomation --name --table
    """
    try:
        client = get_client()

        if by_name:
            # Resolve solution name to ID
            solution_id = client.resolve_solution_id(solution_id)

        # Get components filtered by Workflow type
        result = client.get_solution_components(solution_id, component_type="Workflow")

        # Extract flows from response
        flows = result.get("value", [])

        if not flows:
            print_error("No flows found in solution")
            return

        # Format for display
        if table_format:
            display_flows = []
            for flow in flows:
                props = flow.get("properties", {})
                display_flows.append({
                    "displayName": props.get("displayName", ""),
                    "id": flow.get("name", ""),
                    "state": props.get("state", ""),
                    "createdTime": props.get("createdTime", ""),
                })
            format_response(display_flows, ctx, columns=["displayName", "id", "state", "createdTime"])
        else:
            format_response(flows, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)
