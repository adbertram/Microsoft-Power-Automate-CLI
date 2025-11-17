"""Connection management commands for Power Automate CLI."""
import typer
import json
from typing import Optional
from ..client import get_client
from ..output import format_response, print_success, print_info, print_error, ClientError


app = typer.Typer(help="Manage Power Automate connections")


@app.command("list")
def list_connections(
    ctx: typer.Context,
    connector_id: Optional[str] = typer.Option(None, "--connector", "-c", help="Filter by connector ID"),
):
    """
    List all connections in the environment.

    Connections are authenticated instances of connectors. Each connection
    stores OAuth credentials and refresh tokens for API access.

    Examples:
        powerautomate connection list
        powerautomate --table connection list
        powerautomate connection list --connector shared_prg-5fpodio-5fd251d00ef0afcb57
    """
    try:
        client = get_client()
        result = client.list_connections(connector_id=connector_id)

        connections = result.get("value", [])
        if not connections:
            print_info("No connections found")
            return

        # Build display data
        table_data = []
        for conn in connections:
            props = conn.get("properties", {})
            table_data.append({
                "name": props.get("displayName", ""),
                "id": conn.get("name", ""),
                "connector": props.get("apiId", "").split("/")[-1] if props.get("apiId") else "",
                "status": props.get("statuses", [{}])[0].get("status", "Unknown") if props.get("statuses") else "Unknown",
                "created": props.get("createdTime", "")[:10] if props.get("createdTime") else "",
            })

        # Use centralized output handler
        format_response(table_data, ctx, columns=["name", "id", "connector", "status", "created"])

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("get")
def get_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID"),
):
    """
    Get detailed information about a specific connection.

    Shows OAuth configuration, status, and refresh token settings.

    Examples:
        powerautomate connection get shared_prg-5fpodio-123456789
    """
    try:
        client = get_client()
        connection = client.get_connection(connection_id)

        format_response(connection, ctx)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("refresh")
