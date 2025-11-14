"""Power Automate flow commands using Management API."""
import json
import typer
from typing import Optional
from pathlib import Path

from ..client import get_client
from ..output import (
    print_json,
    print_table,
    print_success,
    print_error,
    print_info,
    handle_api_error,
    format_response,
    ClientError,
)

app = typer.Typer(help="Manage Power Automate flows via Management API")


@app.command("list")
def list_flows(
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
    top: int = typer.Option(50, "--top", help="Number of flows to return"),
):
    """
    List all Power Automate flows in the environment.

    This uses the Power Automate Management API to list flows
    that are properly registered with resourceid.

    Examples:
        powerautomate flow list
        powerautomate flow list --table
        powerautomate flow list --top 10
    """
    try:
        client = get_client()

        # Query flows using Power Automate API
        params = {"$top": top}
        result = client.get("flows", params=params)

        # Extract flows from response
        flows = result.get("value", [])

        if not flows:
            print_error("No flows found")
            return

        # Format for display
        if table_format:
            display_flows = []
            for flow in flows:
                display_flows.append({
                    "name": flow.get("properties", {}).get("displayName", ""),
                    "id": flow.get("name", ""),
                    "state": flow.get("properties", {}).get("state", ""),
                    "created": flow.get("properties", {}).get("createdTime", ""),
                })
            print_table(display_flows, ["name", "id", "state", "created"])
        else:
            print_json(flows)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("get")
def get_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name, not GUID)"),
):
    """
    Get detailed information about a specific flow.

    Examples:
        powerautomate flow get <flow-id>
    """
    try:
        client = get_client()
        result = client.get(f"flows/{flow_id}")
        print_json(result)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("create")
