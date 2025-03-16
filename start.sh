#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

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
