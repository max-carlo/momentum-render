import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import requests
import matplotlib.pyplot as plt
import re
from playwright.sync_api import sync_playwright

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

    return {
        "Earnings Date": formatted_date,
        "Earnings Growth": f"{clean(earnings_growth)}%",
        "Revenue Growth": f"{clean(revenue_growth)}%",
        "Earnings Surprise": signed(earnings_surprise),
        "Revenue Surprise": signed(revenue_surprise),
    }

# 📌 Finhub EPS
def get_finhub_data(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return pd.DataFrame([["Fehler beim Abrufen der Finhub-Daten"]], columns=["Quarter", "EPS Actual", "EPS Change %"])

    data = res.json()
    if not data:
        return pd.DataFrame([["Keine Finhub-Daten verfügbar"]], columns=["Quarter", "EPS Actual", "EPS Change %"])

    df = pd.DataFrame(data)
    df = df.sort_values("period").tail(4)
    df["Quarter"] = df["period"]
    df["EPS Actual"] = df["actual"]

    def compute_change(series):
        return series.pct_change() * 100

    df["EPS Change %"] = compute_change(df["EPS Actual"]).round(2)
    return df[["Quarter", "EPS Actual", "EPS Change %"]]

# 📌 Hauptlogik
if submitted and ticker:
    ticker = ticker.strip().upper()
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"

    col1, col2 = st.columns(2)

    with col1:
        st.header("📰 Finviz News")
        finviz_news = scrape_finviz_news(ticker)
        st.markdown(
            """
            <div style='height: 500px; overflow-y: scroll; padding-right: 10px;'>""",
            unsafe_allow_html=True
        )
        for item in finviz_news:
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                st.markdown(f"**{time}** — [{title}]({url}) ({src})")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.header("📊 EarningsWhispers")
        ew_data = get_earnings_data(ticker)
        if isinstance(ew_data, str):
            st.error(ew_data)
        else:
            for key, value in ew_data.items():
                st.markdown(f"**{key}:** {value}")

    # 📌 Finhub EPS Daten
    st.header("📈 EPS Daten (Finhub)")
    finhub_df = get_finhub_data(ticker, api_key)
    st.dataframe(finhub_df)

    # 📊 EPS Change % Chart
    st.subheader("📉 EPS Veränderung % (Quartal über Quartal)")
    fig, ax = plt.subplots()
    ax.plot(finhub_df["Quarter"], finhub_df["EPS Change %"], marker='o')
    ax.set_title("EPS Change % nach Quartal")
    ax.set_xlabel("Quartal")
    ax.set_ylabel("Change %")
    ax.grid(True)
    st.pyplot(fig)
