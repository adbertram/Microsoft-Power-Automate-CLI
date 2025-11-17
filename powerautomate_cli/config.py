"""Configuration management for Power Automate CLI."""
import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv


class Config:
    """Configuration for Power Automate API client."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load from dataverse-cli .env file (shared config)
        # Try relative path first (sibling directory)
        current_file = Path(__file__).resolve()
        dataverse_cli_path = current_file.parent.parent.parent / "Microsoft-Dataverse-CLI" / ".env"

        if dataverse_cli_path.exists():
            load_dotenv(dataverse_cli_path)
        else:
            # Fallback: try to find in common locations
            possible_paths = [
                Path.home() / "Dropbox" / "GitRepos" / "Microsoft-Dataverse-CLI" / ".env",
                Path.home() / "GitRepos" / "Microsoft-Dataverse-CLI" / ".env",
                Path.home() / "repos" / "Microsoft-Dataverse-CLI" / ".env",
            ]
            for path in possible_paths:
                if path.exists():
                    load_dotenv(path)
                    break

        # Also check local .env
        load_dotenv()

        # Power Automate API (delegated authentication)
        self.client_id = os.getenv("DATAVERSE_CLIENT_ID", "")
        self.tenant_id = os.getenv("DATAVERSE_TENANT_ID", "")
        self.environment_id = os.getenv("DATAVERSE_ENVIRONMENT_ID") or os.getenv("POWERAUTOMATE_ENVIRONMENT_ID", "")
        self.dataverse_url = os.getenv("DATAVERSE_URL", "")

        # Dataverse API (service principal or user authentication)
        self.client_secret = os.getenv("DATAVERSE_CLIENT_SECRET", "")
        self.username = os.getenv("DATAVERSE_USERNAME", "")
        self.password = os.getenv("DATAVERSE_PASSWORD", "")

    def get_missing_credentials(self) -> List[str]:
        """
        Get list of missing required credentials for delegated authentication.

        Returns:
            List of missing credential names
        """
        missing = []

        if not self.client_id:
            missing.append("DATAVERSE_CLIENT_ID")
        if not self.tenant_id:
            missing.append("DATAVERSE_TENANT_ID")
        if not self.environment_id:
            missing.append("DATAVERSE_ENVIRONMENT_ID or POWERAUTOMATE_ENVIRONMENT_ID")

        return missing

    def get_auth_scope(self) -> str:
        """
        Get the OAuth scope for authentication.

        Returns:
            OAuth scope string
        """
        # Use Power Automate Management API scope
        # This is different from Dataverse scope
        return "https://service.flow.microsoft.com/.default"


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get or create the global configuration instance.

    Returns:
        Config: Configuration instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config():
    """Reset the global configuration instance (useful for testing)."""
    global _config
    _config = None
