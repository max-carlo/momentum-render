#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Setze Playwright-Umgebungsvariablen
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Starte Streamlit auf dem von Render bereitgestellten Port
streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0