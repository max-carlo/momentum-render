FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Chromium + alle System-Dependencies die Playwright braucht
RUN playwright install --with-deps chromium

COPY . /app

EXPOSE 10000

CMD ["streamlit", "run", "momentum.py", "--server.port=10000", "--server.address=0.0.0.0"]
