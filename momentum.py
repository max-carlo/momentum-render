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
        return pd.DataFrame(["Fehler beim Laden von Finhub"], columns=["Fehler"])
    data = res.json()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(["Keine Finhub-Daten verf\u00fcgbar"], columns=["Hinweis"])
    df = df.sort_values("period")
    df["actual"] = pd.to_numeric(df["actual"], errors="coerce")
    df["prior_year"] = df["actual"].shift(4)
    df["Change %"] = ((df["actual"] - df["prior_year"]) / df["prior_year"]) * 100
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

        if isinstance(news_items, list) and all(isinstance(i, tuple) for i in news_items):
            news_html = """
            <style>
            .finviz-scroll {
                height: 225px;
                overflow-y: auto;
                font-size: 0.875rem;
            }
            .finviz-item {
                margin-bottom: 6px;
            }
            </style>
            <div class="finviz-scroll">
            """
            for time, title, url, src in news_items:
                news_html += f"<div class='finviz-item'><strong>{time}</strong> — <a href='{url}' target='_blank'>{title}</a> ({src})</div>"
            news_html += "</div>"
            html(news_html, height=250)
        else:
            for item in news_items:
                st.error(item)

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

        st.subheader("EPS Veränderung (YoY %)")
        fig, ax = plt.subplots()
        ax.plot(finhub_df["Period"], finhub_df["Change %"], marker="o")
        ax.set_ylabel("Change %")
        ax.set_xlabel("Period")
        ax.set_title("Year-over-Year Veränderung von Reported EPS")
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.warning("Keine Finhub-Daten gefunden.")
