import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import yfinance as yf
import requests
import re
import pandas as pd
import matplotlib.pyplot as plt
from playwright.sync_api import sync_playwright

# 📌 Konfiguration
st.set_page_config(layout="wide")
st.title("📈 Aktienanalyse")

# 📌 Form
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

    return news_items

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

    return (
        f"Next Earnings Date: {formatted_date}\n"
        f"Earnings Growth: {eg}%\n"
        f"Revenue Growth: {rg}%\n"
        f"Earnings Surprise: {es}\n"
        f"Revenue Surprise: {rs}\n"
        f"Short Ratio: {sr}"
    )

# 📌 Finhub Earnings Data
def get_finhub_data(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        return pd.DataFrame([["Fehler beim Laden von Finhub: {e}"]], columns=["Error"])

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["period"])
    df = df.sort_values("date", ascending=False).head(8).sort_values("date")

    def compute_change(series):
        return series.pct_change(periods=4) * 100

    df["EPS Change %"] = compute_change(df["actual"])
    df["Revenue Change %"] = compute_change(df["revenue"])
    return df[["period", "actual", "EPS Change %", "revenue", "Revenue Change %"]]

# 📌 Datenanzeige
if submitted and ticker:
    ticker = ticker.strip().upper()
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"

    col1, col2 = st.columns(2)

    with col1:
        st.header("📰 Finviz News")
        finviz_news = scrape_finviz_news(ticker)
        with st.container():
            with st.expander("News anzeigen", expanded=True):
                st.markdown(
                    "<div style='height:300px; overflow-y:scroll'>",
                    unsafe_allow_html=True,
                )
                for item in finviz_news:
                    if isinstance(item, str):
                        st.error(item)
                    else:
                        time, title, url, src = item
                        st.markdown(f"**{time}** — [{title}]({url}) ({src})")
                st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.header("📊 Earnings Whispers")
        earnings_info = get_earnings_data(ticker)
        st.text(earnings_info)

    st.header("📈 Finhub Earnings-Daten (letzte 8 Quartale)")
    finhub_df = get_finhub_data(ticker, api_key)
    st.dataframe(finhub_df, use_container_width=True)

    st.subheader("📉 Change %: EPS YoY")
    fig, ax = plt.subplots()
    ax.plot(finhub_df["period"], finhub_df["EPS Change %"], marker="o")
    ax.set_title("EPS Change % (YoY)")
    ax.set_ylabel("%")
    ax.set_xlabel("Quarter")
    ax.grid(True)
    st.pyplot(fig)

    st.subheader("📉 Change %: Revenue YoY")
    fig2, ax2 = plt.subplots()
    ax2.plot(finhub_df["period"], finhub_df["Revenue Change %"], marker="o", linestyle="--")
    ax2.set_title("Revenue Change % (YoY)")
    ax2.set_ylabel("%")
    ax2.set_xlabel("Quarter")
    ax2.grid(True)
    st.pyplot(fig2)

    st.markdown(f"🔗 [Zur SeekingAlpha Earnings-Seite](https://seekingalpha.com/symbol/{ticker}/earnings)", unsafe_allow_html=True)
