"""Dataverse Web API client for Power Automate CLI."""
import requests
from typing import Optional, Dict, Any
from msal import ConfidentialClientApplication, PublicClientApplication
from .config import get_config
from .output import ClientError


# Global Dataverse client instance
_dataverse_client: Optional['DataverseClient'] = None


class DataverseClient:
    """
    Client for interacting with Microsoft Dataverse Web API.

    Provides access to Dataverse tables including workflow execution details,
    solution components, and other entities not available via Power Automate
    Management API.

    Key Use Cases:
    - Query workflow run details and action execution logs
    - Access solution component metadata
    - Query custom entities and relationships
    - Retrieve detailed error information from flow runs
    """

    def __init__(self, dataverse_url: str, access_token: str):
        """
        Initialize Dataverse client.

        Args:
            dataverse_url: Base URL for Dataverse environment (e.g., https://org.crm.dynamics.com)
            access_token: OAuth access token for authentication
        """
        self.dataverse_url = dataverse_url.rstrip('/')
        self.access_token = access_token
        self.api_base = f"{self.dataverse_url}/api/data/v9.2"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        })

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the Dataverse API.

        Args:
            endpoint: API endpoint (e.g., 'workflows', 'solutions', 'asyncoperations')
            params: Optional query parameters (OData filters, select, expand, etc.)

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails

        Examples:
            # Get all workflows
            client.get('workflows')

            # Get specific workflow with filter
            client.get('workflows', {'$filter': 'name eq "My Flow"'})

            # Get workflow with expanded properties
            client.get('workflows', {'$select': 'name,statecode', '$expand': 'ownerid'})
        """
        url = f"{self.api_base}/{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a POST request to the Dataverse API.

        Args:
            endpoint: API endpoint
            data: JSON data to send

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails
        """
        url = f"{self.api_base}/{endpoint}"
        self.session.headers["Content-Type"] = "application/json"
        self.session.headers["Prefer"] = "return=representation"

        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()

            # Handle 204 No Content responses
            if response.status_code == 204:
                # Extract entity ID from OData-EntityId header
                entity_id_header = response.headers.get("OData-EntityId", "")
                if entity_id_header and "(" in entity_id_header:
                    entity_id = entity_id_header.split("(")[1].split(")")[0]
                    return {"id": entity_id}
                return {}

            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def patch(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a PATCH request to the Dataverse API.

        Args:
            endpoint: API endpoint
            data: JSON data to send

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails
        """
        url = f"{self.api_base}/{endpoint}"
        self.session.headers["Content-Type"] = "application/json"

        try:
            response = self.session.patch(url, json=data)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def delete(self, endpoint: str) -> None:
        """
        Make a DELETE request to the Dataverse API.

        Args:
            endpoint: API endpoint

        Raises:
            ClientError: If the request fails
        """
        url = f"{self.api_base}/{endpoint}"

        try:
            response = self.session.delete(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")


def _get_service_principal_token(config) -> str:
    """
    Get access token using service principal (client credentials flow).

    This is the recommended authentication method for accessing Dataverse
    in automated scenarios.

    Args:
        config: Configuration object

    Returns:
        Access token string

    Raises:
        ClientError: If authentication fails
    """
    authority = f"https://login.microsoftonline.com/{config.tenant_id}"
    app = ConfidentialClientApplication(
        config.client_id,
        authority=authority,
        client_credential=config.client_secret,
    )

    # Dataverse scope (different from Power Automate Management API)
    scope = [f"{config.dataverse_url}/.default"]
    result = app.acquire_token_for_client(scopes=scope)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise ClientError(f"Failed to acquire token: {error}")

    return result["access_token"]


def _get_user_token(config) -> str:
    """
    Get access token using username/password (resource owner password credentials flow).

    Note: This flow requires the Azure AD app to have "Allow public client flows" enabled.

    Args:
        config: Configuration object

    Returns:
        Access token string

    Raises:
        ClientError: If authentication fails
    """
    authority = f"https://login.microsoftonline.com/{config.tenant_id}"
    app = PublicClientApplication(
        config.client_id,
        authority=authority,
    )

    scope = [f"{config.dataverse_url}/.default"]
    result = app.acquire_token_by_username_password(
        config.username,
        config.password,
        scopes=scope
    )

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise ClientError(f"Failed to acquire token: {error}")

    return result["access_token"]


def get_dataverse_client() -> DataverseClient:
    """
    Get or create the global Dataverse API client.

    Uses service principal authentication (client credentials flow) if available,
    otherwise falls back to username/password authentication.

    Returns:
        DataverseClient: Authenticated Dataverse API client

    Raises:
        ClientError: If credentials are missing or authentication fails

    Environment Variables Required:
        For service principal auth (recommended):
        - DATAVERSE_URL
        - DATAVERSE_CLIENT_ID
        - DATAVERSE_CLIENT_SECRET
        - DATAVERSE_TENANT_ID

        For user auth:
        - DATAVERSE_URL
        - DATAVERSE_CLIENT_ID
        - DATAVERSE_TENANT_ID
        - DATAVERSE_USERNAME
        - DATAVERSE_PASSWORD
    """
    global _dataverse_client

    if _dataverse_client is not None:
        return _dataverse_client

    config = get_config()

    # Check if we have Dataverse URL
    if not config.dataverse_url:
        raise ClientError(
            "Missing DATAVERSE_URL environment variable. "
            "This is required to access Dataverse Web API.\n\n"
            "Set DATAVERSE_URL to your Dataverse environment URL "
            "(e.g., https://org.crm.dynamics.com)"
        )

    # Try service principal authentication first (recommended for CLI)
    if hasattr(config, 'client_secret') and config.client_secret:
        try:
            access_token = _get_service_principal_token(config)
            _dataverse_client = DataverseClient(config.dataverse_url, access_token)
            return _dataverse_client
        except Exception as e:
            raise ClientError(f"Failed to authenticate with service principal: {e}")

    # Try user authentication
    if hasattr(config, 'username') and hasattr(config, 'password') and config.username and config.password:
        try:
            access_token = _get_user_token(config)
            _dataverse_client = DataverseClient(config.dataverse_url, access_token)
            return _dataverse_client
        except Exception as e:
            raise ClientError(f"Failed to authenticate with user credentials: {e}")

    # No valid authentication method
    raise ClientError(
        "No valid Dataverse authentication method available.\n\n"
        "For service principal authentication (recommended):\n"
        "  Set: DATAVERSE_CLIENT_SECRET\n\n"
        "For user authentication:\n"
        "  Set: DATAVERSE_USERNAME, DATAVERSE_PASSWORD"
    )


def reset_dataverse_client():
    """Reset the global Dataverse client instance (useful for testing)."""
    global _dataverse_client
    _dataverse_client = None
