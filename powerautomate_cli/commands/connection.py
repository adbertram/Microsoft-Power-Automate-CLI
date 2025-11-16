"""Connection management commands for Power Automate CLI."""
import typer
import json
from typing import Optional
from ..client import get_client
from ..output import print_table, print_json, print_success, print_info, print_error, ClientError


app = typer.Typer(help="Manage Power Automate connections")


@app.command("list")
def list_connections(
    connector_id: Optional[str] = typer.Option(None, "--connector", "-c", help="Filter by connector ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    table: bool = typer.Option(False, "--table", help="Output as formatted table"),
):
    """
    List all connections in the environment.

    Connections are authenticated instances of connectors. Each connection
    stores OAuth credentials and refresh tokens for API access.

    Examples:
        powerautomate connection list --table
        powerautomate connection list --connector shared_prg-5fpodio-5fd251d00ef0afcb57
        powerautomate connection list --json
    """
    try:
        client = get_client()
        result = client.list_connections(connector_id=connector_id)

        if json_output:
            print_json(result)
        elif table:
            connections = result.get("value", [])
            if not connections:
                print_info("No connections found")
                return

            # Format for table display
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

            print_table(table_data, ["name", "id", "connector", "status", "created"])
        else:
            print_json(result)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("get")
def get_connection(
    connection_id: str = typer.Argument(..., help="Connection ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """
    Get detailed information about a specific connection.

    Shows OAuth configuration, status, and refresh token settings.

    Examples:
        powerautomate connection get shared_prg-5fpodio-123456789
        powerautomate connection get shared_prg-5fpodio-123456789 --json
    """
    try:
        client = get_client()
        connection = client.get_connection(connection_id)

        if json_output:
            print_json(connection)
        else:
            # Pretty print key information
            props = connection.get("properties", {})
            print_info(f"Connection: {props.get('displayName', 'N/A')}")
            print_info(f"ID: {connection.get('name', 'N/A')}")
            print_info(f"Connector: {props.get('apiId', 'N/A')}")
            print_info(f"Status: {props.get('statuses', [{}])[0].get('status', 'Unknown')}")
            print_info(f"Created: {props.get('createdTime', 'N/A')}")

            # Check for OAuth/token info
            if "parameterValues" in props:
                print_info("\nAuthentication Configuration:")
                print_json({"parameterValues": props["parameterValues"]})

            print_info("\nFull details:")
            print_json(connection)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("refresh")
def refresh_connection(
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
        print_json(result)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("test")
def test_connection(
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

        print_json(result)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("update")
def update_connection(
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
            print_json(result)
        else:
            props = result.get("properties", {})
            print_info(f"Status: {props.get('statuses', [{}])[0].get('status', 'Unknown')}")

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("delete")
def delete_connection(
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

        print_json(new_connection)

    except ClientError as e:
        print_error(str(e))
        raise typer.Exit(1)
