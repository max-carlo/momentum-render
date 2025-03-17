from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = Options()
    options.add_argument("--headless")  # Starte Chrome im Headless-Modus
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = "/usr/bin/google-chrome"
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def get_earnings_data():
    driver = setup_driver()
    driver.get("https://finance.yahoo.com")
    print("Seite geladen:", driver.title)
    driver.quit()

if __name__ == "__main__":
    get_earnings_data()
