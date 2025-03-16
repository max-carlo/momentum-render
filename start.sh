#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install -r requirements.txt

# Setze Playwright-Umgebungsvariablen
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Starte die Anwendung
streamlit run app.py --server.port=10000 --server.address=0.0.0.0
python momentum.py