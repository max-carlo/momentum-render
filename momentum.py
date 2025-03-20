import streamlit as st
from playwright.sync_api import sync_playwright

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Setze auf False, um das Verhalten zu sehen
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)  # Warte auf das Laden
            page.wait_for_selector("#epssummary", timeout=90000)  # Warte auf das Element
            
            earnings_summary = page.inner_text("#epssummary")  # Extrahiere die Inhalte
        except Exception as e:
            earnings_summary = f"Error: {e}"

        browser.close()

    return earnings_summary

st.title("Earnings Whispers Scraper")
ticker = st.text_input("Enter stock ticker:", "AAPL")
if st.button("Fetch Data"):
    data = get_earnings_data(ticker)
    st.text_area("Earnings Data", data)
