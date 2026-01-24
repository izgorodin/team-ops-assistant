#!/bin/bash
# Team Ops Assistant - Local Development Setup
#
# Usage:
#   ./run.sh                        # Setup environment + show available commands
#   ./run.sh --server               # Start HTTP server (webhook mode)
#   ./run.sh --polling              # Polling mode - local Telegram bot testing
#   ./run.sh --tunnel               # Tunnel mode - ngrok + webhooks locally
#   ./run.sh --tunnel --restore-webhook  # Same, restore original webhook on exit
#
# POLLING MODE (simplest for bot development):
#   Uses Telegram getUpdates API instead of webhooks.
#   No public URL needed - works on localhost!
#   Note: Automatically disables webhook on Telegram.
#
# TUNNEL MODE (requires ngrok):
#   Starts ngrok to create a public URL for localhost.
#   Sets Telegram webhook to the ngrok URL.
#   Install ngrok first: brew install ngrok/ngrok/ngrok
#   Then authenticate: ngrok config add-authtoken YOUR_TOKEN
#
# SERVER MODE:
#   Starts HTTP server on localhost:8000.
#   Useful for: pytest, health checks, API endpoint testing.
#   Cannot receive Telegram messages (needs public URL).

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}Team Ops Assistant - Development Environment${NC}"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3.11 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip quietly
pip install --upgrade pip --quiet 2>/dev/null

# Install dependencies (dev includes prod + testing/linting tools)
echo "Checking dependencies..."
pip install -r requirements-dev.txt --quiet 2>/dev/null
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Set default port if not specified
PORT="${APP_PORT:-8000}"
HOST="${APP_HOST:-0.0.0.0}"

# Check for mode
if [[ "$1" == "--polling" ]]; then
    echo ""
    echo "================================================"
    echo "Starting in POLLING MODE (local development)"
    echo "Send a message to your Telegram bot to test!"
    echo "================================================"
    echo ""
    exec python -m src.app --polling

elif [[ "$1" == "--tunnel" ]]; then
    RESTORE_FLAG=""
    if [[ "$2" == "--restore-webhook" ]]; then
        RESTORE_FLAG="--restore-webhook"
    fi
    echo ""
    echo "================================================"
    echo "Starting in TUNNEL MODE (ngrok + webhooks)"
    echo "This will start ngrok and set Telegram webhook"
    echo "================================================"
    echo ""
    exec python -m src.app --tunnel --port "$PORT" $RESTORE_FLAG

elif [[ "$1" == "--server" ]]; then
    echo ""
    echo "================================================"
    echo "Starting HTTP server on $HOST:$PORT"
    echo "================================================"
    echo ""
    exec python -m src.app --host "$HOST" --port "$PORT"

else
    # No arguments - start server (default mode)
    echo ""
    echo -e "${GREEN}✓ Environment ready!${NC}"
    echo ""
    echo "Other modes available:"
    echo -e "  ${BLUE}./run.sh --polling${NC}    Telegram polling (local bot testing)"
    echo -e "  ${BLUE}./run.sh --tunnel${NC}     ngrok tunnel (webhooks locally)"
    echo ""
    echo "================================================"
    echo "Starting HTTP server on $HOST:$PORT"
    echo -e "Health check: ${YELLOW}curl localhost:$PORT/health${NC}"
    echo "================================================"
    echo ""

    # Start server in background
    python -m src.app --host "$HOST" --port "$PORT" &
    SERVER_PID=$!

    # Cleanup function
    cleanup() {
        echo ""
        echo -e "${YELLOW}Stopping server...${NC}"
        kill $SERVER_PID 2>/dev/null
        wait $SERVER_PID 2>/dev/null
        echo -e "${GREEN}✓ Server stopped${NC}"
        exit 0
    }

    # Trap Ctrl+C and other signals
    trap cleanup SIGINT SIGTERM

    # Wait for server to be ready (try health check up to 10 times)
    echo -n "Waiting for server"
    for i in {1..10}; do
        if curl -s "localhost:$PORT/health" > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✓ Health check passed!${NC}"
            break
        fi
        echo -n "."
        sleep 0.5
    done

    # Check if server is still running
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo ""
        echo -e "${YELLOW}⚠ Server failed to start${NC}"
        exit 1
    fi

    echo ""
    echo "Press Ctrl+C to stop"
    echo ""

    # Wait for server
    wait $SERVER_PID
fi
