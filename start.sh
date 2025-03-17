#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Setze Chrome-Pfad für Selenium
export CHROME_BIN=$(which google-chrome)

# Prüfe, ob Chrome wirklich existiert
if [ ! -f "$CHROME_BIN" ]; then
    echo "Fehler: Google Chrome wurde nicht gefunden!"
    exit 1
fi

# Starte das Hauptskript
python momentum.py