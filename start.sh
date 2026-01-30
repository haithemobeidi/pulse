#!/bin/bash

# PC-Inspector - One-Click Startup
# Simple Flask app - single command, everything included

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "PC-Inspector Starting..."
echo ""

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Initialize database
if [ ! -f "data/system.db" ]; then
    echo "Initializing database..."
    python scripts/init_database.py
fi

# Start Flask app
echo ""
echo "========================================"
echo "PC-Inspector is starting..."
echo "Dashboard: http://localhost:5000"
echo "========================================"
echo ""

python -m backend.app
