# Nutze ein schlankes Python-Image
FROM python:3.11-slim

# Installiere Systempakete
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    libnss3 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    fonts-liberation \
    xdg-utils \
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Setze das Arbeitsverzeichnis
WORKDIR /app

# Kopiere alle Dateien ins Container-Verzeichnis
COPY . /app

# Installiere Python-Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Installiere Playwright und seine Browser
RUN playwright install

# Exponiere den richtigen Port
EXPOSE 10000

# Starte die Streamlit-App
CMD ["streamlit", "run", "momentum.py", "--server.port=10000", "--server.address=0.0.0.0"]
