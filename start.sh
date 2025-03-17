#!/bin/bash

echo "Starting virtual display for Chrome..."
Xvfb :99 -screen 0 1920x1080x16 &
export DISPLAY=:99

echo "Checking if Streamlit is installed..."
pip show streamlit || pip install streamlit

echo "Starting Streamlit..."
export PORT=10000  # Render erwartet diesen Port
streamlit run momentum.py --server.port=$PORT --server.address=0.0.0.0