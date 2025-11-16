"""Power Platform user management commands."""
import typer
from typing import Optional
from ..client import get_client
from ..output import (
    print_json,
    print_table,
    print_success,
    print_error,
    print_info,
    handle_api_error,
)
from ..config import get_config

app = typer.Typer(help="Manage Power Platform users and application users")


@app.command("create-app-user")
def create_app_user(
    app_id: str = typer.Argument(..., help="Azure AD Application ID (Client ID)"),
    roles: Optional[str] = typer.Option(
        "System Administrator",
        "--roles",
        "-r",
        help="Comma-separated list of security role names",
    ),
):
    """
    Create an application user in Dataverse for a service principal.

    Application users allow Azure AD applications (service principals) to
    authenticate to Dataverse and perform operations with assigned security roles.

    Examples:
        powerautomate user create-app-user 4f604d1b-7b0b-4cbf-bee7-c0402bce975d
        powerautomate user create-app-user <app-id> --roles "System Administrator,Environment Maker"
    """
    try:
        config = get_config()
        client = get_client()

        # Get Dataverse URL from config
        dataverse_url = config.dataverse_url
        if not dataverse_url:
            print_error("DATAVERSE_URL not found in configuration")
            raise typer.Exit(1)

        # Get access token for Dataverse
        import requests

        # Build Dataverse API endpoint
        api_url = f"{dataverse_url}/api/data/v9.2"

        # First, check if application user already exists
        print_info(f"Checking for existing application user with app ID: {app_id}")

        check_response = requests.get(
            f"{api_url}/systemusers",
            headers={
                "Authorization": f"Bearer {client.access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            params={
                "$filter": f"azureactivedirectoryobjectid eq {app_id}",
                "$select": "systemuserid,fullname,applicationid,isdisabled"
            }
        )

        if check_response.status_code == 200:
            existing = check_response.json().get("value", [])
            if existing:
                user_id = existing[0].get("systemuserid")
                print_warning(f"Application user already exists with ID: {user_id}")
                print_json(existing[0])

                # Assign roles to existing user
                if roles:
                    print_info(f"Assigning roles to existing user: {roles}")
                    assign_roles_to_user(api_url, client.access_token, user_id, roles)

                return

        # Get Azure AD app details using Microsoft Graph
        print_info(f"Fetching application details from Azure AD...")

        graph_response = requests.get(
            f"https://graph.microsoft.com/v1.0/applications",
            headers={
                "Authorization": f"Bearer {client.access_token}",
                "Accept": "application/json",
            },
            params={
                "$filter": f"appId eq '{app_id}'"
            }
        )

        if graph_response.status_code != 200:
            print_error(f"Failed to fetch app from Azure AD: {graph_response.text}")
            raise typer.Exit(1)

        apps = graph_response.json().get("value", [])
        if not apps:
            print_error(f"Application not found in Azure AD: {app_id}")
            raise typer.Exit(1)

        app_details = apps[0]
        app_name = app_details.get("displayName", "Unknown App")

        print_info(f"Found application: {app_name}")

        # Create application user in Dataverse
        print_info("Creating application user in Dataverse...")

        user_data = {
            "applicationid": app_id,
            "fullname": app_name,
            "azureactivedirectoryobjectid": app_id,
            "isdisabled": False,
        }

        create_response = requests.post(
            f"{api_url}/systemusers",
            headers={
                "Authorization": f"Bearer {client.access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            json=user_data
        )

        if create_response.status_code not in [201, 204]:
            print_error(f"Failed to create application user: {create_response.text}")
            raise typer.Exit(1)

        # Get the created user ID from response header
        user_id = None
        if "OData-EntityId" in create_response.headers:
            entity_id = create_response.headers["OData-EntityId"]
            # Extract GUID from URL
            import re
            match = re.search(r'\(([a-f0-9-]+)\)', entity_id)
            if match:
                user_id = match.group(1)

        if not user_id:
            print_error("Failed to get created user ID")
            raise typer.Exit(1)

        print_success(f"Application user created successfully! User ID: {user_id}")

        # Assign security roles
        if roles:
            print_info(f"Assigning security roles: {roles}")
            assign_roles_to_user(api_url, client.access_token, user_id, roles)

        print_success("Application user setup complete!")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


def assign_roles_to_user(api_url: str, access_token: str, user_id: str, role_names: str):
    """Assign security roles to a user."""
    import requests

    role_list = [r.strip() for r in role_names.split(",")]

    for role_name in role_list:
        # Find role by name
        role_response = requests.get(
            f"{api_url}/roles",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            params={
                "$filter": f"name eq '{role_name}'",
                "$select": "roleid,name"
            }
        )

        if role_response.status_code != 200:
            print_error(f"Failed to find role '{role_name}': {role_response.text}")
            continue

        roles = role_response.json().get("value", [])
        if not roles:
            print_error(f"Role not found: {role_name}")
            continue

        role_id = roles[0].get("roleid")
        print_info(f"Found role '{role_name}' with ID: {role_id}")

        # Assign role to user
        assign_response = requests.post(
            f"{api_url}/systemusers({user_id})/systemuserroles_association/$ref",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            json={
                "@odata.id": f"{api_url}/roles({role_id})"
            }
        )

        if assign_response.status_code in [200, 204]:
            print_success(f"✓ Assigned role: {role_name}")
        elif assign_response.status_code == 400 and "duplicate" in assign_response.text.lower():
            print_info(f"  Role '{role_name}' already assigned")
        else:
            print_error(f"Failed to assign role '{role_name}': {assign_response.text}")


@app.command("list-app-users")
def list_app_users(
    table_format: bool = typer.Option(False, "--table", "-t", help="Display as table"),
):
    """
    List all application users in the environment.

    Application users are service principals that can authenticate
    to Dataverse and perform operations.

    Examples:
        powerautomate user list-app-users
        powerautomate user list-app-users --table
    """
    try:
        config = get_config()
        client = get_client()

        dataverse_url = config.dataverse_url
        if not dataverse_url:
            print_error("DATAVERSE_URL not found in configuration")
            raise typer.Exit(1)

        api_url = f"{dataverse_url}/api/data/v9.2"

        import requests

        response = requests.get(
            f"{api_url}/systemusers",
            headers={
                "Authorization": f"Bearer {client.access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            params={
                "$filter": "applicationid ne null",
                "$select": "systemuserid,fullname,applicationid,isdisabled,azureactivedirectoryobjectid"
            }
        )

        if response.status_code != 200:
            print_error(f"Failed to list application users: {response.text}")
            raise typer.Exit(1)

        users = response.json().get("value", [])

        if not users:
            print_error("No application users found")
            return

        if table_format:
            display_users = []
            for user in users:
                display_users.append({
                    "name": user.get("fullname", ""),
                    "app_id": user.get("applicationid", ""),
                    "user_id": user.get("systemuserid", ""),
                    "disabled": "Yes" if user.get("isdisabled") else "No",
                })
            print_table(display_users, ["name", "app_id", "user_id", "disabled"])
        else:
            print_json(users)

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


@app.command("assign-role")
def assign_role_to_user(
    email: str = typer.Argument(..., help="User email address"),
    role: str = typer.Argument(..., help="Security role name (e.g., 'System Administrator')"),
):
    """
    Assign a security role to a regular user account.

    Examples:
        powerautomate user assign-role adam@example.com "System Administrator"
        powerautomate user assign-role user@domain.com "Environment Maker"
    """
    try:
        config = get_config()
        client = get_client()

        dataverse_url = config.dataverse_url
        if not dataverse_url:
            print_error("DATAVERSE_URL not found in configuration")
            raise typer.Exit(1)

        api_url = f"{dataverse_url}/api/data/v9.2"

        import requests

        # Find user by email
        print_info(f"Looking up user: {email}")

        user_response = requests.get(
            f"{api_url}/systemusers",
            headers={
                "Authorization": f"Bearer {client.access_token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            },
            params={
                "$filter": f"internalemailaddress eq '{email}'",
                "$select": "systemuserid,fullname,internalemailaddress"
            }
        )

        if user_response.status_code != 200:
            print_error(f"Failed to find user: {user_response.text}")
            raise typer.Exit(1)

        users = user_response.json().get("value", [])
        if not users:
            print_error(f"User not found: {email}")
            raise typer.Exit(1)

        user = users[0]
        user_id = user.get("systemuserid")
        user_name = user.get("fullname", email)

        print_success(f"Found user: {user_name} (ID: {user_id})")

        # Assign the role
        print_info(f"Assigning role '{role}' to user...")
        assign_roles_to_user(api_url, client.access_token, user_id, role)

        print_success(f"Successfully assigned '{role}' to {user_name}!")

    except Exception as e:
        exit_code = handle_api_error(e)
        raise typer.Exit(exit_code)


def print_warning(message: str):
    """Print a warning message."""
    typer.echo(typer.style(f"⚠ {message}", fg=typer.colors.YELLOW))
