import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf
import re
from datetime import datetime

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#epsdate", timeout=60000)
            earnings_date = page.inner_text("#epsdate")
            earnings_surprise = page.inner_text("#earnings .surprise")
            earnings_growth = page.inner_text("#earnings .growth")
            revenue_growth = page.inner_text("#revenue .growth")
            revenue_surprise = page.inner_text("#revenue .surprise")
        except Exception as e:
            return f"Fehler beim Laden der Earnings-Seite: {e}"
        browser.close()

    # **Formatierungen**
    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")  # **Neues Format mit Uhrzeit**
    except:
        formatted_date = "N/A"

    def clean(text):
        return re.sub(r"[^\d\.\-%]", "", text).replace(",", "") if text else "N/A"

    def signed(text):
        return f"-{clean(text)}" if "-" in text else clean(text)

    eg = clean(earnings_growth)
    rg = clean(revenue_growth)
    es = signed(earnings_surprise)
    rs = signed(revenue_surprise)

    # **Short Ratio**
    try:
        sr = yf.Ticker(ticker).info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (int, float)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg}% / RG: {rg}%\nES: {es}% / RS: {rs}%\nSR: {sr}"

def get_earnings_history(ticker):
    url = f"https://seekingalpha.com/symbol/{ticker}/earnings"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("table[data-test-id='table']", timeout=60000)
            rows = page.query_selector_all("table[data-test-id='table'] tbody tr")

            earnings_data = []
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 6:
                    period = cols[0].inner_text()
                    eps = cols[1].inner_text()
                    eps_beat_miss = cols[2].inner_text()
                    revenue = cols[3].inner_text()
                    yoy_growth = cols[4].inner_text()
                    revenue_beat_miss = cols[5].inner_text()
                    earnings_data.append(f"{period}: EPS {eps} ({eps_beat_miss}), Revenue {revenue} ({yoy_growth} YoY), Rev Surprise {revenue_beat_miss}")

        except Exception as e:
            return [f"Fehler beim Laden der Earnings-History: {e}"]

        browser.close()
    return earnings_data

# **🧼 Schlichtes Interface**
st.title("Hanabi Scraper")

with st.form(key="ticker_form"):
    ticker = st.text_input("Ticker eingeben:")
    submitted = st.form_submit_button("Fetch Data")

if submitted and ticker:
    result = get_earnings_data(ticker.strip().upper())
    st.text_area("Earnings Summary", result, height=180)

    history = get_earnings_history(ticker.strip().upper())
    st.write("### Earnings History (Seeking Alpha)")
    for entry in history:
        st.write(entry)
