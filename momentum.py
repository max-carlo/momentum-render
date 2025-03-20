import streamlit as st
from playwright.sync_api import sync_playwright

def get_earnings_data(ticker):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = f"https://finance.yahoo.com/quote/{ticker}/earnings"
        page.goto(url, wait_until="load")
        
        # Beispiel: Extrahiere den Seitentext (du kannst das anpassen)
        data = page.content()
        
        browser.close()
        return data

st.title("Earnings Whispers Scraper")
ticker = st.text_input("Enter stock ticker:", "AAPL")
if st.button("Fetch Data"):
    data = get_earnings_data(ticker)
    st.text_area("Earnings Data", data[:1000])  # Zeigt die ersten 1000 Zeichen
