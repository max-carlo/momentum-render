import streamlit as st
from playwright.sync_api import sync_playwright
import time

def get_earnings_data(ticker):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"  # Fake User-Agent
        )
        page = context.new_page()

        # Neue URL für den Ticker
        url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
        page.goto(url, wait_until="networkidle", timeout=60000)  # Warte auf komplettes Laden

        # Warte explizit auf das Earnings-Element
        try:
            page.wait_for_selector("div.earningswhispers-container", timeout=60000)
        except:
            page.screenshot(path="debug_screenshot.png")  # Screenshot für Debugging
            browser.close()
            return {"Error": "Earnings-Daten konnten nicht geladen werden (evtl. Blockierung?)"}

        # Extrahiere Earnings-Daten
        try:
            whisper_number = page.inner_text("span#whisper")
            estimate = page.inner_text("span#estimate")
            actual = page.inner_text("span#actual")
            earnings_date = page.inner_text("span#earningsdate")

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
