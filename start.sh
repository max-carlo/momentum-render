#!/bin/bash
pip install -r requirements.txt
# Installiere Playwright und benötigte Dependencies
playwright install --with-deps
# Starte die Streamlit-App
streamlit run app.py --server.port=10000 --server.address=0.0.0.0
# Führe das Scraping-Skript aus
python momentum.py