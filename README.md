# Power Automate CLI

[![GitHub](https://img.shields.io/badge/GitHub-Microsoft--Power--Automate--CLI-blue?logo=github)](https://github.com/adbertram/Microsoft-Power-Automate-CLI)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A Python CLI for Microsoft Power Automate Management API. Create and manage Power Automate flows programmatically with proper service registration.

## Why This CLI?

This CLI uses the **Power Automate Management API** (`api.flow.microsoft.com`) rather than directly manipulating Dataverse workflow records. This ensures:

- ✅ **Proper Flow Registration** - Flows get `resourceid` and `resourcecontainer` fields
- ✅ **Portal Visibility** - Flows appear correctly in https://make.powerautomate.com
- ✅ **Full Flow Lifecycle** - Complete support for create, update, start, stop, delete operations
- ✅ **Solution Integration** - Proper association with Power Platform solutions

**Comparison:**
- `dataverse-cli`: Direct Dataverse database operations (low-level, query-focused)
- `powerautomate-cli`: Power Automate service operations (high-level, proper flow management)

## Features

- ✅ **Flow Management** - Create, list, update, start, stop, and delete flows
- ✅ **Run History** - View flow execution history with status filtering (last 28 days)
- ✅ **Proper API Integration** - Uses Power Automate Management API for full service registration
- ✅ **Delegated Authentication** - Secure device code flow with token caching
- ✅ **Rich CLI Output** - JSON and table formats with syntax highlighting
- ✅ **Shared Configuration** - Uses dataverse-cli for centralized config management
- ✅ **Type Hints** - Full type hints for better IDE support

## Quick Start

Get up and running in 3 steps:

```bash
# 1. Clone and install
git clone https://github.com/adbertram/Microsoft-Power-Automate-CLI.git
cd Microsoft-Power-Automate-CLI
./install.sh

# 2. Configure credentials (edit the file created by installer)
# Location: ../Microsoft-Dataverse-CLI/.env
# Required: CLIENT_ID, TENANT_ID, ENVIRONMENT_ID
# No username/password needed - you'll authenticate interactively!

# 3. Use the CLI
powerautomate flow list --table
powerautomate flow create --name "My Flow" --trigger http
```

**Common Commands:**
```bash
powerautomate flow list --table           # List all flows
powerautomate flow get <flow-id>          # Get flow details
powerautomate flow start <flow-id>        # Turn on a flow
powerautomate flow stop <flow-id>         # Turn off a flow
powerautomate flow runs <flow-id> --table # View flow run history
```

**Troubleshooting:**
- Commands not found? Add `~/.local/bin` to your PATH: `export PATH="$HOME/.local/bin:$PATH"`
- Authentication errors? Verify CLIENT_ID, TENANT_ID, ENVIRONMENT_ID in `../Microsoft-Dataverse-CLI/.env`
- Device code not working? Check that your Azure AD app allows public client flows
- Permission errors? Ensure your user account has Environment Maker role in Power Platform

## Installation

### Automated Installation (Recommended)

The easiest way to install is using the provided installation script, which handles everything automatically:

```bash
# Clone the repository
git clone https://github.com/adbertram/Microsoft-Power-Automate-CLI.git
cd Microsoft-Power-Automate-CLI

# Run the installation script
./install.sh
```

The script will:
- ✅ Check for prerequisites (pipx)
- ✅ Clone the dataverse-cli dependency automatically
- ✅ Install both CLIs globally
- ✅ Set up configuration files
- ✅ Verify the installation
- ✅ Provide clear next steps

### Manual Installation

If you prefer to install manually:

1. **Install pipx** (if not already installed):
```bash
brew install pipx  # macOS
# or
python3 -m pip install --user pipx  # Linux

pipx ensurepath
```

2. **Clone and install dataverse-cli**:
```bash
git clone https://github.com/adbertram/Microsoft-Dataverse-CLI.git
cd Microsoft-Dataverse-CLI
pipx install -e .
```

3. **Clone and install powerautomate-cli**:
```bash
git clone https://github.com/adbertram/Microsoft-Power-Automate-CLI.git
cd Microsoft-Power-Automate-CLI
pipx install -e .
```

## Configuration

**Important:** This CLI uses shared configuration from the dataverse-cli project. All configuration is managed in a single location.

**Prerequisites:**
1. Clone and configure [Microsoft-Dataverse-CLI](https://github.com/adbertram/Microsoft-Dataverse-CLI)
2. Install it as a sibling directory (recommended) or the CLI will search common locations
3. **Azure AD App Registration** - Must allow public client flows (see below)

**Configuration Location:** `../Microsoft-Dataverse-CLI/.env` (relative to this project)

### Azure AD App Registration Setup

The Power Automate CLI requires an Azure AD app registration configured for public client authentication:

1. **Create App Registration** (if not exists):
   - Go to Azure Portal → Azure Active Directory → App Registrations
   - Click "New registration"
   - Name: "PowerAutomate-CLI" (or your preferred name)
   - Supported account types: Choose based on your org needs
   - Click "Register"

2. **Enable Public Client Flows** (Required):
   - Go to: Authentication → Advanced settings
   - **Set "Allow public client flows" to "Yes"**
   - Click "Save"

3. **Add API Permissions** (if not already added):
   - Go to: API permissions → Add a permission
   - Select "APIs my organization uses"
   - Search for "Power Automate" or "Flow Management"
   - Add: `Flows.Manage.All` or `Flows.Read.All`
   - Click "Grant admin consent"

4. **Copy Configuration**:
   - Client ID: Copy from the app overview page
   - Tenant ID: Copy from the app overview page
   - Add these to `../Microsoft-Dataverse-CLI/.env`

### Delegated Authentication (Required for Power Automate API)

The Power Automate Management API requires **delegated (user) authentication**. This CLI uses **device code flow** for interactive authentication.

Add these variables to the dataverse-cli `.env` file:

```bash
# Required for Power Automate CLI
DATAVERSE_CLIENT_ID=your-client-id
DATAVERSE_TENANT_ID=your-tenant-id
DATAVERSE_ENVIRONMENT_ID=Default-your-tenant-id
```

**Authentication Flow:**
When you run a command, the CLI will:
1. Check for a cached token (if you've authenticated before)
2. If no cached token, prompt you to authenticate interactively
3. Display a URL (like https://microsoft.com/devicelogin) and a code
4. You open the URL in your browser and enter the code
5. Complete authentication in the browser
6. The CLI receives your token and caches it for future use

**No username/password in config!** Interactive authentication is more secure and supports MFA.

## Quick Start

### List Flows

```bash
# List all flows (JSON)
powerautomate flow list

# List flows in table format
powerautomate flow list --table

# List top 10 flows
powerautomate flow list --top 10
```

### Create a New Flow

```bash
# Create flow with HTTP trigger
powerautomate flow create --name "My Flow" --trigger http

# Create flow in specific solution
powerautomate flow create --name "My Flow" --trigger http --solution ProgressContentAutomation

# Create with description
powerautomate flow create --name "My Flow" --trigger http --description "Handles incoming webhooks"
```

### Get Flow Details

```bash
powerautomate flow get <flow-id>
```

**Note:** Flow IDs in the Management API are different from Dataverse workflow GUIDs. Use the ID from `flow list`.

### Start/Stop Flows

```bash
# Turn on a flow
powerautomate flow start <flow-id>

# Turn off a flow
powerautomate flow stop <flow-id>
```

### Update Flow

```bash
# Update name
powerautomate flow update <flow-id> --name "New Name"

# Update description
powerautomate flow update <flow-id> --description "Updated description"

# Change state
powerautomate flow update <flow-id> --state started
```

### Delete Flow

```bash
# Delete with confirmation prompt
powerautomate flow delete <flow-id>

# Delete without confirmation
powerautomate flow delete <flow-id> --yes
```

### View Flow Run History

```bash
# List all runs for a flow (last 28 days)
powerautomate flow runs <flow-id>

# List runs in table format
powerautomate flow runs <flow-id> --table

# List only failed runs
powerautomate flow runs <flow-id> --failed --table

# List only successful runs
powerautomate flow runs <flow-id> --succeeded --table

# List only running flows
powerautomate flow runs <flow-id> --running --table

# Limit number of results (max 100)
powerautomate flow runs <flow-id> --top 10 --table

# Custom filter using OData syntax
powerautomate flow runs <flow-id> --filter "status eq 'Failed'"
```

### Get Specific Run Details

```bash
# Get detailed information about a specific run
powerautomate flow run <flow-id> <run-id>
```

**Note:** Power Automate retains the last 28 days of run history. The API returns a maximum of 100 runs per request. Use `--top` to control pagination.

## Command Reference

### Flow Commands

| Command | Description |
|---------|-------------|
| `flow list` | List all Power Automate flows |
| `flow get <id>` | Get flow details |
| `flow create` | Create a new flow with proper registration |
| `flow update <id>` | Update flow properties |
| `flow delete <id>` | Delete a flow |
| `flow start <id>` | Turn on a flow |
| `flow stop <id>` | Turn off a flow |
| `flow runs <id>` | List run history for a flow (last 28 days) |
| `flow run <id> <run-id>` | Get detailed information about a specific run |

### Common Options

- `--table, -t` - Display output as a formatted table
- `--yes, -y` - Skip confirmation prompts
- `--help` - Show command help

## Architecture

### Project Structure

```
Microsoft-Power-Automate-CLI/
├── powerautomate_cli/
│   ├── __init__.py          # Package initialization
│   ├── client.py            # Power Automate API client
│   ├── main.py              # CLI entry point
│   └── commands/
│       ├── __init__.py
│       └── flow.py          # Flow management commands
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

### Dependencies

- **dataverse-cli** - Provides shared authentication and output utilities
- **typer** - CLI framework
- **requests** - HTTP client
- **msal** - Microsoft Authentication Library
- **rich** - Terminal output formatting

## Troubleshooting

### "client_assertion or client_secret required" Error

This error means your Azure AD app is not configured to allow public client flows (delegated authentication).

**Solution:**
1. Go to Azure Portal → App Registrations → Your App
2. Navigate to Authentication → Advanced settings
3. Set "Allow public client flows" to **Yes**
4. Save and try again

### "Environment ID not found" Error

Ensure `DATAVERSE_ENVIRONMENT_ID` is set in your `.env` file:

```bash
# Use the Default-<tenant-id> format for user authentication
DATAVERSE_ENVIRONMENT_ID=Default-11376bd0-c80f-4e99-b86f-05d17b73518d
```

### Device Code Authentication Not Working

If the device code flow fails:
1. Verify your Azure AD app has "Allow public client flows" enabled
2. Check that you have the correct Client ID and Tenant ID
3. Ensure you're opening the device login URL in a browser where you can authenticate
4. Try clearing cached tokens: The CLI uses MSAL cache in `~/.msal_token_cache`

### Flow IDs vs Workflow IDs

- **Power Automate API** uses flow names as IDs (e.g., `a1b2c3d4-...`)
- **Dataverse API** uses workflow GUIDs
- These are different! Use the ID from `powerautomate flow list`, not from Dataverse queries

### Flows Not Appearing in Portal

If flows created with `dataverse flow create` don't appear in the portal, they're missing proper registration. Use `powerautomate flow create` instead, which properly registers flows with the Power Automate service.

## Development

### Setup Development Environment

```bash
# Navigate to repository
cd ~/Dropbox/GitRepos/Microsoft-Power-Automate-CLI

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
pytest --cov=powerautomate_cli --cov-report=html
```

## Related Projects

- **[Microsoft-Dataverse-CLI](https://github.com/adbertram/Microsoft-Dataverse-CLI)** - Low-level Dataverse operations
- Complementary tools for different use cases:
  - Use `dataverse` for: Database queries, workflow record inspection, solution components
  - Use `powerautomate` for: Creating flows, managing flow lifecycle, proper portal integration

## Resources

- [Power Automate Management API Documentation](https://learn.microsoft.com/en-us/rest/api/power-automate/)
- [Power Automate Web API Reference](https://learn.microsoft.com/en-us/power-automate/web-api)
- [Dataverse Web API Documentation](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)
- [Device Code Flow Authentication](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/adbertram/powerautomate-cli).
