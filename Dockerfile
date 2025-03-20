# Nutzt ein schlankes Python-Image
FROM python:3.11-slim

# Installiere Systempakete
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    xdg-utils \
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Installiere Playwright und Chromium
RUN pip install --no-cache-dir playwright && playwright install --with-deps chromium

# Setze das Arbeitsverzeichnis
WORKDIR /app
COPY . /app

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Setze Playwright-Umgebungsvariablen
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome

# Exponiere den richtigen Port
EXPOSE 10000

# Starte die Streamlit-App
CMD ["streamlit", "run", "momentum.py", "--server.port=10000", "--server.address=0.0.0.0"]