def create_flow(
    name: str = typer.Option(..., "--name", "-n", help="Flow display name"),
    trigger: str = typer.Option("http", "--trigger", help="Trigger type: http, manual"),
    solution: Optional[str] = typer.Option(None, "--solution", "-s", help="Solution unique name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Flow description"),
):
    """
    Create a new Power Automate flow using the Management API.

    This properly registers the flow with the Power Automate service,
    ensuring it has a resourceid and appears in the portal.

    Examples:
        powerautomate flow create --name "My Flow" --trigger http
        powerautomate flow create --name "My Flow" --trigger http --solution ProgressContentAutomation
    """
    try:
        client = get_client()

        # Build flow definition based on trigger type
        if trigger.lower() == "http":
            trigger_def = {
                "manual": {
                    "type": "Request",
                    "kind": "Http",
                    "inputs": {
                        "schema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                }
            }
        elif trigger.lower() == "manual":
            trigger_def = {
                "manual": {
                    "type": "Request",
                    "kind": "Button",
                    "inputs": {
                        "schema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                }
            }
        else:
            print_error(f"Unsupported trigger type: {trigger}")
            raise typer.Exit(1)

        # Build flow definition
        flow_definition = {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "$connections": {
                    "defaultValue": {},
                    "type": "Object"
                },
                "$authentication": {
                    "defaultValue": {},
                    "type": "SecureObject"
                }
            },
            "triggers": trigger_def,
            "actions": {},
            "outputs": {}
        }

        # Build request payload for Power Automate API
        flow_data = {
            "properties": {
                "displayName": name,
                "definition": flow_definition,
                "connectionReferences": {},
                "state": "Stopped"
            }
        }

        if description:
            flow_data["properties"]["description"] = description

        # If solution specified, need to add solution context
        if solution:
            flow_data["properties"]["solutionId"] = solution

        # Create the flow via Management API
        result = client.post("flows", flow_data)

        flow_id = result.get("name")
        flow_name = result.get("properties", {}).get("displayName")

        print_success(f"Flow created successfully: {flow_id}")
        print_json({"flow_id": flow_id, "name": flow_name, "trigger": trigger})

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("update")
def update_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New display name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    state: Optional[str] = typer.Option(None, "--state", help="State: started, stopped"),
):
    """
    Update an existing Power Automate flow.

    Examples:
        powerautomate flow update <flow-id> --name "New Name"
        powerautomate flow update <flow-id> --state started
    """
    try:
        client = get_client()

        # Build update payload
        update_data = {"properties": {}}

        if name:
            update_data["properties"]["displayName"] = name
        if description:
            update_data["properties"]["description"] = description
        if state:
            state_value = "Started" if state.lower() == "started" else "Stopped"
            update_data["properties"]["state"] = state_value

        if not update_data["properties"]:
            print_error("No update parameters provided")
            raise typer.Exit(1)

        client.patch(f"flows/{flow_id}", update_data)
        print_success(f"Flow updated successfully: {flow_id}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("delete")
def delete_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Delete a Power Automate flow.

    Examples:
        powerautomate flow delete <flow-id>
        powerautomate flow delete <flow-id> --yes
    """
    try:
        if not confirm:
            confirmed = typer.confirm(f"Are you sure you want to delete flow {flow_id}?")
            if not confirmed:
                print_error("Delete cancelled")
                raise typer.Exit(0)

        client = get_client()
        client.delete(f"flows/{flow_id}")
        print_success(f"Flow deleted successfully: {flow_id}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("start")
def start_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
):
    """
    Start (turn on) a Power Automate flow.

    Examples:
        powerautomate flow start <flow-id>
    """
    try:
        client = get_client()
        update_data = {"properties": {"state": "Started"}}
        client.patch(f"flows/{flow_id}", update_data)
        print_success(f"Flow started successfully: {flow_id}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("stop")
def stop_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
):
    """
    Stop (turn off) a Power Automate flow.

    Examples:
        powerautomate flow stop <flow-id>
    """
    try:
        client = get_client()
        update_data = {"properties": {"state": "Stopped"}}
        client.patch(f"flows/{flow_id}", update_data)
        print_success(f"Flow stopped successfully: {flow_id}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("runs")
def list_runs(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
    top: int = typer.Option(50, "--top", help="Number of runs to return (max 100)"),
    status_filter: Optional[str] = typer.Option(None, "--filter", help="Filter by status (e.g., 'Succeeded', 'Failed', 'Running')"),
    failed: bool = typer.Option(False, "--failed", help="Show only failed runs"),
    succeeded: bool = typer.Option(False, "--succeeded", help="Show only successful runs"),
    running: bool = typer.Option(False, "--running", help="Show only running flows"),
):
    """
    List run history for a specific flow.

    Power Automate retains the last 28 days of run history.
    API returns maximum 100 runs per request.

    Examples:
        powerautomate flow runs <flow-id>
        powerautomate flow runs <flow-id> --table
        powerautomate flow runs <flow-id> --failed --table
        powerautomate flow runs <flow-id> --succeeded --top 10
        powerautomate flow runs <flow-id> --filter "status eq 'Failed'"
    """
    try:
        client = get_client()

        # Build query parameters
        params = {"api-version": "2016-11-01", "$top": min(top, 100)}

        # Handle status filters
        if failed:
            params["$filter"] = "status eq 'Failed'"
        elif succeeded:
            params["$filter"] = "status eq 'Succeeded'"
        elif running:
            params["$filter"] = "status eq 'Running'"
        elif status_filter:
            params["$filter"] = status_filter

        # Query flow runs
        result = client.get(f"flows/{flow_id}/runs", params=params)

        # Extract runs from response
        runs = result.get("value", [])

        if not runs:
            print_error("No runs found")
            return

        # Format for display
        if table_format:
            display_runs = []
            for run in runs:
                props = run.get("properties", {})
                display_runs.append({
                    "name": run.get("name", ""),
                    "status": props.get("status", ""),
                    "start_time": props.get("startTime", ""),
                    "end_time": props.get("endTime", ""),
                    "trigger": props.get("trigger", {}).get("name", ""),
                })
            print_table(display_runs, ["name", "status", "start_time", "end_time", "trigger"])
        else:
            print_json(runs)

        # Show pagination info if there are more results
        if "nextLink" in result:
            print_info(f"More results available. Showing first {len(runs)} runs.")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("run")
def get_run(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    run_id: str = typer.Argument(..., help="Run ID (name)"),
):
    """
    Get detailed information about a specific flow run.

    Examples:
        powerautomate flow run <flow-id> <run-id>
    """
    try:
        client = get_client()

        # Get specific run details
        params = {"api-version": "2016-11-01"}
        result = client.get(f"flows/{flow_id}/runs/{run_id}", params=params)

        print_json(result)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)
