import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import yfinance as yf
import re
import requests
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt
from streamlit.components.v1 import html

st.set_page_config(layout="wide")

# Ampel: Trendanzeige für QQQ EMA9 vs EMA21
qqq = yf.download("QQQ", period="3mo", interval="1d")
qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
ampel = "🔴"
if (
    qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
    and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
    and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
):
    ampel = "🟢"

st.markdown("""
<style>
.ampel-box {
    font-size: 80px;
    line-height: 1;
    text-align: right;
    padding-right: 20px;
}
h1, .block-title, .matplot-title, .stHeader, .stMarkdown h2, .stMarkdown h3 {
    font-size: 1.5rem !important;
    font-weight: 600;
}
.finviz-scroll, .earnings-box {
    font-size: 0.875rem;
    font-family: sans-serif;
    line-height: 1.4;
}
</style>
""", unsafe_allow_html=True)

col_input, col_ampel = st.columns([4, 1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_ampel:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)

# Finviz News

def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    headers = {"User-Agent": "Mozilla/5.0"}
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
            news_items.append((time_cell.text.strip(), link_tag.text.strip(), link_tag["href"], source.text.strip("()")))
    return news_items

# EarningsWhispers Daten

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#epsdate", timeout=60000)
            earnings_surprise = page.inner_text("#earnings .surprise")
            earnings_growth = page.inner_text("#earnings .growth")
            revenue_growth = page.inner_text("#revenue .growth")
            revenue_surprise = page.inner_text("#revenue .surprise")
        except Exception as e:
            return f"Fehler beim Laden: {e}"
        browser.close()

    def clean(t): return re.sub(r"[^\d\.-]", "", t)

    try:
        info = yf.Ticker(ticker).info
        sr = str(round(info.get("shortRatio", "N/A"), 2)) if isinstance(info.get("shortRatio"), (int, float)) else "N/A"
    except:
        sr = "N/A"

    return {
        "Earnings Growth": f"{clean(earnings_growth)}%",
        "Earnings Surprise": clean(earnings_surprise),
        "Revenue Growth": f"{clean(revenue_growth)}%",
        "Revenue Surprise": clean(revenue_surprise),
        "Short Ratio": sr
    }

# Finhub YoY EPS Change mit Vergleich zum Vorjahresquartal

def get_finhub_data_yoy(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&limit=12&token={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return pd.DataFrame([{"Hinweis": "Fehler beim Laden von Finhub"}])
    data = res.json()
    if not data:
        return pd.DataFrame([{"Hinweis": "Keine Finhub-Daten verfügbar"}])

    df = pd.DataFrame(data)
    df = df.sort_values("period", ascending=False).copy()
    df["EPS Actual"] = pd.to_numeric(df["actual"], errors="coerce")
    df["period"] = pd.to_datetime(df["period"])
    df["year"] = df["period"].dt.year
    df["quarter"] = df["period"].dt.quarter

    df_yoy = df.copy()
    df_yoy.set_index(["quarter", "year"], inplace=True)

    changes = []
    for idx, row in df.iterrows():
        q, y = row["quarter"], row["year"]
        try:
            prev_eps = df_yoy.loc[(q, y - 1), "EPS Actual"]
            if pd.notnull(prev_eps) and prev_eps != 0:
                change = ((row["EPS Actual"] - prev_eps) / abs(prev_eps)) * 100
            else:
                change = None
        except KeyError:
            change = None
        changes.append(change)

    df["YoY Change %"] = changes
    df["Quarter"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)
    return df[["Quarter", "EPS Actual", "YoY Change %"]]

if submitted and ticker:
    ticker = ticker.strip().upper()
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"

    col1, col2 = st.columns(2)

    with col1:
        st.header("News")
        news_items = scrape_finviz_news(ticker)
        news_html = """<div class='finviz-scroll'>"""
        for item in news_items:
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                news_html += f"<div><strong>{time}</strong> — <a href='{url}' target='_blank'>{title}</a> ({src})</div>"
        news_html += "</div>"
        html(news_html, height=250)

    with col2:
        st.header("Last Earnings")
        data = get_earnings_data(ticker)
        if isinstance(data, str):
            st.error(data)
        else:
            html_block = """<div class='earnings-box'>"""
            for key, value in data.items():
                html_block += f"<div><strong>{key}</strong>: {value}</div>"
            html_block += "</div>"
            st.markdown(html_block, unsafe_allow_html=True)

    st.header("Historische Earnings")
    col3, col4 = st.columns([1, 1])
    df_eps = get_finhub_data_yoy(ticker, api_key)
    with col3:
        st.dataframe(df_eps)
    with col4:
        st.subheader("EPS Veränderung % (YoY)")
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(df_eps["Quarter"], df_eps["YoY Change %"], marker="o")
        ax.set_ylabel("Change %", fontsize=8)
        ax.set_xlabel("Quarter", fontsize=8)
        ax.tick_params(labelsize=8)
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)
