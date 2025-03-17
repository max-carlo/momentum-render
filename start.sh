#!/bin/bash

echo "Starting virtual display for Chrome..."
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

echo "Ensuring Streamlit is installed..."
pip install --no-cache-dir streamlit

echo "Fixing X11 permissions (Render-safe)..."
chmod 1777 /tmp/.X11-unix || true

echo "Disabling Streamlit onboarding..."
export STREAMLIT_DISABLE_ONBOARDING=1

echo "Starting Streamlit on Render..."
streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0
