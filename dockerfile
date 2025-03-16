# Verwende ein leichtgewichtiges Python-Image
FROM python:3.10-slim

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere alle Dateien in das Arbeitsverzeichnis
COPY . /app

# Installiere Systemabhängigkeiten für Playwright
RUN apt-get update && apt-get install -y \
    curl unzip xvfb libnss3 libxss1 libasound2 libxrandr2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
    libxdamage1 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 \
    libgtk-3-0 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Stelle sicher, dass Playwright-Browser korrekt installiert sind
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright \
    && playwright install --with-deps chromium

# Setze die Umgebungsvariable für Playwright (verhindert Probleme mit /root)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright

# Stelle sicher, dass `start.sh` ausführbar ist
RUN chmod +x start.sh

# Starte die App
CMD ["./start.sh"]
