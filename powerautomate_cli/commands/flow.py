"""Power Automate flow commands using Management API."""
import json
import typer
import tempfile
import subprocess
import os
from typing import Optional
from pathlib import Path

from ..client import get_client
from ..output import (
    print_json,
    print_table,
    print_success,
    print_error,
    print_info,
    print_warning,
    handle_api_error,
    format_response,
    ClientError,
)

app = typer.Typer(help="Manage Power Automate flows via Management API")


@app.command("list")
def list_flows(
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
    top: int = typer.Option(50, "--top", help="Number of flows to return"),
    show_solution: bool = typer.Option(False, "--show-solution", help="Show solution information in table"),
):
    """
    List all Power Automate flows in the environment.

    This uses the Power Automate Management API to list flows
    that are properly registered with resourceid.

    Examples:
        powerautomate flow list
        powerautomate flow list --table
        powerautomate flow list --top 10
        powerautomate flow list --table --show-solution
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
                flow_data = {
                    "name": flow.get("properties", {}).get("displayName", ""),
                    "id": flow.get("name", ""),
                    "state": flow.get("properties", {}).get("state", ""),
                    "created": flow.get("properties", {}).get("createdTime", ""),
                }
                if show_solution:
                    flow_data["solution_id"] = flow.get("properties", {}).get("solutionId", "")
                display_flows.append(flow_data)

            columns = ["name", "id", "state", "created"]
            if show_solution:
                columns.append("solution_id")

            print_table(display_flows, columns)
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
    solution: Optional[str] = typer.Option(None, "--solution", "-s", help="Solution unique name or ID"),
    solution_id: Optional[str] = typer.Option(None, "--solution-id", help="Solution ID (GUID) - alternative to --solution"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Flow description"),
):
    """
    Create a new Power Automate flow using the Management API.

    This properly registers the flow with the Power Automate service,
    ensuring it has a resourceid and appears in the portal.

    Examples:
        powerautomate flow create --name "My Flow" --trigger http
        powerautomate flow create --name "My Flow" --trigger http --solution ProgressContentAutomation
        powerautomate flow create --name "My Flow" --trigger http --solution-id <guid>
    """
    try:
        client = get_client()

        # Resolve solution if specified
        resolved_solution_id = None
        if solution_id:
            resolved_solution_id = solution_id
        elif solution:
            print_info(f"Resolving solution: {solution}")
            resolved_solution_id = client.resolve_solution_id(solution)
            print_info(f"Solution ID: {resolved_solution_id}")

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

        # If solution specified, add solution context
        if resolved_solution_id:
            flow_data["properties"]["solutionId"] = resolved_solution_id

        # Create the flow via Management API
        result = client.post("flows", flow_data)

        flow_id = result.get("name")
        flow_name = result.get("properties", {}).get("displayName")

        print_success(f"Flow created successfully: {flow_id}")

        result_info = {"flow_id": flow_id, "name": flow_name, "trigger": trigger}
        if resolved_solution_id:
            result_info["solution_id"] = resolved_solution_id

        print_json(result_info)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("update")
def update_flow(
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New display name"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    state: Optional[str] = typer.Option(None, "--state", help="State: started, stopped"),
    solution: Optional[str] = typer.Option(None, "--solution", "-s", help="Move flow to solution (unique name or ID)"),
    solution_id: Optional[str] = typer.Option(None, "--solution-id", help="Move flow to solution (GUID)"),
    definition_file: Optional[Path] = typer.Option(None, "--definition-file", "-f", help="JSON file with flow definition"),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open flow in editor for interactive editing"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation prompts"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before updating"),
):
    """
    Update an existing Power Automate flow.

    This command supports multiple update modes:

    1. Property updates (PATCH): Update name, state, or solution
    2. Definition file (PATCH): Update complete flow from JSON file
    3. Interactive edit (PATCH): Edit flow definition in $EDITOR

    Examples:
        # Update properties only
        powerautomate flow update <flow-id> --name "New Name"
        powerautomate flow update <flow-id> --state started
        powerautomate flow update <flow-id> --solution ProgressContentAutomation

        # Update from definition file
        powerautomate flow update <flow-id> --definition-file flow.json

        # Interactive editing
        powerautomate flow update <flow-id> --edit

        # Skip confirmation prompts
        powerautomate flow update <flow-id> --definition-file flow.json --no-confirm

        # Don't create backup
        powerautomate flow update <flow-id> --edit --no-backup
    """
    try:
        client = get_client()

        # Determine update mode
        is_definition_update = definition_file is not None or edit
        is_property_update = name or description or state or solution or solution_id

        if is_definition_update and is_property_update:
            print_error("Cannot combine property updates with definition updates")
            print_info("Use either --name/--description/--state/--solution OR --definition-file/--edit")
            raise typer.Exit(1)

        if not is_definition_update and not is_property_update:
            print_error("No update parameters provided")
            print_info("Use --name, --description, --state, --solution, --definition-file, or --edit")
            raise typer.Exit(1)

        # Property updates use PATCH (simpler, only specified fields)
        if is_property_update:
            _update_flow_properties(client, flow_id, name, description, state, solution, solution_id)
            return

        # Definition updates use PUT (complete flow object)
        if definition_file:
            _update_flow_from_file(client, flow_id, definition_file, backup, no_confirm)
        elif edit:
            _update_flow_interactive(client, flow_id, backup, no_confirm)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


def _update_flow_properties(
    client,
    flow_id: str,
    name: Optional[str],
    description: Optional[str],
    state: Optional[str],
    solution: Optional[str],
    solution_id: Optional[str],
):
    """Update flow properties using PATCH with full flow object."""
    # Power Automate API requires full flow object for PATCH
    # Get current flow first
    current_flow = client.get(f"flows/{flow_id}")

    # Resolve solution if specified
    resolved_solution_id = None
    if solution_id:
        resolved_solution_id = solution_id
    elif solution:
        print_info(f"Resolving solution: {solution}")
        resolved_solution_id = client.resolve_solution_id(solution)
        print_info(f"Solution ID: {resolved_solution_id}")

    # Update specific properties
    if name:
        current_flow["properties"]["displayName"] = name
    if description:
        current_flow["properties"]["description"] = description
    if state:
        state_value = "Started" if state.lower() == "started" else "Stopped"
        current_flow["properties"]["state"] = state_value
    if resolved_solution_id:
        current_flow["properties"]["solutionId"] = resolved_solution_id

    # Send PATCH with full flow object
    client.patch(f"flows/{flow_id}", current_flow)
    print_success(f"Flow properties updated successfully: {flow_id}")

    if resolved_solution_id:
        print_info(f"Flow moved to solution: {resolved_solution_id}")


def _update_flow_from_file(client, flow_id: str, definition_file: Path, backup: bool, no_confirm: bool):
    """Update flow from JSON definition file using PATCH."""
    # Validate file exists
    if not definition_file.exists():
        raise ClientError(f"Definition file not found: {definition_file}")

    # Read and validate JSON
    try:
        with open(definition_file, 'r') as f:
            new_definition = json.load(f)
    except json.JSONDecodeError as e:
        raise ClientError(f"Invalid JSON in definition file: {e}")

    # Validate it's a flow object
    if "properties" not in new_definition:
        raise ClientError("Definition file must contain a 'properties' object")

    # Get current flow for backup and comparison
    current_flow = client.get(f"flows/{flow_id}")

    # Create backup if requested
    if backup:
        backup_file = Path(f"{flow_id}_backup_{int(os.times().elapsed * 1000)}.json")
        with open(backup_file, 'w') as f:
            json.dump(current_flow, f, indent=2)
        print_info(f"Backup created: {backup_file}")

    # Show what's changing (if not skipping confirmation)
    if not no_confirm:
        print_info("Current flow properties:")
        current_props = current_flow.get("properties", {})
        print_info(f"  Name: {current_props.get('displayName', 'N/A')}")
        print_info(f"  State: {current_props.get('state', 'N/A')}")

        print_info("\nNew flow properties:")
        new_props = new_definition.get("properties", {})
        print_info(f"  Name: {new_props.get('displayName', 'N/A')}")
        print_info(f"  State: {new_props.get('state', 'N/A')}")

        confirmed = typer.confirm("\nProceed with update?")
        if not confirmed:
            print_warning("Update cancelled")
            raise typer.Exit(0)

    # Update using PATCH with full flow object
    result = client.patch(f"flows/{flow_id}", new_definition)
    print_success(f"Flow definition updated successfully: {flow_id}")

    # Show updated properties
    updated_props = result.get("properties", {})
    print_info(f"Updated name: {updated_props.get('displayName', 'N/A')}")
    print_info(f"Updated state: {updated_props.get('state', 'N/A')}")


def _update_flow_interactive(client, flow_id: str, backup: bool, no_confirm: bool):
    """Open flow definition in editor for interactive editing using PATCH."""
    # Get current flow
    current_flow = client.get(f"flows/{flow_id}")

    # Create backup if requested
    if backup:
        backup_file = Path(f"{flow_id}_backup_{int(os.times().elapsed * 1000)}.json")
        with open(backup_file, 'w') as f:
            json.dump(current_flow, f, indent=2)
        print_info(f"Backup created: {backup_file}")

    # Create temporary file with current definition
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(current_flow, temp_file, indent=2)
        temp_path = temp_file.name

    try:
        # Get editor from environment or use default
        editor = os.environ.get('EDITOR', 'nano')

        # Open editor
        print_info(f"Opening flow in {editor}...")
        print_info("Save and close the editor to apply changes, or exit without saving to cancel")
        subprocess.run([editor, temp_path], check=True)

        # Read edited content
        with open(temp_path, 'r') as f:
            edited_definition = json.load(f)

        # Validate it's still a valid flow object
        if "properties" not in edited_definition:
            raise ClientError("Edited definition must contain a 'properties' object")

        # Check if anything changed
        if edited_definition == current_flow:
            print_info("No changes detected")
            raise typer.Exit(0)

        # Show what's changing (if not skipping confirmation)
        if not no_confirm:
            print_info("Changes detected:")
            current_props = current_flow.get("properties", {})
            edited_props = edited_definition.get("properties", {})

            if current_props.get("displayName") != edited_props.get("displayName"):
                print_info(f"  Name: {current_props.get('displayName')} → {edited_props.get('displayName')}")
            if current_props.get("state") != edited_props.get("state"):
                print_info(f"  State: {current_props.get('state')} → {edited_props.get('state')}")
            if current_props.get("definition") != edited_props.get("definition"):
                print_info("  Definition: Changed")

            confirmed = typer.confirm("\nProceed with update?")
            if not confirmed:
                print_warning("Update cancelled")
                raise typer.Exit(0)

        # Update using PATCH with full flow object
        result = client.patch(f"flows/{flow_id}", edited_definition)
        print_success(f"Flow definition updated successfully: {flow_id}")

        # Show updated properties
        updated_props = result.get("properties", {})
        print_info(f"Updated name: {updated_props.get('displayName', 'N/A')}")
        print_info(f"Updated state: {updated_props.get('state', 'N/A')}")

    except json.JSONDecodeError as e:
        raise ClientError(f"Invalid JSON after editing: {e}")
    except subprocess.CalledProcessError:
        print_warning("Editor exited with error, update cancelled")
        raise typer.Exit(1)
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


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
