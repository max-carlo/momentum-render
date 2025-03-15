# Basis-Image mit Python 3.11
FROM python:3.11

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Installiere Systemabhängigkeiten für Selenium & Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libatspi2.0-0 \
    libgbm1 \
    xvfb \
    chromium \
    chromium-driver \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Kopiere die benötigten Dateien
COPY requirements.txt /app/

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Installiere Playwright-Browser (falls Playwright verwendet wird)
RUN playwright install && playwright install-deps

# Kopiere den restlichen Code ins Arbeitsverzeichnis
COPY . /app/

# Setze die Umgebungsvariable für Playwright-Browser
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Setze das Startkommando für Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
