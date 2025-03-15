#!/bin/bash
pip install -r requirements.txt
# WebDriver für Selenium automatisch installieren
python -c "from selenium import webdriver; from webdriver_manager.chrome import ChromeDriverManager; webdriver.Chrome(ChromeDriverManager().install())"
# Starte Streamlit App
streamlit run momentum.py --server.port=10000 --server.address=0.0.0.0
