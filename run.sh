#!/bin/bash

# Stock Analyzer - Launch Script
# This script installs dependencies and starts both backend and frontend

set -e

echo "🚀 Stock Analyzer - Starting..."
echo "================================"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+"
    exit 1
fi

# Backend setup
echo -e "${BLUE}📦 Setting up Python backend...${NC}"
cd "$SCRIPT_DIR/backend"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt --quiet

echo -e "${GREEN}✅ Backend dependencies installed${NC}"

# Frontend setup
echo -e "${BLUE}📦 Setting up React frontend...${NC}"
cd "$SCRIPT_DIR/frontend"

# Install npm dependencies
npm install --silent

echo -e "${GREEN}✅ Frontend dependencies installed${NC}"

# Start backend in background
echo -e "${BLUE}🔧 Starting backend server on port 8000...${NC}"
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo -e "${BLUE}🎨 Starting frontend on port 5173...${NC}"
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

# Open browser
echo -e "${GREEN}🌐 Opening browser...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:5173"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open "http://localhost:5173" 2>/dev/null || echo "Please open http://localhost:5173 in your browser"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✨ Stock Analyzer is running!${NC}"
echo ""
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"
echo -e "${GREEN}================================${NC}"

# Handle shutdown
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
