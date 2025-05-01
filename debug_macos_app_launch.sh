#!/bin/bash
# Simulate launching the ANPE GUI .app bundle using the debug environment
# This script mimics the behavior of main_macos.py when run inside a .app,
# using the Python environment created by debug_macos_setup.sh.

# --- Configuration ---
APP_NAME="ANPE GUI"
DEFAULT_DEBUG_INSTALL_DIR="./debug_install"
SETUP_FLAG_FILE=".setup_complete"

# Terminal colors
RESET_COLOR="\033[0m"
BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
RED="\033[31m"

# --- Helper Functions ---
print_info() {
  echo -e "${BOLD}${BLUE}INFO:${RESET_COLOR} $1"
}

print_warn() {
  echo -e "${BOLD}${YELLOW}WARN:${RESET_COLOR} $1"
}

print_error() {
  echo -e "${BOLD}${RED}ERROR:${RESET_COLOR} $1" >&2
}

# --- Argument Parsing ---
FORCE_SETUP=false
DEBUG_INSTALL_DIR="" # Allow override

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --force-setup) FORCE_SETUP=true; shift ;;
        --install-path=*) DEBUG_INSTALL_DIR="${1#*=}"; shift ;;
        *) echo "Unknown parameter passed: $1"; \
           echo "Usage: $0 [--force-setup] [--install-path=PATH]"; \
           exit 1 ;;
    esac
done

# --- Determine Project Root and Debug Install Directory ---
PROJECT_ROOT=$(dirname "$(realpath "$0")")
cd "$PROJECT_ROOT" || exit 1 # Ensure we are in the project root

# Use provided path or default
if [ -z "$DEBUG_INSTALL_DIR" ]; then
    # Check environment variable as a fallback, like run_anpe_debug.sh
    if [ -n "$ANPE_INSTALL_PATH" ]; then
        DEBUG_INSTALL_DIR="$ANPE_INSTALL_PATH"
        print_info "Using debug install path from ANPE_INSTALL_PATH: $DEBUG_INSTALL_DIR"
    else
        DEBUG_INSTALL_DIR="$DEFAULT_DEBUG_INSTALL_DIR"
        print_info "Using default debug install path: $DEBUG_INSTALL_DIR"
    fi
fi

# Ensure the debug install path is absolute
DEBUG_INSTALL_DIR_ABS=$(realpath "$DEBUG_INSTALL_DIR")

if [ ! -d "$DEBUG_INSTALL_DIR_ABS" ]; then
    print_error "Debug install directory not found: $DEBUG_INSTALL_DIR_ABS"
    print_error "Please run './debug_macos_setup.sh' first (potentially with --install-path=\"$DEBUG_INSTALL_DIR\")."
    exit 1
fi

# Export the determined install path for main_macos.py to use in simulation mode
export ANPE_INSTALL_PATH="$DEBUG_INSTALL_DIR_ABS"
print_info "Exported ANPE_INSTALL_PATH=$ANPE_INSTALL_PATH"

# --- Setup Flag Handling (in Debug Directory) ---
SETUP_FLAG_PATH="$DEBUG_INSTALL_DIR_ABS/$SETUP_FLAG_FILE" # Check flag in debug dir

if [ "$FORCE_SETUP" = true ]; then
     if [ -f "$SETUP_FLAG_PATH" ]; then
        print_info "--force-setup requested, removing existing setup flag: $SETUP_FLAG_PATH"
        rm "$SETUP_FLAG_PATH"
    else
        print_info "--force-setup requested, flag not found in debug directory."
     fi
fi

# --- Execute main_macos.py with Simulated Bundle Environment --- 
MAIN_SCRIPT="$PROJECT_ROOT/main_macos.py"

if [ ! -f "$MAIN_SCRIPT" ]; then
    print_error "Main script not found: $MAIN_SCRIPT"
    exit 1
fi

print_info "Simulating .app launch by running main_macos.py using system python3..."
print_info "Setting ANPE_SIMULATE_APP_BUNDLE=1"

# Set the environment variable and run the main script using system python3
export ANPE_SIMULATE_APP_BUNDLE=1

# Use system python3 to run the main script
python3 "$MAIN_SCRIPT"

EXIT_CODE=$?

# Unset variable after execution (optional, good practice)
unset ANPE_SIMULATE_APP_BUNDLE
unset ANPE_INSTALL_PATH # Unset the exported path

print_info "Simulation finished with exit code: $EXIT_CODE"
exit $EXIT_CODE 