"""Power Automate connector commands using Power Apps API."""
import json
import typer
import tempfile
import subprocess
import os
from typing import Optional
from pathlib import Path

from ..client import get_client
from ..output import (
    format_response,
    print_success,
    print_error,
    print_info,
    print_warning,
    handle_api_error,
    ClientError,
)

app = typer.Typer(help="Manage Power Automate connectors (custom and managed)")


@app.command("list")
def list_connectors(
   ctx: typer.Context,
    custom: bool = typer.Option(False, "--custom", help="Show only custom connectors"),
    managed: bool = typer.Option(False, "--managed", help="Show only managed connectors"),
    filter_text: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter by name or publisher"),
):
    """
    List all connectors (custom and managed) in the environment.

    Connectors include both Microsoft-managed connectors (like Office 365, SharePoint)
    and custom connectors created by users.

    Examples:
        powerautomate connector list
        powerautomate --table connector list
        powerautomate --table connector list --custom
        powerautomate connector list --filter "podio"
        powerautomate connector list --managed --filter "sharepoint"
    """
    try:
        client = get_client()

        # Query connectors using Power Apps API
        result = client.list_connectors(
            filter_text=filter_text,
            custom_only=custom,
            managed_only=managed
        )

        # Extract connectors from response
        connectors = result.get("value", [])

        if not connectors:
            print_error("No connectors found")
            return

        # Build display data
        display_connectors = []
        for connector in connectors:
            props = connector.get("properties", {})

            # Determine connector type
            is_custom = client._is_custom_connector(connector)
            connector_type = "Custom" if is_custom else "Managed"

            # Extract tier (if available)
            tier = props.get("tier", "N/A")

            display_connectors.append({
                "name": props.get("displayName", ""),
                "id": connector.get("name", ""),
                "type": connector_type,
                "publisher": props.get("publisher", ""),
                "tier": tier,
            })

        # Use centralized output handler
        format_response(display_connectors, ctx, columns=["name", "id", "type", "publisher", "tier"])

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("get")
def get_connector(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector ID (name)"),
    operations: bool = typer.Option(False, "--operations", "-o", help="Show operations/actions"),
    permissions: bool = typer.Option(False, "--permissions", "-p", help="Show permissions"),
):
    """
    Get detailed information about a specific connector.

    Shows connector metadata, configuration, and optionally operations/permissions.

    Examples:
        powerautomate connector get shared_podio
        powerautomate connector get shared_office365 --operations
        powerautomate connector get my_custom_connector --permissions
    """
    try:
        client = get_client()

        if permissions:
            # Get connector permissions
            result = client.get_connector_permissions(connector_id)
        else:
            # Get connector details
            result = client.get_connector(connector_id, include_operations=operations)

        format_response(result, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("create")
def create_connector(
    ctx: typer.Context,
    definition_file: Path = typer.Option(..., "--definition-file", "-f", help="JSON file with connector definition"),
):
    """
    Create a new custom connector from a definition file.

    The definition file must be a JSON file containing the complete connector
    specification including name, display name, description, API definition, etc.

    Examples:
        powerautomate connector create --definition-file connector.json

    Note: Only custom connectors can be created. You cannot create or modify
    Microsoft-managed connectors.
    """
    try:
        # Validate file exists
        if not definition_file.exists():
            raise ClientError(f"Definition file not found: {definition_file}")

        # Read and validate JSON
        try:
            with open(definition_file, 'r') as f:
                definition = json.load(f)
        except json.JSONDecodeError as e:
            raise ClientError(f"Invalid JSON in definition file: {e}")

        # Validate required fields
        if "name" not in definition:
            raise ClientError("Definition file must contain a 'name' field")
        if "properties" not in definition:
            raise ClientError("Definition file must contain a 'properties' object")

        client = get_client()

        # Create the connector
        result = client.create_connector(definition)

        connector_name = result.get("properties", {}).get("displayName", result.get("name"))
        print_success(f"Custom connector created successfully: {connector_name}")
        format_response(result, ctx)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("update")
def update_connector(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector ID (name)"),
    definition_file: Optional[Path] = typer.Option(None, "--definition-file", "-f", help="JSON file with updated connector definition"),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open connector in editor for interactive editing"),
    oauth_secret: Optional[str] = typer.Option(None, "--oauth-secret", "-s", help="OAuth client secret (required for OAuth connectors)"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip confirmation prompts"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Create backup before updating"),
):
    """
    Update an existing custom connector.

    IMPORTANT: Update JSON Structure
    ═══════════════════════════════════════════════════════════════════

    Exported connectors contain the full object, but UPDATES require
    a different structure. You MUST restructure the JSON:

    ✓ CORRECT format for updates:
    {
      "properties": {
        "description": "...",
        "connectionParameters": {...},
        "apiDefinitions": {...}
      }
    }

    ✗ WRONG (exported format - do not use for updates):
    {
      "name": "...",
      "id": "...",
      "type": "...",
      "properties": {...}
    }

    Remove These Read-Only Properties:
    ═══════════════════════════════════════════════════════════════════

    These MUST be removed or you'll get errors:
    - displayName (Error: "Cannot update API displayName")
    - environment (Error: "Cannot update API environment")
    - createdTime, changedTime, tier, publisher

    OAuth Connector Updates:
    ═══════════════════════════════════════════════════════════════════

    When updating OAuth settings (token URLs, client ID, etc.), you MUST
    provide --oauth-secret or the update will fail with 403 Forbidden.

    Get secret from: Azure AD > App registrations > Your app > Certificates & secrets

    Quick Guide:
    ═══════════════════════════════════════════════════════════════════

    1. Export: powerautomate connector export <id> --output export.json
    2. Convert to update format (see CONNECTOR_UPDATES.md)
    3. Update: powerautomate connector update <id> --definition-file update.json

    Examples:
        # Non-OAuth update (description, API operations, etc.)
        powerautomate connector update my_connector -f connector.json

        # OAuth update (token URLs, auth endpoints, client ID)
        powerautomate connector update shared_podio -f podio.json --oauth-secret "abc123"

        # Interactive editing (opens in $EDITOR)
        powerautomate connector update my_connector --edit

        # Skip confirmation prompt
        powerautomate connector update my_connector -f connector.json --no-confirm

    See CONNECTOR_UPDATES.md for detailed examples and troubleshooting.
    """
    try:
        client = get_client()

        # Determine update mode
        if not definition_file and not edit:
            print_error("No update method specified")
            print_info("Use either --definition-file or --edit")
            raise typer.Exit(1)

        if definition_file and edit:
            print_error("Cannot use both --definition-file and --edit")
            print_info("Choose one update method")
            raise typer.Exit(1)

        if definition_file:
            _update_connector_from_file(client, connector_id, definition_file, oauth_secret, backup, no_confirm)
        elif edit:
            _update_connector_interactive(client, connector_id, oauth_secret, backup, no_confirm)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


def _update_connector_from_file(client, connector_id: str, definition_file: Path, oauth_secret: Optional[str], backup: bool, no_confirm: bool):
    """Update connector from JSON definition file."""
    # Validate file exists
    if not definition_file.exists():
        raise ClientError(f"Definition file not found: {definition_file}")

    # Read and validate JSON
    try:
        with open(definition_file, 'r') as f:
            new_definition = json.load(f)
    except json.JSONDecodeError as e:
        raise ClientError(f"Invalid JSON in definition file: {e}")

    # Validate it's a connector object
    if "properties" not in new_definition:
        raise ClientError("Definition file must contain a 'properties' object")

    # Get current connector for backup and comparison
    current_connector = client.get_connector(connector_id)

    # Check if it's a custom connector
    if not client._is_custom_connector(current_connector):
        raise ClientError(f"Cannot update managed connector: {connector_id}")

    # Create backup if requested
    if backup:
        backup_file = Path(f"{connector_id}_backup_{int(os.times().elapsed * 1000)}.json")
        with open(backup_file, 'w') as f:
            json.dump(current_connector, f, indent=2)
        print_info(f"Backup created: {backup_file}")

    # Show what's changing (if not skipping confirmation)
    if not no_confirm:
        print_info("Current connector properties:")
        current_props = current_connector.get("properties", {})
        print_info(f"  Name: {current_props.get('displayName', 'N/A')}")
        print_info(f"  Publisher: {current_props.get('publisher', 'N/A')}")

        print_info("\nNew connector properties:")
        new_props = new_definition.get("properties", {})
        print_info(f"  Name: {new_props.get('displayName', 'N/A')}")
        print_info(f"  Publisher: {new_props.get('publisher', 'N/A')}")

        # Check if this is an OAuth connector update
        has_oauth_settings = False
        conn_params = new_props.get("connectionParameters", {})
        if conn_params.get("token", {}).get("oauthSettings"):
            has_oauth_settings = True

        if has_oauth_settings and not oauth_secret:
            print_warning("\nThis appears to be an OAuth connector update.")
            print_warning("For OAuth configuration changes, provide --oauth-secret to ensure the update succeeds.")

        confirmed = typer.confirm("\nProceed with update?")
        if not confirmed:
            print_warning("Update cancelled")
            raise typer.Exit(0)

    # Update the connector (with OAuth secret if provided)
    result = client.update_connector(connector_id, new_definition, client_secret=oauth_secret)
    print_success(f"Custom connector updated successfully: {connector_id}")

    # Show updated properties
    updated_props = result.get("properties", {})
    print_info(f"Updated name: {updated_props.get('displayName', 'N/A')}")

    # Important notice about connections
    print_warning("\nIMPORTANT: Any connections using this connector must be recreated to inherit these schema changes.")
    print_info("Existing connections will continue using the old schema until they are deleted and recreated.")


def _update_connector_interactive(client, connector_id: str, oauth_secret: Optional[str], backup: bool, no_confirm: bool):
    """Open connector definition in editor for interactive editing."""
    # Get current connector
    current_connector = client.get_connector(connector_id)

    # Check if it's a custom connector
    if not client._is_custom_connector(current_connector):
        raise ClientError(f"Cannot update managed connector: {connector_id}")

    # Create backup if requested
    if backup:
        backup_file = Path(f"{connector_id}_backup_{int(os.times().elapsed * 1000)}.json")
        with open(backup_file, 'w') as f:
            json.dump(current_connector, f, indent=2)
        print_info(f"Backup created: {backup_file}")

    # Create temporary file with current definition
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
        json.dump(current_connector, temp_file, indent=2)
        temp_path = temp_file.name

    try:
        # Get editor from environment or use default
        editor = os.environ.get('EDITOR', 'nano')

        # Open editor
        print_info(f"Opening connector in {editor}...")
        print_info("Save and close the editor to apply changes, or exit without saving to cancel")
        subprocess.run([editor, temp_path], check=True)

        # Read edited content
        with open(temp_path, 'r') as f:
            edited_definition = json.load(f)

        # Validate it's still a valid connector object
        if "properties" not in edited_definition:
            raise ClientError("Edited definition must contain a 'properties' object")

        # Check if anything changed
        if edited_definition == current_connector:
            print_info("No changes detected")
            raise typer.Exit(0)

        # Show what's changing (if not skipping confirmation)
        if not no_confirm:
            print_info("Changes detected:")
            current_props = current_connector.get("properties", {})
            edited_props = edited_definition.get("properties", {})

            if current_props.get("displayName") != edited_props.get("displayName"):
                print_info(f"  Name: {current_props.get('displayName')} → {edited_props.get('displayName')}")
            if current_props.get("publisher") != edited_props.get("publisher"):
                print_info(f"  Publisher: {current_props.get('publisher')} → {edited_props.get('publisher')}")
            if current_props.get("apiDefinitions") != edited_props.get("apiDefinitions"):
                print_info("  API Definition: Changed")

            # Check if this is an OAuth connector update
            has_oauth_settings = False
            conn_params = edited_props.get("connectionParameters", {})
            if conn_params.get("token", {}).get("oauthSettings"):
                has_oauth_settings = True

            if has_oauth_settings and not oauth_secret:
                print_warning("\nThis appears to be an OAuth connector update.")
                print_warning("For OAuth configuration changes, provide --oauth-secret to ensure the update succeeds.")

            confirmed = typer.confirm("\nProceed with update?")
            if not confirmed:
                print_warning("Update cancelled")
                raise typer.Exit(0)

        # Update the connector (with OAuth secret if provided)
        result = client.update_connector(connector_id, edited_definition, client_secret=oauth_secret)
        print_success(f"Custom connector updated successfully: {connector_id}")

        # Show updated properties
        updated_props = result.get("properties", {})
        print_info(f"Updated name: {updated_props.get('displayName', 'N/A')}")

        # Important notice about connections
        print_warning("\nIMPORTANT: Any connections using this connector must be recreated to inherit these schema changes.")
        print_info("Existing connections will continue using the old schema until they are deleted and recreated.")

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
def delete_connector(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector ID (name)"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Delete a custom connector.

    Examples:
        powerautomate connector delete my_connector
        powerautomate connector delete my_connector --yes

    Note: Only custom connectors can be deleted. You cannot delete Microsoft-managed connectors.
    """
    try:
        client = get_client()

        # Get connector to verify it's custom
        connector = client.get_connector(connector_id)
        if not client._is_custom_connector(connector):
            raise ClientError(f"Cannot delete managed connector: {connector_id}")

        if not confirm:
            confirmed = typer.confirm(f"Are you sure you want to delete connector {connector_id}?")
            if not confirmed:
                print_error("Delete cancelled")
                raise typer.Exit(0)

        client.delete_connector(connector_id)
        print_success(f"Custom connector deleted successfully: {connector_id}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("export")
def export_connector(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector ID (name)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file path"),
    openapi: bool = typer.Option(False, "--openapi", help="Export OpenAPI/Swagger definition only"),
):
    """
    Export connector definition to a JSON file.

    This exports the complete connector definition which can be used to:
    - Back up custom connectors
    - Version control connector configurations
    - Recreate connectors in other environments

    Examples:
        powerautomate connector export my_connector --output connector.json
        powerautomate connector export shared_podio --output podio.json
        powerautomate connector export my_connector --output swagger.json --openapi
    """
    try:
        client = get_client()

        # Get connector details
        result = client.get_connector(connector_id)

        # If OpenAPI requested, extract just the API definition
        if openapi:
            api_def = result.get("properties", {}).get("apiDefinitions", {})
            if not api_def:
                raise ClientError("Connector does not have an OpenAPI/Swagger definition")
            export_data = api_def
        else:
            export_data = result

        # Write to file
        with open(output, 'w') as f:
            json.dump(export_data, f, indent=2)

        print_success(f"Connector exported to: {output}")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)