def refresh_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID to refresh"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Refresh a connection's OAuth token.

    Forces the connection to request a new access token using its refresh token.
    This is useful when a connection has authentication issues.

    Examples:
        powerautomate connection refresh shared_prg-5fpodio-123456789
        powerautomate connection refresh shared_prg-5fpodio-123456789 --yes
    """
    try:
        if not yes:
            confirm = typer.confirm(f"Refresh connection {connection_id}?")
            if not confirm:
                print_info("Cancelled")
                raise typer.Exit(0)

        client = get_client()
        result = client.refresh_connection(connection_id)

        print_success(f"Connection {connection_id} refreshed successfully")
        format_response(result, ctx)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("test")
def test_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID to test"),
):
    """
    Test a connection to verify it's working properly.

    Attempts to use the connection to make a test API call.

    Examples:
        powerautomate connection test shared_prg-5fpodio-123456789
    """
    try:
        client = get_client()
        result = client.test_connection(connection_id)

        status = result.get("properties", {}).get("statuses", [{}])[0]
        if status.get("status") == "Connected":
            print_success(f"Connection {connection_id} is working!")
        else:
            print_error(f"Connection {connection_id} test failed: {status.get('error', 'Unknown error')}")

        format_response(result, ctx)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("update")
def update_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID"),
    enable_auto_refresh: Optional[bool] = typer.Option(None, "--auto-refresh/--no-auto-refresh", help="Enable/disable automatic token refresh"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Update connection configuration.

    Can enable/disable automatic OAuth token refresh and update other settings.

    Examples:
        powerautomate connection update shared_prg-5fpodio-123456789 --auto-refresh
        powerautomate connection update shared_prg-5fpodio-123456789 --no-auto-refresh
    """
    try:
        client = get_client()

        # Build update payload
        updates = {}
        if enable_auto_refresh is not None:
            updates["enableAutoRefresh"] = enable_auto_refresh

        if not updates:
            print_error("No updates specified. Use --auto-refresh or other options.")
            raise typer.Exit(1)

        result = client.update_connection(connection_id, updates)

        print_success(f"Connection {connection_id} updated")

        if json_output:
            format_response(result, ctx)
        else:
            props = result.get("properties", {})
            print_info(f"Status: {props.get('statuses', [{}])[0].get('status', 'Unknown')}")

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("create")
def create_connection(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector ID (e.g., shared_prg-5fpodio-5fd251d00ef0afcb57)"),
    display_name: str = typer.Option(..., "--name", "-n", help="Display name for the connection"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Create a new connection for a connector.

    NOTE: This command may not work with delegated authentication due to API limitations.
    Connection creation requires admin-level permissions that may not be available with user tokens.

    If this command fails with a 403 error, you must create the connection manually:
    1. Go to https://make.powerautomate.com
    2. Navigate to Data > Connections
    3. Click "New connection" and select your connector
    4. Complete the OAuth authentication flow
    5. Use 'powerautomate connection list --table' to get the new connection ID

    Examples:
        powerautomate connection create shared_prg-5fpodio-5fd251d00ef0afcb57 --name "Podio Connection"
        powerautomate connection create shared_prg-5fpodio-5fd251d00ef0afcb57 -n "My Podio" --json
    """
    try:
        client = get_client()

        print_info(f"Creating connection '{display_name}' for connector {connector_id}...")
        result = client.create_connection(connector_id, display_name)

        print_success(f"Connection created successfully!")
        print_info(f"Connection ID: {result.get('name', 'N/A')}")

        # Check if OAuth authentication is required
        props = result.get("properties", {})
        status = props.get("statuses", [{}])[0].get("status", "")

        if status != "Connected":
            print_info("\nYou must now authenticate this connection:")
            print_info("1. Go to https://make.powerautomate.com")
            print_info("2. Navigate to Data > Connections")
            print_info(f"3. Find connection '{display_name}'")
            print_info("4. Click 'Fix connection' or the connection name")
            print_info("5. Complete the OAuth authentication flow")

        if json_output:
            format_response(result, ctx)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("delete")
def delete_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Delete a connection.

    WARNING: This will break any flows using this connection!

    Examples:
        powerautomate connection delete shared_prg-5fpodio-123456789
        powerautomate connection delete shared_prg-5fpodio-123456789 --yes
    """
    try:
        if not yes:
            print_error("WARNING: This will break any flows using this connection!")
            confirm = typer.confirm(f"Delete connection {connection_id}?")
            if not confirm:
                print_info("Cancelled")
                raise typer.Exit(0)

        client = get_client()
        client.delete_connection(connection_id)

        print_success(f"Connection {connection_id} deleted")

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("recreate")
def recreate_connection(
    ctx: typer.Context,
    connection_id: str = typer.Argument(..., help="Connection ID to recreate"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    [DEPRECATED] Recreate a connection from scratch.

    NOTE: This command does not work with delegated authentication due to API limitations.
    Connection creation requires admin-level permissions not available with user tokens.

    Alternative workflow:
    1. Delete connection: powerautomate connection delete <connection-id> --yes
    2. Create manually at https://make.powerautomate.com > Data > Connections
    3. Authenticate the new connection
    4. List to get new ID: powerautomate connection list --table

    Examples:
        powerautomate connection recreate shared_prg-5fpodio-123456789 (will fail)
    """
    # Show deprecation warning
    print_error("WARNING: This command is deprecated and will not work with delegated authentication.")
    print_info("\nConnection creation requires admin API permissions not available with user authentication.")
    print_info("\nRecommended alternative:")
    print_info("1. powerautomate connection delete <connection-id> --yes")
    print_info("2. Go to https://make.powerautomate.com")
    print_info("3. Navigate to Data > Connections and create new connection")
    print_info("4. powerautomate connection list --table (to get new connection ID)")

    if not yes:
        confirm = typer.confirm("\nAttempt to recreate anyway (will likely fail)?")
        if not confirm:
            print_info("Cancelled")
            raise typer.Exit(0)

    try:
        client = get_client()

        # Get connection details before deleting
        print_info("Getting connection details...")
        old_connection = client.get_connection(connection_id)
        connector_id = old_connection.get("properties", {}).get("apiId", "").split("/")[-1]
        display_name = old_connection.get("properties", {}).get("displayName", "")

        if not connector_id:
            print_error("Could not determine connector ID from connection")
            raise typer.Exit(1)

        # Delete old connection
        print_info(f"Deleting connection {connection_id}...")
        client.delete_connection(connection_id)

        # Attempt to create new connection (will likely fail with 403)
        print_info(f"Attempting to create new connection for connector {connector_id}...")
        new_connection = client.create_connection(connector_id, display_name)

        print_success("Connection recreated successfully!")
        print_info(f"New connection ID: {new_connection.get('name', 'N/A')}")
        print_info("\nYou must now authenticate this connection in the Power Automate portal:")
        print_info("1. Go to https://make.powerautomate.com")
        print_info("2. Navigate to Data > Connections")
        print_info(f"3. Find connection '{display_name}' and click 'Fix connection'")
        print_info("4. Complete the OAuth authentication flow")

        format_response(new_connection, ctx)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)
