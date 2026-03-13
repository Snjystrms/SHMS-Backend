#!/usr/bin/env bash
# Start backend so it's reachable from Expo/frontend (localhost + LAN IP e.g. 192.168.1.27:8000)
set -euo pipefail

UVICORN_BIN="uvicorn"
if [[ -x "./venv/bin/uvicorn" ]]; then
  UVICORN_BIN="./venv/bin/uvicorn"
fi

$UVICORN_BIN app.main:app --reload --host 0.0.0.0 --port 8000
