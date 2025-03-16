# Verwende ein schlankes Python-Image als Basis
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere die App-Dateien in den Container
COPY . /app

# Installiere Systemabhängigkeiten für Playwright (kein Selenium nötig!)
RUN apt-get update && apt-get install -y \
    curl unzip xvfb libnss3 libxss1 libasound2 libxrandr2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxdamage1 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Setze die Umgebungsvariable, damit Playwright-Browser an den richtigen Ort installiert werden
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip && pip install -r requirements.txt

# Installiere Playwright mit Abhängigkeiten
RUN playwright install --with-deps

# Stelle sicher, dass die Startdatei ausführbar ist
RUN chmod +x start.sh

# Definiere das Startkommando
CMD ["bash", "start.sh"]
