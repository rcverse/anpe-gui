#!/bin/bash
# Debug launcher for ANPE GUI macOS setup
# This script prepares a local debug environment by running the setup process.

# Parse arguments
RESET=true # Default to reset for debug runs unless otherwise specified
VERBOSE=false
# SKIP_MODELS=false # This is handled by the underlying setup logic now if needed

INSTALL_PATH="" # Default to be set later

# Terminal colors
RESET_COLOR="\033[0m"
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
RED="\033[31m"

# Project root is where this script is located
PROJECT_ROOT=$(dirname "$(realpath "$0")")

# Process command line arguments
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --reset=false | --no-reset) # Add option to disable reset
      RESET=false
      shift
      ;;
    --reset)
      RESET=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    # --skip-models argument removed as it's not directly used here
    --install-path=*) # Allow specifying install path via argument
      INSTALL_PATH="${1#*=}"
      shift
      ;;
    *)
      # Unknown option
      echo "Unknown option: $1"
      echo "Usage: $0 [--reset|--no-reset] [--verbose] [--install-path=PATH]"
      exit 1
      ;;
  esac
done

# --- Configuration (Consolidated & Updated) ---
INSTALLER_ASSETS_DIR="installer/assets"
PBS_ARCHIVE_ARM64="cpython-3.12.10+20250409-aarch64-apple-darwin-install_only_stripped.tar.gz"
PBS_ARCHIVE_X86_64="cpython-3.12.10+20250409-x86_64-apple-darwin-install_only_stripped.tar.gz"
APP_SOURCE_DIR="anpe_gui"
SETUP_SCRIPT_MODULE="installer.setup_macos"

# Use provided INSTALL_PATH or default to ./debug_install
if [ -z "$INSTALL_PATH" ]; then
  INSTALL_PATH="./debug_install"
fi

# Convert to absolute path early
INSTALL_DIR_ABS="$(mkdir -p "$INSTALL_PATH" && cd "$INSTALL_PATH" && pwd)"
if [ -z "$INSTALL_DIR_ABS" ]; then
    echo -e "${RED}Error: Failed to determine or create absolute path for install directory: $INSTALL_PATH${RESET_COLOR}"
    exit 1
fi

# --- Helper Functions ---
print_step() {
    echo -e "\n==== $1 ===="
}

print_error() {
    echo -e "${RED}ERROR: $1${RESET_COLOR}" >&2
    exit 1
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${RESET_COLOR}"
}

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓ ${2} found: ${1}${RESET_COLOR}"
        return 0
    else
        echo -e "${RED}✗ ${2} missing: ${1}${RESET_COLOR}"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓ ${2} exists at: ${1}${RESET_COLOR}"
        return 0
    else
        echo -e "${RED}✗ ${2} missing: ${1}${RESET_COLOR}"
        return 1
    fi
}

# --- Pre-flight Checks ---
print_step "Checking Required Assets"
cd "$PROJECT_ROOT" # Ensure checks run from project root

ASSET_CHECKS_PASSED=true
check_dir "$INSTALLER_ASSETS_DIR" "Installer assets directory" || ASSET_CHECKS_PASSED=false
check_file "$INSTALLER_ASSETS_DIR/$PBS_ARCHIVE_ARM64" "Standalone Python archive (ARM64)" || ASSET_CHECKS_PASSED=false
check_file "$INSTALLER_ASSETS_DIR/$PBS_ARCHIVE_X86_64" "Standalone Python archive (x86_64)" || ASSET_CHECKS_PASSED=false
check_dir "$APP_SOURCE_DIR" "Application source code" || ASSET_CHECKS_PASSED=false

if [ "$ASSET_CHECKS_PASSED" = false ]; then
    echo ""
    echo "One or more required assets are missing."
    echo "Please ensure the following exist relative to the script location ($PROJECT_ROOT):"
    echo "  - Directory: $INSTALLER_ASSETS_DIR"
    echo "  - Directory: $APP_SOURCE_DIR"
    echo "  - File: $INSTALLER_ASSETS_DIR/$PBS_ARCHIVE_ARM64"
    echo "  - File: $INSTALLER_ASSETS_DIR/$PBS_ARCHIVE_X86_64"
    echo ""
    echo "You can download the required Python archives from the python-build-standalone releases page."
    exit 1
fi

echo "✓ Asset checks complete!"

# --- Main Setup Logic ---
print_step "ANPE GUI macOS Setup Debug"
echo "Install path: $INSTALL_DIR_ABS"
echo "Reset installation: $RESET"
echo "Verbose logging: $VERBOSE"
echo "=================================="

if [ "$RESET" = true ]; then
    print_step "Resetting installation..."
    if [ -d "$INSTALL_DIR_ABS" ]; then
        echo "Removing existing debug install directory: $INSTALL_DIR_ABS"
        rm -rf "$INSTALL_DIR_ABS" || print_error "Failed to remove existing directory."
    fi
     # Ensure the directory exists after potential reset
    mkdir -p "$INSTALL_DIR_ABS" || print_error "Failed to create install directory: $INSTALL_DIR_ABS"
    echo "Reset complete"
fi

# Verify write permissions again after potential reset/creation
if [ ! -w "$INSTALL_DIR_ABS" ]; then
  print_error "Install directory is not writable: $INSTALL_DIR_ABS"
fi

print_step "Launching setup script..."

# Set environment variables for setup script
export ANPE_DEBUG="1" # Indicate debug mode to installer if needed
if [ "$VERBOSE" = true ]; then
    export ANPE_VERBOSE="1"
fi

# Define command as an array
COMMAND_ARRAY=(
    "python3"
    "-m"
    "$SETUP_SCRIPT_MODULE"
    "--debug"
    "--target-install-dir=$INSTALL_DIR_ABS" 
)

# Echo the command for clarity, quoting elements properly
printf -v CMD_STR '%q ' "${COMMAND_ARRAY[@]}"
echo "Command: ${CMD_STR}"

# Execute the command using the array
if "${COMMAND_ARRAY[@]}"; then
    echo -e "${GREEN}Debug environment setup completed successfully in: $INSTALL_DIR_ABS${RESET_COLOR}"
    echo -e "\nYou can now simulate launching the application with:"
    echo -e "${BLUE}./debug_macos_app_launch.sh --install-path=\"$INSTALL_DIR_ABS\"${RESET_COLOR}"
    echo -e "(Use --force-setup with the launch script to test the setup check logic)"
else
    print_error "Debug environment setup failed with exit code $?"
    exit 1 # Already exits due to set -e, but explicit for clarity
fi

# Unset environment variables if they were set
unset ANPE_DEBUG
unset ANPE_VERBOSE

print_step "Debug Setup Finished"
exit 0

# --- END OF SCRIPT --- 
# (Removed redundant logic below this line) 