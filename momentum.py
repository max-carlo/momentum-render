import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf

# Funktion für Playwright-Scraping
def get_earnings_data(ticker):
    url = f"https://finance.yahoo.com/quote/{ticker}/earnings"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)  # Erhöhte Timeout-Zeit
            data = page.content()  # Holt den HTML-Quellcode
        except Exception as e:
            data = f"Error: {e}"
        
        browser.close()
    
    return data[:1000]  # Beschränkung für Ausgabe

# Funktion für Short Ratio von yfinance
def get_short_ratio(ticker):
    try:
        stock = yf.Ticker(ticker)
        short_ratio = stock.info.get("shortRatio", "N/A")
        return short_ratio
    except Exception as e:
        return f"Error: {e}"

# Streamlit UI
st.title("Earnings Whispers Scraper")

ticker = st.text_input("Enter stock ticker:", "AAPL")

if st.button("Fetch Data"):
    earnings_data = get_earnings_data(ticker)
    short_ratio = get_short_ratio(ticker)

    st.text_area("Earnings Data", earnings_data)
    st.write(f"Short Ratio: {short_ratio}")
