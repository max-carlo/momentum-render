#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Playwright-Browser installieren (falls nicht schon in Docker installiert)
playwright install --with-deps chromium

# Setze die Playwright-Umgebungsvariable (WICHTIG!)
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Prüfe, ob eine Web-App (Streamlit) genutzt wird
if grep -q "streamlit" requirements.txt; then
    echo "Starte Streamlit..."
    streamlit run momentum.py --server.port=${PORT:-10000} --server.address=0.0.0.0
else
    echo "Starte Momentum-Skript..."
    python momentum.py
fi
