import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf
import re
from datetime import datetime

# --- Initialisiere Session State ---
if "fetch_data" not in st.session_state:
    st.session_state.fetch_data = False

# --- Funktion: Earnings Whispers Scraper ---
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_selector("#epssummary", timeout=90000)

        try:
            raw_date = page.inner_text("#epsdate").strip()
            earnings_growth = page.inner_text("#earnings .growth").strip()
            revenue_growth = page.inner_text("#revenue .growth").strip()
            earnings_surprise = page.inner_text("#earnings .surprise").strip()
            revenue_surprise = page.inner_text("#revenue .surprise").strip()
        except Exception:
            return "Fehler: Daten konnten nicht extrahiert werden."

        browser.close()

    formatted_date = parse_date_to_ddmmyy(raw_date)
    earnings_growth = clean_percentage(earnings_growth)
    revenue_growth = clean_percentage(revenue_growth)
    earnings_surprise = clean_percentage(earnings_surprise)
    revenue_surprise = clean_percentage(revenue_surprise)

    return f"{formatted_date}\nEG: {earnings_growth} / RG: {revenue_growth}\nES: {earnings_surprise} / RS: {revenue_surprise}"

# --- Funktion: Seeking Alpha Earnings History Scraper ---
def get_earnings_history(ticker):
    url = f"https://seekingalpha.com/symbol/{ticker}/earnings"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        try:
            page.wait_for_selector("table[data-test-id='table']", timeout=60000)
        except:
            return "Fehler: Earnings-History konnte nicht geladen werden."

        rows = page.query_selector_all("table[data-test-id='table'] tbody tr")

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

    return "\n".join(earnings_data) if earnings_data else "Keine Earnings-Daten gefunden."

# --- Funktion: YFinance Short Ratio ---
def get_short_ratio(ticker):
    t = yf.Ticker(ticker)
    info = t.info
    return str(info.get("shortRatio", "N/A"))

# --- Hilfsfunktionen ---
def parse_date_to_ddmmyy(date_str):
    if date_str == "N/A":
        return "N/A"

    cleaned = date_str.replace(" at ", " ").replace(" ET", "")
    if ", " in cleaned:
        parts = cleaned.split(", ", maxsplit=1)
        if len(parts) == 2:
            cleaned = parts[1]

    try:
        dt = datetime.strptime(cleaned, "%B %d, %Y %I:%M %p")
        return dt.strftime("%d/%m/%y %I:%M %p")
    except:
        return "N/A"

def clean_percentage(value):
    if value == "N/A":
        return "N/A"
    return value.replace(",", "").replace("Earnings Growth", "").replace("Revenue Growth", "").replace("Earnings Surprise", "").replace("Revenue Surprise", "").strip()

# --- Streamlit UI ---
st.set_page_config(page_title="Hanabi Scraper", layout="wide")
st.markdown("<style>body { background-color: black; color: white; }</style>", unsafe_allow_html=True)

st.title("Hanabi Scraper")

# --- Eingabefeld mit Enter-Taste auslösen ---
def submit():
    st.session_state.fetch_data = True

ticker = st.text_input("Enter stock ticker:", key="ticker", on_change=submit)

# --- Button zum Abrufen der Daten ---
if st.button("Fetch Data") or st.session_state.fetch_data:
    st.session_state.fetch_data = False  # Reset nach Abruf

    ew_data = get_earnings_data(ticker)
    short_ratio = get_short_ratio(ticker)
    earnings_history = get_earnings_history(ticker)

    st.text_area("Earnings Whispers Data", ew_data, height=100)
    st.text_area("Short Ratio", f"SR: {short_ratio}", height=80)
    st.text_area("Earnings History (Seeking Alpha)", earnings_history, height=250)
