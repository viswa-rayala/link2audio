#!/bin/bash
# Kill any process currently occupying port 8000
fuser -k 8000/tcp 2>/dev/null || true

# Give the port a split second to clear
sleep 0.5

# Start the server
.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --reload
