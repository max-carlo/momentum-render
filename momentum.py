import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
from datetime import datetime

# 📌 Finviz News Scraper
def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
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

    return news_items[:15]  # Top 15 News

# 📌 Zacks Earnings Calendar Scraper
def scrape_zacks_earnings(ticker):
    url = f"https://www.zacks.com/stock/research/{ticker}/earnings-calendar"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("table#earnings_announcements_earnings_table", timeout=10000)  # NEU: Warten auf Tabelle
            html = page.content()
        except Exception as e:
            browser.close()
            return pd.DataFrame([["Fehler beim Laden der Zacks-Seite", "", "", "", "", "", ""]],
                                columns=["Date", "Period", "Estimate", "Reported", "Surprise", "% Surprise", "Time"])
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table#earnings_announcements_earnings_table tr.odd, table#earnings_announcements_earnings_table tr.even")

    if not rows:
        return pd.DataFrame([["Keine Datenzeilen gefunden", "", "", "", "", "", ""]],
                            columns=["Date", "Period", "Estimate", "Reported", "Surprise", "% Surprise", "Time"])

    data = []
    for row in rows[:8]:
        cells = row.find_all(["th", "td"])
        if len(cells) == 7:
            data.append([c.text.strip() for c in cells])

    df = pd.DataFrame(data, columns=["Date", "Period", "Estimate", "Reported", "Surprise", "% Surprise", "Time"])
    return df


# 📌 EarningsWhispers Current Earnings
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

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")
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

    try:
        sr = yf.Ticker(ticker).info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (int, float)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg} / RG: {rg}%\nES: {es} / RS: {rs}\nSR: {sr}"

# 📌 Streamlit Interface
st.set_page_config(layout="wide")
st.title("📈 Hanabi Market Scraper")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben (z. B. AAPL)", "")
    submitted = st.form_submit_button("Daten abrufen")

if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📰 Finviz News zu {ticker}")
        news = scrape_finviz_news(ticker)
        if isinstance(news, list):
            for time, title, url, source in news:
                st.markdown(f"- **{time}** – [{title}]({url}) ({source})")
        else:
            st.error(news)

    with col2:
        st.subheader(f"📅 Aktuelle Earnings zu {ticker} (EarningsWhispers)")
        result = get_earnings_data(ticker)
        st.text_area("Earnings Summary", result, height=180)

    st.subheader(f"📊 Zacks Earnings History für {ticker}")
    df = scrape_zacks_earnings(ticker)
    st.dataframe(df, use_container_width=True)
