#!/bin/bash

echo "Starting virtual display for Chrome..."
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

echo "Ensuring all Python dependencies are installed..."
pip install --no-cache-dir -r requirements.txt

echo "Disabling Streamlit onboarding..."
export STREAMLIT_DISABLE_ONBOARDING=1

# **Wichtiger Fix für den X11-Fehler**
echo "Fixing /tmp/.X11-unix permissions..."
if [ -d /tmp/.X11-unix ]; then
    rm -rf /tmp/.X11-unix
fi
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix || true

echo "Starting Streamlit on Render..."
streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0
