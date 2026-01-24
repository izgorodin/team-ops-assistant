#!/bin/bash
# Team Ops Assistant - Local Development Server
#
# Purpose: Run server locally for development and testing
#
# What this script CAN do:
#   - Set up venv and install dependencies
#   - Run local server for health checks: curl localhost:8000/health
#   - Enable local API endpoint testing
#   - Run tests: source .venv/bin/activate && pytest
#
# What this script CANNOT do:
#   - Receive Telegram/Discord/WhatsApp webhooks (requires public URL)
#   - End-to-end bot testing
#
# For actual bot testing: Deploy to Render (see docs/RUNBOOK.md)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3.11 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Set default port if not specified
PORT="${APP_PORT:-8000}"
HOST="${APP_HOST:-0.0.0.0}"

echo ""
echo "================================================"
echo "Starting Team Ops Assistant on $HOST:$PORT"
echo "================================================"
echo ""

# Run the Quart application
exec python -m src.app --host "$HOST" --port "$PORT"
