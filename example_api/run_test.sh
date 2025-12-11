#!/bin/bash

# Data Catalog API - Test Mode Runner
# This script runs the API in test mode using local _data files

echo "🧪 Starting Data Catalog API in TEST MODE"
echo "=========================================="
echo "Mode: TEST MODE (using local _data files)"
echo "Port: 8000"
echo ""

# Set environment variables for test mode
export TEST_MODE=true
export PASSTHROUGH_MODE=false
export PORT=8000

echo "Environment variables set:"
echo "  TEST_MODE=$TEST_MODE"
echo "  PASSTHROUGH_MODE=$PASSTHROUGH_MODE"
echo "  PORT=$PORT"
echo ""

echo "Starting API..."
echo "Press Ctrl+C to stop"
echo ""

# Run the API
python3 main.py
