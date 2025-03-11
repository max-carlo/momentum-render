import re
from datetime import datetime
import streamlit as st
import yfinance as yf
from playwright.sync_api import sync_playwright

# Hilfsfunktionen
def remove_label_phrases(text):
    if text == "Nicht gefunden":
        return text

    patterns = [r"Earnings Growth", r"Revenue Growth", r"Earnings Surprise"]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.I)

    return text.strip()

def remove_commas(value):
    return value.replace(",", "") if value != "Nicht gefunden" else value


def parse_date_ddmmyy(date_str):
    if date_str := re.search(r"\w+, (.+ ET)", date_str):
        date_str = date_str.group(1)

    try:
        dt = datetime.strptime(date_str, "%B %d, %Y at %I:%M %p ET")
        return dt.strftime("%d/%m/%y")
    except:
        return "Nicht gefunden"

@st.cache_data(show_spinner="Lade Earnings-Daten von Earnings Whispers...")
def get_earnings_data(ticker):
    from playwright.sync_api import sync_playwright

    with webdriver_context() as browser:
        page = browser.new_page()
        url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
        page.goto(url)

        earnings_data = {
            "earnings_date": "Nicht gefunden",
            "earnings_surprise": "Nicht gefunden",
            "earnings_growth": "Nicht gefunden",
            "revenue_surprise": "Nicht gefunden",
            "revenue_growth": "Nicht gefunden",
        }

        try:
            earnings_data["earnings_date"] = page.text_content("#epsdetails #epsdate", timeout=8000).strip()
        except:
            pass

        selectors = {
            "earnings_surprise": "#earnings .surprise",
            "earnings_growth": "#earnings .growth",
            "revenue_surprise": "#revenue .surprise",
            "revenue_growth": "#revenue .growth"
        }

        for key, sel in selectors.items():
            try:
                earnings_data[key] = page.text_content(sel, timeout=5000).strip()
            except:
                pass

    return earnings_data


def webdriver_context():
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    return browser


def webdriver_close(browser):
    browser.close()


# YFinance Short Ratio
def get_short_ratio(ticker):
    ticker_info = yf.Ticker(ticker).info
    return ticker_info.get("shortRatio", "Nicht gefunden")


# Streamlit App
st.title("📈 Momentum Earnings App")

ticker = st.text_input("Bitte gib den Ticker ein (z.B. MARA):").strip().upper()

if ticker:
    with st.spinner("Daten werden geladen..."):
        earnings_data = get_earnings_data(ticker)

        date_clean = parse_date_to_ddmmyy(earnings_data["earnings_date"])

        eg_clean = remove_label_phrases(remove_commas(earnings_data["earnings_growth"]))
        rg_clean = remove_label_phrases(remove_commas(earnings_data["revenue_growth"]))
        es_clean = remove_label_phrases(remove_commas(earnings_data["earnings_surprise"]))

        short_ratio = get_short_ratio(ticker)

        st.markdown(f"### 📅 Datum: {date_clean}")
        st.markdown(f"**📊 Earnings Growth:** {eg_clean}")
        st.markdown(f"**Revenue Growth:** {rg_clean}")
        st.markdown(f"**Earnings Surprise:** {es_clean}")
        st.markdown(f"**Short Ratio:** {short_ratio}")


# Hilfsfunktionen für Playwright-Kontext (wichtig für Render)
from contextlib import contextmanager

@contextmanager
def get_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            yield browser
        finally:
            browser.close()


@contextmanager
def webdriver_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
