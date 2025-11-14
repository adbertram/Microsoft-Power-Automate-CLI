"""Power Automate Management API client."""
import requests
import os
import atexit
from pathlib import Path
from typing import Optional, Dict, Any
from msal import PublicClientApplication, SerializableTokenCache
from .config import get_config
from .output import ClientError, print_info, print_success


# Global client instance
_client: Optional['PowerAutomateClient'] = None

# Global token cache
_token_cache = SerializableTokenCache()

# Cache file location
_cache_file = Path.home() / ".powerautomate_token_cache.bin"


def _load_cache():
    """Load the token cache from disk."""
    if _cache_file.exists():
        with open(_cache_file, "r") as f:
            _token_cache.deserialize(f.read())


def _save_cache():
    """Save the token cache to disk."""
    if _token_cache.has_state_changed:
        with open(_cache_file, "w") as f:
            f.write(_token_cache.serialize())


# Load cache on module import
_load_cache()

# Save cache on exit
atexit.register(_save_cache)


class PowerAutomateClient:
    """
    Client for interacting with Microsoft Power Automate Management API.

    Handles authentication, API requests, and response handling for the
    Power Automate service (api.flow.microsoft.com), which properly
    registers flows with resource IDs.
    """

    def __init__(self, environment_id: str, access_token: str):
        """
        Initialize Power Automate client.

        Args:
            environment_id: Power Platform environment ID
            access_token: OAuth access token for authentication
        """
        self.environment_id = environment_id
        self.access_token = access_token
        self.api_base = "https://api.flow.microsoft.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-ms-client-scope": "full",
        })

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a GET request to the Power Automate API.

        Args:
            endpoint: API endpoint (e.g., 'flows', 'connections')
            params: Optional query parameters

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails
        """
        # Construct full URL with environment context
        if not endpoint.startswith('http'):
            url = f"{self.api_base}/providers/Microsoft.ProcessSimple/environments/{self.environment_id}/{endpoint}"
        else:
            url = endpoint

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
        Make a POST request to the Power Automate API.

        Args:
            endpoint: API endpoint
            data: JSON data to send

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails
        """
        # Construct full URL with environment context
        if not endpoint.startswith('http'):
            url = f"{self.api_base}/providers/Microsoft.ProcessSimple/environments/{self.environment_id}/{endpoint}"
        else:
            url = endpoint

        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def patch(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a PATCH request to the Power Automate API.

        Args:
            endpoint: API endpoint
            data: JSON data to send

        Returns:
            JSON response as dictionary

        Raises:
            ClientError: If the request fails
        """
        # Construct full URL with environment context
        if not endpoint.startswith('http'):
            url = f"{self.api_base}/providers/Microsoft.ProcessSimple/environments/{self.environment_id}/{endpoint}"
        else:
            url = endpoint

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
        Make a DELETE request to the Power Automate API.

        Args:
            endpoint: API endpoint

        Raises:
            ClientError: If the request fails
        """
        # Construct full URL with environment context
        if not endpoint.startswith('http'):
            url = f"{self.api_base}/providers/Microsoft.ProcessSimple/environments/{self.environment_id}/{endpoint}"
        else:
            url = endpoint

        try:
            response = self.session.delete(url)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")


def _get_delegated_token(config) -> str:
    """
    Get access token using device code flow (delegated authentication).

    Power Automate Management API requires delegated authentication,
    which means the user must interactively authenticate. Device code
    flow is the standard for CLI tools.

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
        token_cache=_token_cache,
    )

    scope = [config.get_auth_scope()]

    # Try silent authentication first (using cached token)
    accounts = app.get_accounts()
    if accounts:
        print_info("Using cached authentication...")
        result = app.acquire_token_silent(scope, account=accounts[0])
        if result and "access_token" in result:
            print_success("Authentication successful (cached)")
            _save_cache()  # Save cache after successful silent auth
            return result["access_token"]

    # Fall back to device code flow (interactive)
    print_info("Starting interactive authentication...")
    print_info("Power Automate API requires user (delegated) authentication")

    flow = app.initiate_device_flow(scopes=scope)

    if "user_code" not in flow:
        error = flow.get("error_description", "Unknown error initiating device flow")
        raise ClientError(f"Failed to initiate device flow: {error}")

    # Display the user code and verification URL
    print("")
    print_info(flow["message"])
    print("")

    # Poll for the user completing the authentication
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise ClientError(f"Failed to acquire token: {error}")

    print_success("Authentication successful!")
    _save_cache()  # Save cache after successful device code auth
    return result["access_token"]


def _extract_environment_id_from_url(config) -> str:
    """
    Extract environment ID from configuration.

    Args:
        config: Configuration object

    Returns:
        Environment ID (GUID)

    Raises:
        ClientError: If environment ID is not configured
    """
    if not config.environment_id:
        raise ClientError(
            "Environment ID not found. Please set DATAVERSE_ENVIRONMENT_ID or "
            "POWERAUTOMATE_ENVIRONMENT_ID in your .env file.\n\n"
            "You can find your environment ID in the Power Platform Admin Center or "
            "by running: dataverse auth whoami"
        )

    return config.environment_id


def get_client() -> PowerAutomateClient:
    """
    Get or create the global Power Automate API client.

    The Power Automate Management API requires delegated (user) authentication.
    This uses device code flow for interactive authentication in a CLI context.

    Returns:
        PowerAutomateClient: Authenticated Power Automate API client

    Raises:
        ClientError: If credentials are missing or authentication fails
    """
    global _client

    if _client is not None:
        return _client

    config = get_config()

    # Check for missing credentials
    missing = config.get_missing_credentials()
    if missing:
        error_msg = (
            "Missing required configuration. Please set the following "
            "environment variables in ../Microsoft-Dataverse-CLI/.env:\n\n"
        )
        for cred in missing:
            error_msg += f"  - {cred}\n"

        error_msg += "\nRequired for Power Automate CLI:\n"
        error_msg += "  - DATAVERSE_CLIENT_ID (Azure AD app registration)\n"
        error_msg += "  - DATAVERSE_TENANT_ID\n"
        error_msg += "  - DATAVERSE_ENVIRONMENT_ID (e.g., Default-<tenant-id>)\n"

        raise ClientError(error_msg)

    # Get environment ID
    try:
        environment_id = _extract_environment_id_from_url(config)
    except Exception as e:
        raise ClientError(f"Failed to determine environment ID: {e}")

    # Use delegated authentication (device code flow)
    try:
        access_token = _get_delegated_token(config)
        _client = PowerAutomateClient(environment_id, access_token)
        return _client
    except Exception as e:
        raise ClientError(f"Failed to authenticate with Power Automate API: {e}")


def reset_client():
    """Reset the global client instance (useful for testing)."""
    global _client
    _client = None
