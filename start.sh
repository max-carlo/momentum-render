#!/bin/bash

# Start Xvfb for headless Chrome
Xvfb :99 -screen 0 1024x768x16 &
export DISPLAY=:99

# Start the application
streamlit run momentum.py --server.port=${PORT:-8501} --server.address=0.0.0.0