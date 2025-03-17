#!/bin/bash

echo "Checking if Streamlit is installed..."
pip show streamlit || pip install streamlit

echo "Starting virtual display for Chrome..."
Xvfb :99 -screen 0 1920x1080x16 &

echo "Starting Streamlit..."
streamlit run momentum.py --server.port=8501 --server.address=0.0.0.0
