"""Main entry point for Power Automate CLI."""
import sys
import typer
from typing import Optional

from .output import ClientError

# Create main Typer app
app = typer.Typer(
    name="powerautomate",
    help="CLI interface for Microsoft Power Automate Management API - Properly create and manage flows",
    no_args_is_help=True,
    add_completion=True,
)


# Import and register command modules
try:
    from .commands import flow, connector, solution, connection, user
    app.add_typer(flow.app, name="flow", help="Manage Power Automate flows via Management API")
    app.add_typer(connector.app, name="connector", help="Manage Power Automate connectors (custom and managed)")
    app.add_typer(solution.app, name="solution", help="Manage Power Platform solutions")
    app.add_typer(connection.app, name="connection", help="Manage Power Automate connections")
    app.add_typer(user.app, name="user", help="Manage Power Platform users and application users")
except ImportError:
    # Commands not yet implemented - will add as we build them
    pass


@app.callback()
def callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        is_eager=True,
    ),
):
    """
    Power Automate CLI - Create and manage Power Automate flows using the Management API.

    This CLI uses the Power Automate Management API (api.flow.microsoft.com) to properly
    register flows with resourceid and resourcecontainer, ensuring they appear in the
    Power Automate portal.

    Authentication uses delegated (user) authentication via device code flow.
    Required environment variables (configured in dataverse-cli .env):

      - DATAVERSE_CLIENT_ID (Azure AD app registration)
      - DATAVERSE_TENANT_ID (Azure AD tenant)
      - DATAVERSE_ENVIRONMENT_ID (Power Platform environment)

    On first use, you'll authenticate interactively via device code flow.
    Subsequent commands use cached tokens automatically.

    Examples:
        powerautomate flow list
        powerautomate flow create --name "My Flow" --trigger http
        powerautomate flow start <flow-id>
        powerautomate flow get <flow-id>
    """
    if version:
        from . import __version__
        typer.echo(f"powerautomate-cli version {__version__}")
        raise typer.Exit()


def main():
    """Main entry point for the CLI application."""
    try:
        app()
    except ClientError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2)
    except KeyboardInterrupt:
        typer.echo("\nAborted!", err=True)
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}", err=True)
        if "--debug" in sys.argv:
            raise
        raise typer.Exit(1)


if __name__ == "__main__":
    main()
