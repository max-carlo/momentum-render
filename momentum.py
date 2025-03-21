import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf
import re
from datetime import datetime

# Earnings Whispers Scraper
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=90000)

            # Warte auf die Earnings-Box
            page.wait_for_selector("#epssummary", timeout=90000)

            raw_date = page.inner_text("#epsdate").strip()
            earnings_growth = page.inner_text("#earnings .growth").strip()
            revenue_growth = page.inner_text("#revenue .growth").strip()
            earnings_surprise = page.inner_text("#earnings .surprise").strip()
            revenue_surprise = page.inner_text("#revenue .surprise").strip()

        except Exception as e:
            raw_date, earnings_growth, revenue_growth, earnings_surprise, revenue_surprise = ["N/A"] * 5

        browser.close()

    # Daten formatieren
    parsed_date = parse_date_to_ddmmyy(raw_date)

    return parsed_date, earnings_growth, revenue_growth, earnings_surprise, revenue_surprise

# Seeking Alpha Earnings-History Scraper
def get_earnings_history(ticker):
    url = f"https://seekingalpha.com/symbol/{ticker}/earnings"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=90000)

        try:
            page.wait_for_selector("table[data-test-id='table']", timeout=90000)

            rows = page.query_selector_all("table[data-test-id='table'] tbody tr")
            if not rows:
                raise Exception("Keine Tabellenzeilen gefunden!")

            earnings_data = []
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) < 6:
                    continue

                period = row.query_selector("th").inner_text().strip()
                eps = cols[0].inner_text().strip()
                eps_beat_miss = cols[1].inner_text().strip()
                revenue = cols[2].inner_text().strip()
                yoy_growth = cols[3].inner_text().strip()
                revenue_beat_miss = cols[4].inner_text().strip()

                earnings_data.append(f"{period}: EPS {eps} ({eps_beat_miss}), Revenue {revenue} ({revenue_beat_miss}), YoY: {yoy_growth}")

            browser.close()
            return "\n".join(earnings_data) if earnings_data else "⚠️ Keine Earnings-Daten gefunden."

        except Exception as e:
            browser.close()
            return f"❌ Fehler beim Laden der Earnings-History: {e}"

# Short Ratio abrufen
def get_short_ratio(ticker):
    try:
        stock = yf.Ticker(ticker)
        sr = stock.info.get("shortRatio", "N/A")
        return str(sr)
    except:
        return "N/A"

# Datumsformatierung
def parse_date_to_ddmmyy(date_str):
    if date_str == "N/A":
        return date_str

    cleaned = date_str.replace(" at ", " ").replace(" ET", "")
    if ", " in cleaned:
        parts = cleaned.split(", ", maxsplit=1)
        if len(parts) == 2:
            cleaned = parts[1]

    try:
        dt = datetime.strptime(cleaned, "%B %d, %Y %I:%M %p")
        return dt.strftime("%d/%m/%y %I:%M %p")
    except:
        return date_str

# Streamlit App UI
st.title("Hanabi Scraper")

# Text Input (Enter sendet automatisch die Anfrage)
ticker = st.text_input("Enter stock ticker:", "", key="ticker_input")

# Automatische Suche beim Drücken von Enter
if ticker:
    date, eg, rg, es, rs = get_earnings_data(ticker)
    sr = get_short_ratio(ticker)
    history = get_earnings_history(ticker)

    # Ergebnisse anzeigen
    st.text_area(
        "Earnings Data",
        f"{date}\nEG: {eg} / RG: {rg}\nES: {es} / RS: {rs}\nSR: {sr}",
        height=120
    )

    st.text_area("Earnings History", history, height=180)
