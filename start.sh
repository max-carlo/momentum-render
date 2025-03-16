#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Setze die Playwright-Umgebungsvariable (wichtig!)
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Starte dein Python-Skript
python momentum.py