# Verwende ein schlankes Python-Image als Basis
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere alle Dateien ins Container-Verzeichnis
COPY . /app

# Installiere Systemabhängigkeiten für Selenium & Chrome
RUN apt-get update && apt-get install -y \
    wget curl unzip libnss3 libxss1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# Installiere Google Chrome (Headless-Modus für Selenium)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Stelle sicher, dass das Start-Skript ausführbar ist
RUN chmod +x start.sh

# Definiere das Startkommando
CMD ["./start.sh"]
