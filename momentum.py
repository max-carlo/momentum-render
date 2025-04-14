import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import yfinance as yf
import re
import requests
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")
st.title("Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

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

# EarningsWhispers
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
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
            return f"Fehler beim Laden: {e}"
        browser.close()

    def clean(t): return re.sub(r"[^\d\.\-%]", "", t).replace(",", "") if t else "N/A"
    def signed(t): return f"-{clean(t)}" if "-" in t else clean(t)

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")
    except:
        formatted_date = "N/A"

    try:
        info = yf.Ticker(ticker).info
        sr = str(round(info.get("shortRatio", "N/A"), 2)) if isinstance(info.get("shortRatio"), (int, float)) else "N/A"
    except:
        sr = "N/A"

    return (
        f"Earnings Date: {formatted_date}\n"
        f"Earnings Growth: {clean(earnings_growth)}%\n"
        f"Revenue Growth: {clean(revenue_growth)}%\n"
        f"Earnings Surprise: {signed(earnings_surprise)}\n"
        f"Revenue Surprise: {signed(revenue_surprise)}\n"
        f"Short Ratio: {sr}"
    )

# Finhub Earnings
def get_finhub_data(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return pd.DataFrame([["Fehler beim Laden von Finhub"]], columns=["Fehler"])
    data = res.json()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame([["Keine Finhub-Daten verf\xfcgbar"]], columns=["Hinweis"])
    df = df.head(12).copy()
    df["actual"] = pd.to_numeric(df["actual"], errors="coerce")
    df = df.sort_values("period")
    df["Change %"] = df["actual"].pct_change(periods=4) * 100
    df["Change %"] = df["Change %"].round(2)
    df["Period"] = df["period"].str.replace("-", "/")
    df = df[["Period", "actual", "Change %"]]
    df.rename(columns={"actual": "Reported EPS"}, inplace=True)
    return df

# Anzeige
if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.header("News")
        news_items = scrape_finviz_news(ticker)

        st.markdown("""
        <style>
        .finviz-item:nth-child(even) {
            background-color: rgba(200, 200, 200, 0.1);
        }
        .finviz-scroll {
            height: 225px;
            overflow-y: auto;
            padding-top: 0;
            margin-top: 0;
        }
        </style>
        <div class="finviz-scroll">
        """, unsafe_allow_html=True)

        for idx, item in enumerate(news_items):
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                st.markdown(f"<div class='finviz-item'><strong>{time}</strong> — <a href='{url}' target='_blank'>{title}</a> ({src})</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.header("Last Earnings")
        st.markdown("<div style='height: 225px; overflow-y: auto; white-space: pre-wrap;'>", unsafe_allow_html=True)
        st.text(get_earnings_data(ticker))
        st.markdown("</div>", unsafe_allow_html=True)

    st.header("Historische Earnings")
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"
    finhub_df = get_finhub_data(ticker, api_key)
    if not finhub_df.empty and "Reported EPS" in finhub_df.columns:
        st.dataframe(finhub_df)

        st.subheader("EPS Ver\xe4nderung (YoY %)")
        fig, ax = plt.subplots()
        ax.plot(finhub_df["Period"], finhub_df["Change %"], marker="o")
        ax.set_ylabel("Change %")
        ax.set_xlabel("Period")
        ax.set_title("Year-over-Year Ver\xe4nderung von Reported EPS")
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.warning("Keine Finhub-Daten gefunden.")
