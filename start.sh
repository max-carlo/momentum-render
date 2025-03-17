#!/bin/bash

# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install -r requirements.txt

# Setze die Umgebungsvariable für Chrome
export CHROME_BIN=/usr/bin/google-chrome
export PATH=$PATH:/usr/bin/

# Starte das Python-Skript
python momentum.py
