#!/bin/bash

# Power Automate CLI Installation Script
# This script installs both powerautomate-cli and its dependency dataverse-cli

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if pipx is installed
check_pipx() {
    if ! command -v pipx &> /dev/null; then
        print_error "pipx is not installed"
        echo ""
        echo "Please install pipx first:"
        echo "  macOS:   brew install pipx"
        echo "  Linux:   python3 -m pip install --user pipx"
        echo ""
        echo "After installation, run: pipx ensurepath"
        exit 1
    fi
    print_success "pipx is installed"
}

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
DATAVERSE_CLI_DIR="$PARENT_DIR/Microsoft-Dataverse-CLI"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Power Automate CLI Installation                        ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check prerequisites
print_step "Checking prerequisites..."
check_pipx

# Step 2: Clone/Update dataverse-cli
print_step "Setting up dataverse-cli dependency..."

if [ -d "$DATAVERSE_CLI_DIR" ]; then
    print_warning "dataverse-cli already exists at: $DATAVERSE_CLI_DIR"
    read -p "Do you want to update it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Updating dataverse-cli..."
        cd "$DATAVERSE_CLI_DIR"
        git pull origin main || git pull origin master
        print_success "dataverse-cli updated"
    else
        print_success "Using existing dataverse-cli"
    fi
else
    print_step "Cloning dataverse-cli..."
    cd "$PARENT_DIR"
    git clone https://github.com/adbertram/Microsoft-Dataverse-CLI.git
    print_success "dataverse-cli cloned to: $DATAVERSE_CLI_DIR"
fi

# Step 3: Install dataverse-cli
print_step "Installing dataverse-cli..."
cd "$DATAVERSE_CLI_DIR"
pipx install -e . --force 2>&1 | grep -v "⚠️" || true
print_success "dataverse-cli installed"

# Step 4: Install powerautomate-cli
print_step "Installing powerautomate-cli..."
cd "$SCRIPT_DIR"
pipx install -e . --force 2>&1 | grep -v "⚠️" || true
print_success "powerautomate-cli installed"

# Step 5: Check PATH
print_step "Checking PATH configuration..."
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    print_warning "$HOME/.local/bin is not in your PATH"
    echo ""
    echo "Add this to your shell configuration file (~/.bashrc, ~/.zshrc, etc.):"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run: source ~/.bashrc (or ~/.zshrc)"
else
    print_success "PATH is configured correctly"
fi

# Step 6: Configuration setup
print_step "Setting up configuration..."

if [ -f "$DATAVERSE_CLI_DIR/.env" ]; then
    print_success "Configuration file already exists: $DATAVERSE_CLI_DIR/.env"
else
    print_warning "Configuration file not found"
    echo ""
    read -p "Do you want to create a configuration file now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "$DATAVERSE_CLI_DIR/.env.example" ]; then
            cp "$DATAVERSE_CLI_DIR/.env.example" "$DATAVERSE_CLI_DIR/.env"
            print_success "Created configuration file: $DATAVERSE_CLI_DIR/.env"
            echo ""
            echo "Please edit this file and add your credentials:"
            echo "  $DATAVERSE_CLI_DIR/.env"
            echo ""
            echo "Required variables for Power Automate CLI:"
            echo "  - DATAVERSE_URL"
            echo "  - DATAVERSE_CLIENT_ID"
            echo "  - DATAVERSE_TENANT_ID"
            echo "  - DATAVERSE_ENVIRONMENT_ID (use Default-<tenant-id>)"
            echo "  - DATAVERSE_USERNAME"
            echo "  - DATAVERSE_PASSWORD"
        else
            print_error "Could not find .env.example file"
        fi
    else
        echo ""
        echo "You can create the configuration file later by copying:"
        echo "  cp $DATAVERSE_CLI_DIR/.env.example $DATAVERSE_CLI_DIR/.env"
    fi
fi

# Step 7: Verify installation
print_step "Verifying installation..."

# Check if commands are available
DATAVERSE_FOUND=false
POWERAUTOMATE_FOUND=false

if command -v dataverse &> /dev/null; then
    DATAVERSE_FOUND=true
    print_success "dataverse command is available"
else
    print_error "dataverse command not found in PATH"
fi

if command -v powerautomate &> /dev/null; then
    POWERAUTOMATE_FOUND=true
    print_success "powerautomate command is available"
else
    print_error "powerautomate command not found in PATH"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Installation Complete!                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ "$DATAVERSE_FOUND" = true ] && [ "$POWERAUTOMATE_FOUND" = true ]; then
    echo -e "${GREEN}Both CLIs are ready to use!${NC}"
    echo ""
    echo "Try these commands:"
    echo "  dataverse --help"
    echo "  powerautomate --help"
    echo ""
    echo "Configuration location:"
    echo "  $DATAVERSE_CLI_DIR/.env"
    echo ""
    echo "Documentation:"
    echo "  https://github.com/adbertram/Microsoft-Dataverse-CLI"
    echo "  https://github.com/adbertram/Microsoft-Power-Automate-CLI"
else
    echo -e "${YELLOW}Installation completed with warnings${NC}"
    echo ""
    echo "If commands are not found, ensure ~/.local/bin is in your PATH:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then restart your shell or run: source ~/.bashrc"
fi

echo ""
