#!/bin/bash

# Starte virtuellen Display-Server für Chrome (falls benötigt)
if ! pgrep -x "Xvfb" > /dev/null
then
    echo "Starte Xvfb..."
    Xvfb :99 -screen 0 1024x768x24 &
    sleep 2
else
    echo "Xvfb läuft bereits."
fi
export DISPLAY=:99

# Installiere Python-Abhängigkeiten
pip install -r requirements.txt --no-cache-dir

# Setze explizit den Port auf die Render PORT Variable
echo "Starte Streamlit auf Port $PORT ..."
streamlit run momentum.py --server.port=${PORT} --server.address=0.0.0.0
