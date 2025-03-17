# Verwende ein leichtes Python-Image als Basis
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere alle Dateien ins Container-Verzeichnis
COPY . /app

# Installiere Systemabhängigkeiten für Selenium & Chrome
RUN apt-get update && apt-get install -y \
    wget curl unzip libnss3 libxss1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libgtk-3-0 libgbm-dev libxshmfence1 ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Installiere Google Chrome & ChromeDriver
RUN wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb

# Stelle sicher, dass Chrome existiert
RUN which google-chrome || (echo "Chrome installation failed!" && exit 1)

# Setze die Umgebungsvariable für Chrome
ENV CHROME_BIN="/usr/bin/google-chrome"

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Stelle sicher, dass das Start-Skript ausführbar ist
RUN chmod +x start.sh

# Definiere das Startkommando
CMD ["./start.sh"]
