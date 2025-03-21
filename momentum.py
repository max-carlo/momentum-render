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
        except Exception as e:
            return f"Fehler beim Laden der Earnings-Seite: {e}"
        browser.close()

    # Formatierungen
    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y")
    except:
        formatted_date = "N/A"

    def clean(text):
        return re.sub(r"[^\d\.\-%]", "", text).replace(",", "") if text else "N/A"

    def signed(text):
        return f"-{clean(text)}" if "-" in text else clean(text)

    eg = clean(earnings_growth)
    rg = clean(revenue_growth)
    es = signed(earnings_surprise)

    # Short Ratio
    try:
        sr = yf.Ticker(ticker).info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (int, float)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg}% / RG: {rg}%\nES: {es}%\nSR: {sr}"

# 🧼 Schlichtes Interface
st.title("Hanabi Scraper")

with st.form(key="ticker_form"):
    ticker = st.text_input("Ticker eingeben:")
    submitted = st.form_submit_button("Fetch Data")

if submitted and ticker:
    result = get_earnings_data(ticker.strip().upper())
    st.text_area("Ergebnis", result, height=180)
