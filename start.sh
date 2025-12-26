#!/bin/bash

# Kill any existing processes
lsof -ti:8090 | xargs kill -9 2>/dev/null || true
lsof -ti:3000,3001 | xargs kill -9 2>/dev/null || true

# Start API
echo "Starting API on port 8090..."
services/api/.venv/bin/uvicorn app.main:app --app-dir services/api --reload --port 8090 &
API_PID=$!

# Start Worker
echo "Starting Worker..."
PYTHONPATH=services/worker services/worker/.venv/bin/python -m worker &
WORKER_PID=$!

# Start Frontend
echo "Starting Frontend..."
pnpm -C apps/web dev &
FRONTEND_PID=$!

echo ""
echo "Services started:"
echo "  API: http://localhost:8090 (PID: $API_PID)"
echo "  Worker: PID $WORKER_PID"
echo "  Frontend: http://localhost:3000 (PID: $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap "kill $API_PID $WORKER_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
