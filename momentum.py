import streamlit as st
import yfinance as yf
from playwright.sync_api import sync_playwright
import re
from datetime import datetime

def format_date(raw_date):
    """ Wandelt das Datum in das Format dd/mm/yy um. """
    try:
        dt = datetime.strptime(raw_date, "%A, %B %d, %Y at %I:%M %p ET")
        return dt.strftime("%d/%m/%y")
    except:
        return "N/A"

def clean_value(value):
    """ Entfernt Label und Kommas (z.B. '6,300.0%' → '6300.0%'). """
    if not value:
        return "N/A"
    return re.sub(r"[^0-9.\-%]", "", value).replace(",", "")

def get_short_ratio(ticker):
    """ Ruft das Short Ratio aus yfinance ab. """
    try:
        stock = yf.Ticker(ticker)
        sr = stock.info.get("shortRatio", None)
        return str(round(sr, 2)) if sr else "N/A"
    except:
        return "N/A"

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

            # Warten auf die benötigten Elemente
            page.wait_for_selector("#epsdate", timeout=90000)
            page.wait_for_selector("#earnings .surprise", timeout=90000)
            page.wait_for_selector("#earnings .growth", timeout=90000)
            page.wait_for_selector("#revenue .growth", timeout=90000)

            # Extrahiere die Daten
            raw_date = page.inner_text("#epsdate").strip()
            earnings_growth = page.inner_text("#earnings .growth").strip()
            revenue_growth = page.inner_text("#revenue .growth").strip()
            earnings_surprise = page.inner_text("#earnings .surprise").strip()

            # Daten bereinigen
            date_formatted = format_date(raw_date)
            earnings_growth_clean = clean_value(earnings_growth)
            revenue_growth_clean = clean_value(revenue_growth)
            earnings_surprise_clean = clean_value(earnings_surprise)

        except Exception as e:
            return f"Fehler beim Abrufen der Daten: {e}"

        finally:
            browser.close()

    # Short Ratio abrufen
    short_ratio = get_short_ratio(ticker)

    return f"{date_formatted}\nEG: {earnings_growth_clean} / RG: {revenue_growth_clean}\nES: {earnings_surprise_clean}\nSR: {short_ratio}"

# ---- Streamlit UI ----
st.set_page_config(page_title="Hanabi Scraper", layout="wide", initial_sidebar_state="collapsed")

# CSS für schwarzes Design
st.markdown(
    """
    <style>
        body {
            background-color: black;
            color: white;
        }
        .stTextInput, .stButton {
            border-radius: 8px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Hanabi Scraper")
ticker = st.text_input("Enter stock ticker:")

if st.button("Fetch Data") and ticker:
    data = get_earnings_data(ticker)
    st.text_area("Earnings Data", data)
