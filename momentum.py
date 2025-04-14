import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import yfinance as yf
import re
import requests
from playwright.sync_api import sync_playwright
import pandas as pd

# 📌 Streamlit Setup
st.set_page_config(layout="wide")
st.title("📈 Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

# 📌 Finviz News
def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        )
    }
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except Exception as e:
        return [f"Fehler beim Laden der Finviz-Seite: {e}"]

    soup = BeautifulSoup(res.text, "html.parser")
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
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ))
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

# 📌 Finnhub EPS (letzte Quartale)
def get_finhub_earnings(ticker):
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
        if not data:
            return pd.DataFrame([["Keine Daten"]], columns=["Info"])
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["period"]).dt.strftime("%Y-%m-%d")
        return df[["date", "actual", "estimate"]].head(4).rename(columns={"actual": "Reported EPS", "estimate": "Estimate"})
    except Exception as e:
        return pd.DataFrame([[f"Fehler beim Laden der Finnhub-Daten: {e}"]], columns=["Info"])

# 📌 Datenanzeige
if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.header("📰 Finviz News")
        finviz_news = scrape_finviz_news(ticker)
        for item in finviz_news:
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                st.markdown(f"**{time}** — [{title}]({url}) ({src})")

    with col2:
        st.header("📊 EarningsWhispers")
        earnings_info = get_earnings_data(ticker)
        st.text(earnings_info)

    # 📌 Finnhub Earnings Table
    st.header("📈 Finnhub: Letzte 4 Quartale (EPS)")
    finhub_df = get_finhub_earnings(ticker)
    st.dataframe(finhub_df)

    # 📌 Seeking Alpha als Hinweis
    st.header("📷 SeekingAlpha (optional)")
    sa_url = f"https://seekingalpha.com/symbol/{ticker}/earnings"
    st.markdown(f"🔗 [Zur SeekingAlpha Earnings-Seite]({sa_url})", unsafe_allow_html=True)
