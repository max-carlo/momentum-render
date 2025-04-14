import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
from datetime import datetime
import yfinance as yf
import os

# 📌 Screenshot von Seeking Alpha (EPS Surprise & Estimates)
def screenshot_seeking_alpha_eps_chart(ticker):
    url = f"https://seekingalpha.com/symbol/{ticker}/earnings"
    output_path = f"{ticker}_eps_chart.png"
    selector = '[data-test-id="surprise-and-estimates-bar-chart"]'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1200, "height": 800})
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(selector, timeout=30000)
            element = page.locator(selector)
            element.screenshot(path=output_path)
        except Exception as e:
            return f"Fehler beim Screenshot: {e}"
        browser.close()

    return output_path

# 📌 Finviz News
def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
        except Exception as e:
            browser.close()
            return [f"Fehler beim Laden der Finviz-Seite: {e}"]
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")

    news_items = []
    for row in rows:
        time_cell = row.find("td", width="130")
        link_tag = row.find("a", class_="tab-link-news")
        source = row.find("span")
        if time_cell and link_tag and source:
            time = time_cell.text.strip()
            title = link_tag.text.strip()
            url = link_tag["href"]
            src = source.text.strip("()")
            news_items.append((time, title, url, src))

    return news_items[:15]

# 📌 EarningsWhispers
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            earnings_date = page.inner_text("#epsdate")
            earnings_surprise = page.inner_text("#earnings .surprise")
            earnings_growth = page.inner_text("#earnings .growth")
            revenue_growth = page.inner_text("#revenue .growth")
            revenue_surprise = page.inner_text("#revenue .surprise")
        except Exception as e:
            browser.close()
            return f"Fehler beim Laden der Earnings-Seite: {e}"
        browser.close()

    def clean(text):
        return re.sub(r"[^\d\.\-%]", "", text).replace(",", "") if text else "N/A"

    def signed(text):
        return f"-{clean(text)}" if "-" in text else clean(text)

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")
    except:
        formatted_date = "N/A"

    eg = clean(earnings_growth).rstrip("%")
    rg = clean(revenue_growth).rstrip("%")
    es = signed(earnings_surprise)
    rs = signed(revenue_surprise)

    try:
        info = yf.Ticker(ticker).info
        sr = info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (float, int)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg}% / RG: {rg}%\nES: {es} / RS: {rs}\nSR: {sr}"

# 📌 Streamlit UI
st.set_page_config(layout="wide")
st.title("📊 Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben (z.B. AAPL)", "")
    submitted = st.form_submit_button("Daten abrufen")

if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.header("📰 Finviz News")
        news = scrape_finviz_news(ticker)
        for time, title, url, source in news:
            st.markdown(f"- [{time}] [{title}]({url}) ({source})")

    with col2:
        st.header("📅 EarningsWhispers")
        ew_data = get_earnings_data(ticker)
        st.text(ew_data)

    st.header("📸 SeekingAlpha EPS Chart")
    screenshot_path = screenshot_seeking_alpha_eps_chart(ticker)
    if os.path.exists(screenshot_path):
        st.image(screenshot_path, caption="EPS Surprise & Estimates by Quarter", use_column_width=True)
    else:
        st.warning("Screenshot konnte nicht geladen werden.")
