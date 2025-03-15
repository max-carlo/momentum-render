# Verwende ein offizielles Python-Image als Basis
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere die Anwendungsdateien in den Container
COPY . /app

# Installiere die benötigten Pakete
RUN apt-get update && apt-get install -y \
    curl unzip xvfb \
    && rm -rf /var/lib/apt/lists/*

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Installiere Playwright und Browser
RUN pip install playwright && playwright install chromium

# Setze die Umgebungsvariablen für Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Stelle sicher, dass die Datei ausführbar ist
RUN chmod +x start.sh

# Definiere das Startkommando
CMD ["./start.sh"]
