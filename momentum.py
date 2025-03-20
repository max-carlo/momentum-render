import streamlit as st
from playwright.sync_api import sync_playwright

# Funktion zum Scrapen von Earnings Whispers
def get_earnings_data(ticker):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # URL von Earnings Whispers für das eingegebene Ticker-Symbol
        url = f"https://www.earningswhispers.com/stocks/{ticker}"
        page.goto(url, timeout=60000)  # Timeout auf 60 Sekunden setzen, um Ladeprobleme zu vermeiden

        # Warte auf das Laden der relevanten Elemente
        page.wait_for_selector("div.earningswhispers-score-container", timeout=30000)

        # Extrahiere die wichtigsten Earnings-Daten
        try:
            whisper_number = page.inner_text("div#whisper")
            estimate = page.inner_text("div#estimate")
            actual = page.inner_text("div#actual")
            earnings_date = page.inner_text("div#earningsdate")

            earnings_data = {
                "Whisper Number": whisper_number,
                "Analyst Estimate": estimate,
                "Actual Earnings": actual,
                "Earnings Date": earnings_date
            }
        except Exception as e:
            earnings_data = {"Error": f"Fehler beim Scrapen: {e}"}

        browser.close()
        return earnings_data

# Streamlit UI
st.title("Earnings Whispers Scraper")
ticker = st.text_input("Enter stock ticker:", "AAPL")

if st.button("Fetch Data"):
    data = get_earnings_data(ticker)
    st.write(data)
