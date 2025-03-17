from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os

def get_earnings_data(ticker):
    options = Options()
    options.add_argument("--headless")  # Führe Chrome im Headless-Modus aus
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Setze den Chrome-Binärpfad aus der Umgebungsvariable
    chrome_path = os.getenv("CHROME_BIN", "/usr/bin/google-chrome")
    print(f"Verwende Chrome unter: {chrome_path}")
    options.binary_location = chrome_path

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://example.com/earnings?ticker={ticker}"
    driver.get(url)

    data = driver.page_source  # Beispiel: HTML-Quellcode als Ergebnis
    driver.quit()
    return data

if __name__ == "__main__":
    ticker = "AAPL"
    print(get_earnings_data(ticker))
