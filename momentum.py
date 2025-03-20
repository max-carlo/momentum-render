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

            # Warte explizit auf die Earnings-Elemente (bis zu 90 Sekunden)
            page.wait_for_selector(".eps-datetime", timeout=90000)
            page.wait_for_selector(".earningswhispers-growth", timeout=90000)
            page.wait_for_selector(".earningswhispers-revenue-growth", timeout=90000)
            page.wait_for_selector(".earningswhispers-surprise", timeout=90000)

            # Datum extrahieren
            raw_date = page.inner_text(".eps-datetime").strip()
            match = re.search(r"([A-Za-z]+), ([A-Za-z]+) (\d+), (\d+)", raw_date)
            formatted_date = (
                datetime.strptime(f"{match.group(3)} {match.group(2)} {match.group(4)}", "%d %B %Y").strftime("%d/%m/%y")
                if match else "N/A"
            )

            # Earnings-Daten extrahieren
            earnings_growth = page.inner_text(".earningswhispers-growth").strip().replace(",", "")
            revenue_growth = page.inner_text(".earningswhispers-revenue-growth").strip().replace(",", "")
            earnings_surprise = page.inner_text(".earningswhispers-surprise").strip().replace(",", "")

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
