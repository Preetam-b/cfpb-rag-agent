#!/bin/bash
set -e

# FastAPI backend, internal only -- this is the 127.0.0.1:8000 that
# streamlit_app.py's API_BASE already points at. Not exposed outside the container.
uvicorn api:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# Give it a moment to come up before Streamlit starts hitting it.
sleep 3

# Streamlit is the process HF Spaces actually exposes (port 7860, see Dockerfile/README).
streamlit run streamlit_app.py --server.port 7860 --server.address 0.0.0.0 --server.headless true &
STREAMLIT_PID=$!

# If either process dies, bring the whole container down so HF Spaces
# shows it as crashed instead of silently half-working.
wait -n "$API_PID" "$STREAMLIT_PID"
exit $?