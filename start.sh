#!/bin/bash

# PC-Inspector - One-Click Startup Script for WSL2/Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           PC-INSPECTOR - Starting Services                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Install Python 3.12 and try again"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install dependencies
echo "[2/4] Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt

# Initialize database
if [ ! -f "data/system.db" ]; then
    echo "[3/4] Initializing database..."
    python scripts/init_database.py
else
    echo "[3/4] Database already initialized"
fi

# Start services
echo "[4/4] Starting services..."
echo ""
echo -e "${GREEN}Starting Backend (FastAPI) on http://localhost:8000${NC}"

# Start backend in background
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > /tmp/pc-inspector-backend.log 2>&1 &
BACKEND_PID=$!

sleep 2

echo -e "${GREEN}Starting Frontend (HTTP Server) on http://localhost:8080${NC}"

# Start frontend in background
cd "$SCRIPT_DIR/frontend"
python -m http.server 8080 > /tmp/pc-inspector-frontend.log 2>&1 &
FRONTEND_PID=$!

cd "$SCRIPT_DIR"

sleep 2

# Display status
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║             Services Started Successfully!                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Dashboard:${NC}  http://localhost:8080"
echo -e "${GREEN}API Docs:${NC}   http://localhost:8000/docs"
echo ""
echo "Both services running in background:"
echo "  Backend PID: $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo ""
echo "View logs:"
echo "  Backend:  tail -f /tmp/pc-inspector-backend.log"
echo "  Frontend: tail -f /tmp/pc-inspector-frontend.log"
echo ""
echo -e "${YELLOW}Open in browser: http://localhost:8080${NC}"
echo ""

# Attempt to open browser
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8080" 2>/dev/null || true
elif command -v open &> /dev/null; then
    open "http://localhost:8080" 2>/dev/null || true
fi

# Wait for input to stop
echo "Press Enter to stop services and exit..."
read

# Stop processes
echo ""
echo "Shutting down services..."
kill $BACKEND_PID 2>/dev/null || true
kill $FRONTEND_PID 2>/dev/null || true

# Deactivate venv
deactivate 2>/dev/null || true

echo "Services closed. Goodbye!"
