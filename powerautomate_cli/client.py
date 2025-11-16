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

    def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a PUT request to the Power Automate API.

        Used for full resource updates (e.g., updating complete flow definitions).

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

        # Add API version to URL for PUT requests
        url_separator = '&' if '?' in url else '?'
        url = f"{url}{url_separator}api-version=2016-11-01"

        try:
            response = self.session.put(url, json=data)
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

    def list_connectors(self, filter_text: Optional[str] = None, custom_only: bool = False, managed_only: bool = False) -> Dict[str, Any]:
        """
        List all connectors (custom and managed) in the environment.

        Uses Power Apps API which manages connectors.

        Args:
            filter_text: Optional text to filter connectors by name or publisher
            custom_only: Only return custom connectors
            managed_only: Only return managed connectors

        Returns:
            Dictionary containing connector list

        Raises:
            ClientError: If the request fails
        """
        # Use Power Apps API for connectors (non-admin path)
        url = "https://api.powerapps.com/providers/Microsoft.PowerApps/apis"
        params = {"api-version": "2016-11-01", "$filter": f"environment eq '{self.environment_id}'"}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            result = response.json() if response.text else {}

            # Apply filters if specified
            connectors = result.get("value", [])

            # Filter by custom/managed
            if custom_only:
                connectors = [c for c in connectors if self._is_custom_connector(c)]
            elif managed_only:
                connectors = [c for c in connectors if not self._is_custom_connector(c)]

            # Filter by text
            if filter_text:
                filter_lower = filter_text.lower()
                connectors = [
                    c for c in connectors
                    if filter_lower in c.get("properties", {}).get("displayName", "").lower()
                    or filter_lower in c.get("properties", {}).get("publisher", "").lower()
                    or filter_lower in c.get("name", "").lower()
                ]

            return {"value": connectors}

        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def get_connector(self, connector_id: str, include_operations: bool = False) -> Dict[str, Any]:
        """
        Get details about a specific connector.

        Args:
            connector_id: Connector ID (name)
            include_operations: Include operations/actions in response

        Returns:
            Connector details

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/apis/{connector_id}"
        params = {"api-version": "2016-11-01", "$filter": f"environment eq '{self.environment_id}'"}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def get_connector_permissions(self, connector_id: str) -> Dict[str, Any]:
        """
        Get permissions for a specific connector.

        Args:
            connector_id: Connector ID (name)

        Returns:
            Connector permissions

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/apis/{connector_id}/permissions"
        params = {"api-version": "2016-11-01"}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def create_connector(self, definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom connector.

        Args:
            definition: Connector definition

        Returns:
            Created connector details

        Raises:
            ClientError: If the request fails
        """
        connector_name = definition.get("name")
        if not connector_name:
            raise ClientError("Connector definition must include 'name' field")

        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/apis/{connector_name}"
        params = {"api-version": "2016-11-01"}

        try:
            response = self.session.put(url, json=definition, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def update_connector(self, connector_id: str, definition: Dict[str, Any], client_secret: Optional[str] = None) -> Dict[str, Any]:
        """
        Update a custom connector using the PowerApps API.

        This method uses PATCH (not PUT) and includes the environment filter,
        matching paconn's approach. This allows updating OAuth configuration
        which is blocked when using the Power Automate Management API.

        Args:
            connector_id: Connector ID (name)
            definition: Updated connector definition
            client_secret: Optional OAuth client secret for OAuth connectors

        Returns:
            Updated connector details

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/apis/{connector_id}"
        params = {
            "api-version": "2016-11-01",
            "$filter": f"environment eq '{self.environment_id}'"
        }

        # Inject OAuth client secret if provided (required for OAuth connector updates)
        if client_secret:
            self._inject_oauth_secret(definition, client_secret)

        # Add custom header to identify the tool
        headers = {"x-ms-origin": "powerautomate-cli"}

        try:
            # Use PATCH instead of PUT (this is critical for OAuth updates)
            response = self.session.patch(url, json=definition, params=params, headers=headers)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def delete_connector(self, connector_id: str) -> None:
        """
        Delete a custom connector.

        Args:
            connector_id: Connector ID (name)

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/apis/{connector_id}"
        params = {"api-version": "2016-11-01"}

        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def _is_custom_connector(self, connector: Dict[str, Any]) -> bool:
        """
        Determine if a connector is custom or managed.

        Custom connectors have different properties structure.

        Args:
            connector: Connector object

        Returns:
            True if custom, False if managed
        """
        # Custom connectors typically have properties.environment or are in environment scope
        # Managed connectors have properties.tier and known publishers
        props = connector.get("properties", {})

        # Check for custom connector indicators
        if "environment" in props:
            return True

        # Check publisher - custom connectors often have user/org as publisher
        publisher = props.get("publisher", "").lower()
        if publisher and publisher not in ["microsoft", "microsoft corporation", "azure"]:
            # Could be custom, but also third-party managed
            # Check tier - custom connectors typically don't have tier or have "NotSpecified"
            tier = props.get("tier", "")
            if not tier or tier == "NotSpecified":
                return True

        return False

    def _inject_oauth_secret(self, definition: Dict[str, Any], client_secret: str) -> None:
        """
        Inject OAuth client secret into connector definition.

        This replicates paconn's approach of embedding the client secret
        in the connector payload for OAuth connectors.

        Modifies the definition in-place.

        Args:
            definition: Connector definition to modify
            client_secret: OAuth client secret to inject
        """
        props = definition.get("properties", {})

        # Handle single auth configuration (standard OAuth)
        connection_params = props.get("connectionParameters", {})
        token_property = connection_params.get("token")
        if token_property:
            oauth_settings = token_property.get("oauthSettings")
            if oauth_settings:
                oauth_settings["clientSecret"] = client_secret

        # Handle multi-auth configuration (multiple authentication options)
        connection_param_set = props.get("connectionParameterSet", {})
        auth_values = connection_param_set.get("values", [])
        for auth in auth_values:
            params = auth.get("parameters", {})
            token_property = params.get("token")
            if token_property:
                oauth_settings = token_property.get("oauthSettings")
                if oauth_settings:
                    oauth_settings["clientSecret"] = client_secret

    def list_solutions(self, filter_text: Optional[str] = None) -> Dict[str, Any]:
        """
        List all solutions in the environment.

        Uses Dataverse Web API to query solution table directly.
        Requires Dataverse URL configured and appropriate authentication.

        NOTE: For full solution management, use dataverse-cli which has
        comprehensive Dataverse API support.

        Args:
            filter_text: Optional text to filter solutions by name

        Returns:
            Dictionary containing solution list

        Raises:
            ClientError: If the request fails or auth is insufficient
        """
        # Get environment URL from config
        from .config import get_config
        config = get_config()

        if not config.dataverse_url:
            raise ClientError(
                "Dataverse URL not configured. Please set DATAVERSE_URL in your .env file.\n\n"
                "For solution operations, use the dataverse-cli tool instead:\n"
                "  dataverse solution list --table\n"
                "  dataverse solution get --name ProgressContentAutomation\n"
            )

        # Use Dataverse Web API to query solutions table
        url = f"{config.dataverse_url}/api/data/v9.2/solutions"
        params = {"$select": "solutionid,friendlyname,uniquename,version,publisherid,ismanaged"}

        # Add filter if specified
        if filter_text:
            filter_lower = filter_text.lower()
            params["$filter"] = (
                f"contains(tolower(friendlyname), '{filter_lower}') or "
                f"contains(tolower(uniquename), '{filter_lower}')"
            )

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            result = response.json() if response.text else {}

            # Transform Dataverse response to match Power Apps format
            solutions = []
            for sol in result.get("value", []):
                solutions.append({
                    "name": sol.get("solutionid"),
                    "properties": {
                        "displayName": sol.get("friendlyname", ""),
                        "uniqueName": sol.get("uniquename", ""),
                        "version": sol.get("version", ""),
                        "publisherId": sol.get("publisherid", ""),
                        "isManaged": sol.get("ismanaged", False),
                    }
                })

            return {"value": solutions}

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}\n\n"
            if e.response.status_code == 401:
                error_msg += (
                    "Authentication failed for Dataverse API.\n"
                    "Power Automate delegated tokens don't work with Dataverse API.\n\n"
                    "For solution operations, use dataverse-cli instead:\n"
                    "  dataverse solution list --table\n"
                )
            raise ClientError(error_msg)
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def get_solution(self, solution_id: str) -> Dict[str, Any]:
        """
        Get details about a specific solution.

        Args:
            solution_id: Solution ID (GUID)

        Returns:
            Solution details

        Raises:
            ClientError: If the request fails
        """
        from .config import get_config
        config = get_config()

        if not config.dataverse_url:
            raise ClientError(
                "Dataverse URL not configured. Please set DATAVERSE_URL in your .env file."
            )

        url = f"{config.dataverse_url}/api/data/v9.2/solutions({solution_id})"
        params = {"$select": "solutionid,friendlyname,uniquename,version,publisherid,ismanaged,description"}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            result = response.json() if response.text else {}

            # Transform to Power Apps format
            return {
                "name": result.get("solutionid"),
                "properties": {
                    "displayName": result.get("friendlyname", ""),
                    "uniqueName": result.get("uniquename", ""),
                    "version": result.get("version", ""),
                    "publisherId": result.get("publisherid", ""),
                    "isManaged": result.get("ismanaged", False),
                    "description": result.get("description", ""),
                }
            }
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def get_solution_by_name(self, solution_name: str) -> Dict[str, Any]:
        """
        Get solution by its unique name.

        Args:
            solution_name: Solution unique name

        Returns:
            Solution details

        Raises:
            ClientError: If solution not found or request fails
        """
        # List all solutions and find by name
        result = self.list_solutions(filter_text=solution_name)
        solutions = result.get("value", [])

        # Find exact match by uniqueName
        for solution in solutions:
            if solution.get("properties", {}).get("uniqueName", "") == solution_name:
                # Return full solution details
                solution_id = solution.get("name")
                return self.get_solution(solution_id)

        raise ClientError(f"Solution not found: {solution_name}")

    def resolve_solution_id(self, solution_name_or_id: str) -> str:
        """
        Resolve solution name or ID to solution ID.

        Accepts either a solution unique name or a solution ID (GUID).
        Returns the solution ID.

        NOTE: Solution name resolution requires Dataverse API access.
        For simplicity, use solution ID (GUID) directly, which can be
        obtained from: dataverse solution list --table

        Args:
            solution_name_or_id: Solution unique name or ID

        Returns:
            Solution ID (GUID)

        Raises:
            ClientError: If solution not found or auth insufficient
        """
        # Check if it looks like a GUID (contains hyphens and correct length)
        if "-" in solution_name_or_id and len(solution_name_or_id) == 36:
            # Assume it's a valid GUID and return it
            # Flow creation will fail if the solution ID is invalid
            return solution_name_or_id

        # Try to find by name (requires Dataverse API access)
        print_info = __import__('powerautomate_cli.output', fromlist=['print_info']).print_info
        print_info("Attempting to resolve solution name (requires Dataverse API access)...")

        try:
            solution = self.get_solution_by_name(solution_name_or_id)
            return solution.get("name")
        except ClientError as e:
            if "401" in str(e):
                raise ClientError(
                    f"Cannot resolve solution name '{solution_name_or_id}' - Dataverse API access denied.\n\n"
                    f"To create flows in solutions, use the solution ID (GUID) instead:\n"
                    f"  1. Get solution ID: dataverse solution list --table\n"
                    f"  2. Create flow: powerautomate flow create --name 'My Flow' --solution-id <guid>\n"
                )
            raise

    def get_solution_components(self, solution_id: str, component_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all components in a solution.

        For flows specifically, queries the workflows table directly filtered by solution.
        Component type 29 = Modern Cloud Flow (workflow)

        Args:
            solution_id: Solution ID (GUID)
            component_type: Optional component type filter (e.g., "Workflow" for flows)

        Returns:
            Dictionary containing component list

        Raises:
            ClientError: If the request fails
        """
        from .config import get_config
        config = get_config()

        if not config.dataverse_url:
            raise ClientError(
                "Dataverse URL not configured. Please set DATAVERSE_URL in your .env file."
            )

        # For workflows (flows), query the workflows table directly
        if component_type and component_type.lower() == "workflow":
            url = f"{config.dataverse_url}/api/data/v9.2/workflows"
            params = {
                "$select": "workflowid,name,statecode,createdon,modifiedon",
                "$filter": f"category eq 5 and _solutionid_value eq {solution_id}"
            }
        else:
            # Query solutioncomponents table for other component types
            url = f"{config.dataverse_url}/api/data/v9.2/solutioncomponents"
            params = {
                "$select": "solutioncomponentid,componenttype,objectid,createdon",
                "$filter": f"_solutionid_value eq {solution_id}"
            }

            # Component type mapping: 29 = Workflow (modern cloud flow)
            if component_type and component_type.lower() == "workflow":
                params["$filter"] += " and componenttype eq 29"

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            result = response.json() if response.text else {}

            # Transform to Power Apps format
            components = []
            for comp in result.get("value", []):
                if "workflowid" in comp:
                    # This is a workflow
                    components.append({
                        "name": comp.get("workflowid"),
                        "type": "Workflow",
                        "properties": {
                            "displayName": comp.get("name", ""),
                            "state": "On" if comp.get("statecode") == 1 else "Off",
                            "createdTime": comp.get("createdon", ""),
                        }
                    })
                else:
                    # This is from solutioncomponents table
                    comp_type_map = {
                        29: "Workflow",
                        1: "Entity",
                        2: "Attribute",
                        60: "Canvas App",
                    }
                    components.append({
                        "name": comp.get("objectid"),
                        "type": comp_type_map.get(comp.get("componenttype"), f"Type{comp.get('componenttype')}"),
                        "properties": {
                            "createdTime": comp.get("createdon", ""),
                        }
                    })

            return {"value": components}

        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def list_connections(self, connector_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all connections in the environment.

        Connections are authenticated instances of connectors that store OAuth
        credentials and refresh tokens.

        Args:
            connector_id: Optional connector ID to filter connections

        Returns:
            Dictionary containing connection list

        Raises:
            ClientError: If the request fails
        """
        url = "https://api.powerapps.com/providers/Microsoft.PowerApps/connections"
        params = {"api-version": "2016-11-01", "$filter": f"environment eq '{self.environment_id}'"}

        if connector_id:
            params["$filter"] += f" and apiId eq '/providers/Microsoft.PowerApps/apis/{connector_id}'"

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def get_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific connection.

        Args:
            connection_id: Connection ID

        Returns:
            Connection details including OAuth configuration

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/connections/{connection_id}"
        params = {"api-version": "2016-11-01", "$filter": f"environment eq '{self.environment_id}'"}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def refresh_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Refresh a connection's OAuth token.

        Forces the connection to request a new access token using its refresh token.

        Args:
            connection_id: Connection ID

        Returns:
            Updated connection details

        Raises:
            ClientError: If the request fails
        """
        # First get the current connection to preserve its configuration
        connection = self.get_connection(connection_id)

        # Use PATCH to update connection and trigger token refresh
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/connections/{connection_id}"
        params = {"api-version": "2016-11-01"}

        # Trigger refresh by updating with current configuration
        update_data = {
            "properties": {
                "displayName": connection.get("properties", {}).get("displayName", ""),
            }
        }

        try:
            response = self.session.patch(url, json=update_data, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def test_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Test a connection to verify it's working.

        Args:
            connection_id: Connection ID

        Returns:
            Connection status

        Raises:
            ClientError: If the request fails
        """
        # Get connection and check its status
        connection = self.get_connection(connection_id)

        # Check if there's a test endpoint available
        statuses = connection.get("properties", {}).get("statuses", [])
        if statuses and statuses[0].get("status") == "Error":
            raise ClientError(f"Connection test failed: {statuses[0].get('error', 'Unknown error')}")

        return connection

    def update_connection(self, connection_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update connection configuration.

        Args:
            connection_id: Connection ID
            updates: Dictionary of properties to update

        Returns:
            Updated connection details

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/connections/{connection_id}"
        params = {"api-version": "2016-11-01"}

        update_data = {"properties": updates}

        try:
            response = self.session.patch(url, json=update_data, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def delete_connection(self, connection_id: str) -> None:
        """
        Delete a connection.

        WARNING: This will break any flows using this connection!

        Args:
            connection_id: Connection ID

        Raises:
            ClientError: If the request fails
        """
        url = f"https://api.powerapps.com/providers/Microsoft.PowerApps/connections/{connection_id}"
        params = {"api-version": "2016-11-01"}

        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ClientError(f"HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise ClientError(f"Request failed: {e}")

    def create_connection(self, connector_id: str, display_name: str) -> Dict[str, Any]:
        """
        Create a new connection for a connector.

        Note: Connection creation is not supported with delegated authentication.
        The Power Apps API requires admin-level permissions that are not available
        with user (delegated) authentication tokens.

        Even with admin permissions, OAuth connections require interactive
        authentication in the Power Automate portal.

        Recommended workflow:
        1. Create connections manually at https://make.powerautomate.com
        2. Navigate to Data > Connections
        3. Add new connection and complete OAuth flow
        4. Use 'powerautomate connection list' to get connection IDs
        5. Reference connection IDs in flow definitions

        Args:
            connector_id: Connector ID
            display_name: Display name for the connection

        Returns:
            Created connection details

        Raises:
            ClientError: If the request fails (will fail with 403 for delegated auth)
        """
        url = "https://api.powerapps.com/providers/Microsoft.PowerApps/connections"
        params = {"api-version": "2016-11-01"}

        connection_data = {
            "properties": {
                "displayName": display_name,
                "apiId": f"/providers/Microsoft.PowerApps/apis/{connector_id}",
                "environment": {
                    "name": self.environment_id,
                }
            }
        }

        try:
            response = self.session.post(url, json=connection_data, params=params)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.HTTPError as e:
            # Provide helpful error message for permission issues
            if e.response.status_code == 403 and "does not have permission" in e.response.text:
                raise ClientError(
                    "Connection creation requires admin API permissions not available with delegated authentication.\n\n"
                    "Workaround:\n"
                    "1. Create connections manually at https://make.powerautomate.com\n"
                    "2. Go to Data > Connections\n"
                    "3. Add new connection and authenticate\n"
                    "4. Use 'powerautomate connection list --table' to get connection IDs\n"
                    "5. Reference connection IDs in your flows\n\n"
                    f"Original error: {e.response.text}"
                )
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
        result = app.acquire_token_silent(scope, account=accounts[0])
        if result and "access_token" in result:
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
