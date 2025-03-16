#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Installiere Playwright-Browser (nur falls nicht vorhanden)
playwright install --with-deps chromium

# Setze Playwright-Umgebungsvariable
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Starte die Streamlit-App auf dem richtigen Port
streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0