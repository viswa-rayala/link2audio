#!/bin/bash
PORT="${1:-8000}"

# Kill any process currently occupying the port
fuser -k "${PORT}/tcp" 2>/dev/null || true

# Give the port a split second to clear
sleep 0.5

echo "Starting YouTube to MP3 Converter on http://localhost:${PORT} ..."
# Start the server
.venv/bin/uvicorn server:app --host 0.0.0.0 --port "${PORT}" --reload
