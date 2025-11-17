"""Power Automate flow commands using Management API."""
import json
import typer
import os
from typing import Optional
from pathlib import Path

from ..client import get_client, get_dataverse_client
from ..output import (
    format_response,
    print_success,
    print_error,
    print_info,
    print_warning,
    handle_api_error,
    ClientError,
)

app = typer.Typer(help="Manage Power Automate flows via Management API")


@app.command("list")
def list_flows(
    ctx: typer.Context,
    top: int = typer.Option(50, "--top", help="Number of flows to return"),
    show_solution: bool = typer.Option(False, "--show-solution", help="Show solution information in table"),
):
    """
    List all Power Automate flows in the environment.

    This uses the Power Automate Management API to list flows and retrieves
    corresponding Dataverse workflow IDs for detailed querying.

    Examples:
        powerautomate flow list
        powerautomate --table flow list
        powerautomate flow list --top 10
        powerautomate --table flow list --show-solution
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

        # Always get Dataverse workflow mappings
        # All Power Automate flows have corresponding Dataverse workflows
        workflow_map = {}
        try:
            dv_client = get_dataverse_client()

            # Get all workflow IDs from Dataverse
            # Query by workflowid to find matches
            flow_ids = [f.get("name", "") for f in flows]

            # Try direct lookup first (flow ID might match workflow ID)
            for flow_id in flow_ids:
                try:
                    wf = dv_client.get(f"workflows({flow_id})", {
                        "$select": "workflowid"
                    })
                    workflow_map[flow_id] = wf.get("workflowid")
                except:
                    # Flow ID doesn't match workflow ID directly
                    pass

            # For any unmapped flows, search by name in workflows table
            unmapped = [fid for fid in flow_ids if fid not in workflow_map]
            if unmapped:
                for flow in flows:
                    flow_id = flow.get("name", "")
                    if flow_id in workflow_map:
                        continue

                    display_name = flow.get("properties", {}).get("displayName", "")
                    if display_name:
                        try:
                            # Search by display name
                            wf_result = dv_client.get("workflows", {
                                "$select": "workflowid,name",
                                "$filter": f"name eq '{display_name}'",
                                "$top": 1
                            })
                            wf_list = wf_result.get("value", [])
                            if wf_list:
                                workflow_map[flow_id] = wf_list[0].get("workflowid")
                        except:
                            pass
        except Exception as e:
            print_info(f"Note: Could not retrieve Dataverse workflow mappings: {e}")

        # Build display data with dataverse_workflow_id
        display_flows = []
        for flow in flows:
            flow_id = flow.get("name", "")
            dv_workflow_id = workflow_map.get(flow_id, flow_id)

            flow_data = {
                "name": flow.get("properties", {}).get("displayName", ""),
                "id": flow_id,
                "dataverse_workflow_id": dv_workflow_id,
                "state": flow.get("properties", {}).get("state", ""),
                "created": flow.get("properties", {}).get("createdTime", ""),
            }
            if show_solution:
                flow_data["solution_id"] = flow.get("properties", {}).get("solutionId", "")
            display_flows.append(flow_data)

        # Define columns for table output
        columns = ["name", "id", "dataverse_workflow_id", "state", "created"]
        if show_solution:
            columns.append("solution_id")

        # Use centralized output handler
        format_response(display_flows, ctx, columns=columns)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("get")
def get_flow(
    ctx: typer.Context,
    flow_id: str = typer.Argument(..., help="Flow ID (name, not GUID)"),
):
    """
    Get detailed information about a specific flow.

    Examples:
        powerautomate flow get <flow-id>
        powerautomate flow get <flow-id> --file flow.json
    """
    try:
        client = get_client()
        result = client.get(f"flows/{flow_id}")
        format_response(result, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("create")
def create_flow(
    ctx: typer.Context,
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

        format_response(result_info, ctx)

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
    no_confirm: bool = typer.Option(False, "--no-confirm", "--yes", "-y", help="Skip confirmation prompts"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before updating"),
):
    """
    Update an existing Power Automate flow.

    This command supports two update modes:

    1. Property updates (PATCH): Update name, state, or solution
    2. Definition file (PATCH): Update complete flow from JSON file

    Examples:
        # Update properties only
        powerautomate flow update <flow-id> --name "New Name"
        powerautomate flow update <flow-id> --state started
        powerautomate flow update <flow-id> --solution ProgressContentAutomation

        # Update from definition file
        powerautomate flow update <flow-id> --definition-file flow.json

        # Skip confirmation prompts
        powerautomate flow update <flow-id> --definition-file flow.json --no-confirm

        # Don't create backup
        powerautomate flow update <flow-id> --definition-file flow.json --no-backup
    """
    try:
        client = get_client()

        # Determine update mode
        is_definition_update = definition_file is not None
        is_property_update = name or description or state or solution or solution_id

        if is_definition_update and is_property_update:
            print_error("Cannot combine property updates with definition updates")
            print_info("Use either --name/--description/--state/--solution OR --definition-file")
            raise typer.Exit(1)

        if not is_definition_update and not is_property_update:
            print_error("No update parameters provided")
            print_info("Use --name, --description, --state, --solution, or --definition-file")
            raise typer.Exit(1)

        # Property updates use PATCH (simpler, only specified fields)
        if is_property_update:
            _update_flow_properties(client, flow_id, name, description, state, solution, solution_id)
            return

        # Definition updates use PUT (complete flow object)
        if definition_file:
            _update_flow_from_file(client, flow_id, definition_file, backup, no_confirm)

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
    ctx: typer.Context,
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
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
        powerautomate --table flow runs <flow-id>
        powerautomate --table flow runs <flow-id> --failed
        powerautomate flow runs <flow-id> --succeeded --top 10
        powerautomate flow runs <flow-id> --filter "status eq 'Failed'"
    """
    try:
        # Use Power Automate Management API for flow runs
        client = get_client()

        # Build Power Automate API endpoint (client.get() prepends environment path)
        endpoint = f"flows/{flow_id}/runs"

        # Build query parameters
        params = {
            "api-version": "2016-11-01",
            "$top": min(top, 100)
        }

        # Add status filter if specified
        if failed:
            params["$filter"] = "status eq 'Failed'"
        elif succeeded:
            params["$filter"] = "status eq 'Succeeded'"
        elif running:
            params["$filter"] = "status eq 'Running'"
        elif status_filter:
            params["$filter"] = status_filter

        # Query flow runs from Power Automate Management API
        result = client.get(endpoint, params=params)

        # Extract runs from response
        runs = result.get("value", [])

        if not runs:
            print_error("No runs found")
            return

        # Build display data
        display_runs = []
        for run in runs:
            # Power Automate API fields
            props = run.get("properties", {})
            run_name = run.get("name", "")[:8] + "..."  # Truncate ID
            status = props.get("status", "")
            start_time = props.get("startTime", "")
            end_time = props.get("endTime", "")
            error = props.get("error", {}).get("code", "") or ""

            display_runs.append({
                "run_id": run_name,
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
                "error": error
            })

        # Use centralized output handler
        format_response(display_runs, ctx, columns=["run_id", "status", "start_time", "end_time", "error"])

        # Show pagination info
        if len(runs) == top:
            print_info(f"More results available. Showing first {len(runs)} runs.")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("run")
def get_run(
    ctx: typer.Context,
    flow_id: str = typer.Argument(..., help="Flow ID (name)"),
    run_id: str = typer.Argument(..., help="Run ID (name)"),
):
    """
    Get detailed information about a specific flow run.

    Examples:
        powerautomate flow run <flow-id> <run-id>
        powerautomate flow run <flow-id> <run-id> --file run.json
    """
    try:
        client = get_client()

        # Get specific run details
        params = {"api-version": "2016-11-01"}
        result = client.get(f"flows/{flow_id}/runs/{run_id}", params=params)

        format_response(result, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)
