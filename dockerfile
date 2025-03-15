# 1️⃣ Basis-Image: Leichtgewichtige Python-Version mit Debian-Unterbau
FROM python:3.10-slim

# 2️⃣ Setze das Arbeitsverzeichnis
WORKDIR /app

# 3️⃣ Installiere systemweite Abhängigkeiten für Playwright
RUN apt-get update && apt-get install -y \
    curl unzip xvfb libnss3 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libgtk-3-0 libgbm-dev libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4️⃣ Kopiere den App-Code in den Container
COPY . /app

# 5️⃣ Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir --upgrade pip \
    && pip install -r requirements.txt

# 6️⃣ Installiere Playwright und den Chromium-Browser
RUN pip install playwright && playwright install --with-deps chromium

# 7️⃣ Setze die Umgebungsvariablen für Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# 8️⃣ Stelle sicher, dass `start.sh` ausführbar ist
RUN chmod +x start.sh

# 9️⃣ Starte die Anwendung mit `start.sh`
CMD ["./start.sh"]
