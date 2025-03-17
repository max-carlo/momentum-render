#!/bin/bash

echo "Starting virtual display for Chrome..."
if ! pgrep Xvfb > /dev/null; then
    Xvfb :99 -screen 0 1920x1080x16 & 
    export DISPLAY=:99
else
    echo "Xvfb is already running, skipping start."
fi

echo "Ensuring all Python dependencies are installed..."
pip install --no-cache-dir -r requirements.txt

echo "Setting up Chrome environment variables..."
export CHROME_BIN=/usr/bin/google-chrome
export CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

echo "Starting Streamlit..."
streamlit run momentum.py --server.port=${PORT:-8501} --server.address=0.0.0.0
