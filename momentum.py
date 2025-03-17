from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

# Setze Chrome-Optionen
chrome_options = Options()
chrome_options.add_argument("--headless")  # Headless-Modus für Server
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Starte den Webdriver
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

# Beispiel-Navigation
driver.get("https://www.google.com")
time.sleep(2)  # Warte kurz
print(driver.title)

# Schließe den Browser
driver.quit()
