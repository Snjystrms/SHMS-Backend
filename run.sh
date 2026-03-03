#!/usr/bin/env bash
# Start backend so it's reachable from Expo/frontend (localhost + LAN IP e.g. 192.168.1.27:8000)
uvicorn app.main:app --reload --host 0.0.0.0
