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
st.markdown(f"<div style='position:fixed; right:30px; top:20px; font-size:40px; z-index:100'>{ampel}</div>", unsafe_allow_html=True)

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

# Finviz News
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

# EarningsWhispers
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

    return {
        "Earnings Growth": f"{clean(earnings_growth)}%",
        "Earnings Surprise": signed(earnings_surprise),
        "Revenue Growth": f"{clean(revenue_growth)}%",
        "Revenue Surprise": signed(revenue_surprise),
        "Short Ratio": "N/A"
    }

# Finhub EPS – alle Quartale

def get_finhub_data(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return pd.DataFrame([{"Hinweis": "Fehler beim Laden von Finhub"}])
    data = res.json()
    if not data:
        return pd.DataFrame([{"Hinweis": "Keine Finhub-Daten verfügbar"}])

    df = pd.DataFrame(data)
    df = df.sort_values("period", ascending=False)  # neuestes Quartal zuerst
    df["EPS Actual"] = pd.to_numeric(df["actual"], errors="coerce")
    df["EPS Change %"] = df["EPS Actual"].pct_change(-1).round(2) * 100
    df.rename(columns={"period": "Quarter"}, inplace=True)
    return df[["Quarter", "EPS Actual", "EPS Change %"]]

# Anzeige
if submitted and ticker:
    ticker = ticker.strip().upper()
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"

    col1, col2 = st.columns(2)

    with col1:
        st.header("News")
        finviz_news = scrape_finviz_news(ticker)
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
        for item in finviz_news:
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                news_html += f"<div class='finviz-item'><strong>{time}</strong> — <a href='{url}' target='_blank'>{title}</a> ({src})</div>"
        news_html += "</div>"
        html(news_html, height=250)

    with col2:
        st.header("Last Earnings")
        ew_data = get_earnings_data(ticker)
        if isinstance(ew_data, str):
            st.error(ew_data)
        else:
            st.markdown("""
            <style>
            .earnings-box {
                height: 225px;
                overflow-y: auto;
                white-space: pre-wrap;
                margin: 0;
                padding: 0;
                display: block;
            }
            </style>
            <div class='earnings-box'>
            """, unsafe_allow_html=True)
            st.markdown("<pre>" + "\n".join([f"{key}: {value}" for key, value in ew_data.items()]) + "</pre>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.header("Historische Earnings")
    finhub_df = get_finhub_data(ticker, api_key)
    if not finhub_df.empty and "EPS Actual" in finhub_df.columns:
        col3, col4 = st.columns([1, 1])
        with col3:
            st.dataframe(finhub_df)
        with col4:
            st.subheader("EPS Veränderung % (Quartal über Quartal)")
            fig, ax = plt.subplots(figsize=(4, 2.5))
            ax.plot(finhub_df["Quarter"], finhub_df["EPS Change %"], marker="o")
            ax.set_ylabel("Change %")
            ax.set_xlabel("Quarter")
            ax.set_title("EPS Change")
            ax.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(fig)
    else:
        st.warning("Keine Finhub-Daten gefunden oder nicht genügend Daten für Change %.")
