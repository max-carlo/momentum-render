#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install -r requirements.txt

# Setze Playwright-Umgebungsvariablen
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Installiere die benötigten Browser für Playwright
playwright install --with-deps

# Starte Streamlit mit `momentum.py`
streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0