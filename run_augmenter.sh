#!/bin/bash
# Image Augmentation Script Wrapper
# Sets up virtual environment, installs dependencies, and runs the augmenter

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PYTHON_SCRIPT="$SCRIPT_DIR/process_files.py"
CONFIG_FILE="$SCRIPT_DIR/config.json"

# Temporary credentials for CI/CD
TEMP_CREDENTIALS_FILE=""
TEMP_TOKEN_FILE=""
CLEANUP_NEEDED=false

echo -e "${GREEN}=== Image Augmentation Setup & Runner ===${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Cleanup function for temporary files
cleanup() {
    if [ "$CLEANUP_NEEDED" = true ]; then
        echo -e "${YELLOW}Cleaning up temporary credentials...${NC}"
        if [ -n "$TEMP_CREDENTIALS_FILE" ] && [ -f "$TEMP_CREDENTIALS_FILE" ]; then
            rm -f "$TEMP_CREDENTIALS_FILE"
            echo -e "${GREEN}✓ Removed temporary credentials.json${NC}"
        fi
        if [ -n "$TEMP_TOKEN_FILE" ] && [ -f "$TEMP_TOKEN_FILE" ]; then
            rm -f "$TEMP_TOKEN_FILE"
            echo -e "${GREEN}✓ Removed temporary token.json${NC}"
        fi
    fi
}

# Set up trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Check for Python 3
if ! command_exists python3; then
    echo -e "${RED}Error: python3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}Found Python $PYTHON_VERSION${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip --quiet

# Install/upgrade requirements
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Installing dependencies from requirements.txt...${NC}"
    pip install -r "$REQUIREMENTS_FILE" --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}Warning: requirements.txt not found at $REQUIREMENTS_FILE${NC}"
fi

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}Error: process_files.py not found at $PYTHON_SCRIPT${NC}"
    exit 1
fi

# Handle credentials for CI/CD
echo -e "${YELLOW}Setting up credentials...${NC}"

# Create credentials.json from environment variable if provided
if [ -n "$CREDENTIALS_JSON" ]; then
    TEMP_CREDENTIALS_FILE="$SCRIPT_DIR/credentials.json"
    echo "$CREDENTIALS_JSON" > "$TEMP_CREDENTIALS_FILE"
    CLEANUP_NEEDED=true
    export CREDENTIALS_PATH="$TEMP_CREDENTIALS_FILE"
    echo -e "${GREEN}✓ Created credentials.json from CREDENTIALS_JSON env var${NC}"
fi

# Create temporary token.json location
if [ -n "$CREDENTIALS_JSON" ] || [ -n "$TOKEN_JSON" ]; then
    TEMP_TOKEN_FILE="$SCRIPT_DIR/token.json.tmp"

    # If TOKEN_JSON env var is provided, use it
    if [ -n "$TOKEN_JSON" ]; then
        echo "$TOKEN_JSON" > "$TEMP_TOKEN_FILE"
        echo -e "${GREEN}✓ Created token.json from TOKEN_JSON env var${NC}"
    fi

    CLEANUP_NEEDED=true
    export TOKEN_PATH="$TEMP_TOKEN_FILE"
fi

# Check for config file or environment variables
if [ ! -f "$CONFIG_FILE" ] && [ -z "$INPUT_FOLDER_ID" ] && [ -z "$LOCAL_INPUT_PATH" ]; then
    echo -e "${YELLOW}Warning: No configuration found${NC}"
    echo -e "${YELLOW}Please either:${NC}"
    echo -e "${YELLOW}  1. Create config.json in $SCRIPT_DIR${NC}"
    echo -e "${YELLOW}  2. Set environment variables (INPUT_FOLDER_ID, OUTPUT_FOLDER_ID, etc.)${NC}"
    echo -e "${YELLOW}  3. Pass configuration as command-line arguments${NC}"
    echo ""
    echo -e "${YELLOW}Example usage:${NC}"
    echo ""
    echo -e "${GREEN}With config.json (recommended):${NC}"
    echo "  ./run_augmenter.sh --operation augment --n-samples 3"
    echo ""
    echo -e "${GREEN}With environment variables:${NC}"
    echo "  export INPUT_FOLDER_ID='1VScZDE8q1xdHIq1kY588uT-detAMDfei'"
    echo "  export OUTPUT_FOLDER_ID='1NK1qtldoJAmYqhSoWQi8e1ZPgMDr5dzD'"
    echo "  ./run_augmenter.sh --operation augment --n-samples 3"
    echo ""
fi

# Run the Python script
echo -e "${GREEN}=== Running Image Augmentation ===${NC}"
python3 "$PYTHON_SCRIPT" --operation augment "$@"

# Capture exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Augmentation completed successfully${NC}"
else
    echo -e "${RED}✗ Augmentation failed with exit code $EXIT_CODE${NC}"
fi

# Deactivate virtual environment
deactivate

# Explicit cleanup (trap will also call this, but being explicit)
cleanup

exit $EXIT_CODE
