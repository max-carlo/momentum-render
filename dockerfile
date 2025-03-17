# Verwende ein offizielles Python-Image als Basis
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere die Dateien in das Containerverzeichnis
COPY . /app

# Installiere benötigte Systempakete
RUN apt-get update && apt-get install -y \
    wget unzip curl \
    google-chrome-stable \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Setze Umgebungsvariablen für Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV PATH=$PATH:/usr/bin/

# Mache das Start-Skript ausführbar
RUN chmod +x start.sh

# Definiere den Startbefehl
CMD ["./start.sh"]
