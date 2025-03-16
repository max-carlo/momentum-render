#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install --no-cache-dir -r requirements.txt

# Setze Chrome-Pfad für Selenium
export CHROME_BIN="/usr/bin/google-chrome"

# Starte das Hauptskript
python momentum.py
