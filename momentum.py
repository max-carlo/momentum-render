import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf
import re
from datetime import datetime

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_selector("#epssummary", timeout=90000)

            earnings_summary = page.inner_text("#epssummary")

            # Extrahiere das Datum
            match = re.search(r"([A-Za-z]+), ([A-Za-z]+) (\d+), (\d{4})", earnings_summary)
            formatted_date = (
                datetime.strptime(f"{match.group(3)} {match.group(2)} {match.group(4)}", "%d %B %Y").strftime("%d/%m/%y")
                if match else "N/A"
            )

            # Extrahiere Earnings Growth, Revenue Growth und Earnings Surprise
            earnings_growth = re.search(r"Earnings Growth: ([\d,]+\.?\d*)%", earnings_summary)
            earnings_growth = earnings_growth.group(1) + "%" if earnings_growth else "N/A"

            revenue_growth = re.search(r"Revenue Growth: ([\d,]+\.?\d*)%", earnings_summary)
            revenue_growth = revenue_growth.group(1) + "%" if revenue_growth else "N/A"

            earnings_surprise = re.search(r"Earnings Surprise: ([\d,]+\.?\d*)%", earnings_summary)
            earnings_surprise = earnings_surprise.group(1) + "%" if earnings_surprise else "N/A"

        except Exception as e:
            formatted_date = "N/A"
            earnings_growth = revenue_growth = earnings_surprise = f"Error: {e}"

        browser.close()

    # Short Ratio von Yahoo Finance abrufen
    try:
        stock = yf.Ticker(ticker)
        short_ratio = stock.info.get("shortRatio", "N/A")
    except Exception as e:
        short_ratio = f"Error: {e}"

    # Formatierten String zurückgeben
    return f"{formatted_date}\nEG: {earnings_growth} / RG: {revenue_growth}\nES: {earnings_surprise}\nSR: {short_ratio}"

# Streamlit UI
st.title("Earnings Whispers Scraper")
ticker = st.text_input("Enter stock ticker:", "AAPL")
if st.button("Fetch Data"):
    data = get_earnings_data(ticker)
    st.text(data)  # Gibt die Daten als formatierten Text aus
