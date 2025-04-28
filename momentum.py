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

# =======================
# AMPel‑Trend (QQQ EMA9 vs EMA21)
# =======================
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

# =======================
# CSS‑Styling
# =======================
st.markdown(
    """
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
        max-height: 225px;
        overflow-y: auto;
        padding-right: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =======================
# Eingabe + Ampel‑Spalten
# =======================
col_input, col_ampel = st.columns([4, 1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_ampel:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)

# =======================
# Finviz‑News‑Scraper
# =======================

def scrape_finviz_news(ticker: str):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        return [f"Fehler beim Laden der Finviz-Seite: {e}"]

    soup = BeautifulSoup(res.text, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")
    news_items = []
    for row in rows:
        td_time = row.find("td", width="130")
        a_title = row.find("a", class_="tab-link-news")
        span_src = row.find("span")
        if td_time and a_title and span_src:
            news_items.append(
                (
                    td_time.text.strip(),
                    a_title.text.strip(),
                    a_title["href"],
                    span_src.text.strip("()"),
                )
            )
    return news_items

# =======================
# EarningsWhispers‑Scraper (robust)
# =======================

def get_earnings_data(ticker: str):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            for sel in [
                "#earnings .growth",
                "#earnings .surprise",
                "#revenue .growth",
                "#revenue .surprise",
            ]:
                page.wait_for_selector(sel, timeout=15000)

            earnings_growth = page.inner_text("#earnings .growth")
            earnings_surprise = page.inner_text("#earnings .surprise")
            revenue_growth = page.inner_text("#revenue .growth")
            revenue_surprise = page.inner_text("#revenue .surprise")
        except Exception:
            earnings_growth = earnings_surprise = revenue_growth = revenue_surprise = "N/A"
        finally:
            browser.close()

    def clean(txt):
        return re.sub(r"[^\d\.-]", "", txt)

    try:
        info = yf.Ticker(ticker).info
        sr_raw = info.get("shortRatio")
        sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    except:
        sr = "N/A"

    return {
        "Earnings Growth": f"{clean(earnings_growth)}%",
        "Earnings Surprise": clean(earnings_surprise),
        "Revenue Growth": f"{clean(revenue_growth)}%",
        "Revenue Surprise": clean(revenue_surprise),
        "Short Ratio": sr,
    }

# =======================
# Zacks‑Scraper für Quartals‑EPS + YoY
# =======================

def get_zacks_eps_yoy(ticker: str):
    """Scrape Zacks earnings table and compute YoY change."""
    url = f"https://www.zacks.com/stock/research/{ticker}/earnings-calendar?tab=transcript&icid=quote-eps-quote_nav_tracking-zcom-left_subnav_quote_navbar-earnings_transcripts"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
    except Exception as e:
        return pd.DataFrame([{"Hinweis": f"Zacks nicht erreichbar: {e}"}])

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table", id="earnings_announcements_earnings_table")
    if table is None:
        return pd.DataFrame([{"Hinweis": "Kein Earnings‑Table auf Zacks gefunden."}])

    rows = table.select("tbody tr")
    data = []
    for r in rows:
        cells = [c.get_text(strip=True) for c in r.find_all("td")]
        if len(cells) < 5:
            continue
        period = cells[1]  # e.g. "2024-03-31" (Period Ending)
        reported_eps = cells[3]  # Reported EPS
        try:
            eps_val = float(re.sub(r"[^\d\.-]", "", reported_eps))
        except ValueError:
            eps_val = None
        data.append((period, eps_val))

    if not data:
        return pd.DataFrame([{"Hinweis": "Zacks lieferte keine Daten."}])

    df = pd.DataFrame(data, columns=["Period", "EPS Actual"])
    df["Period"] = pd.to_datetime(df["Period"])
    df["year"] = df["Period"].dt.year
    df["quarter"] = df["Period"].dt.quarter
    df.sort_values("Period", ascending=False, inplace=True)

    # YoY Berechnung: gleiches Quartal Vorjahr
    df["YoY Change %"] = None
    for idx, row in df.iterrows():
        cur_q, cur_y = row["quarter"], row["year"]
        match = df[(df["quarter"] == cur_q) & (df["year"] == cur_y - 1)]
        if not match.empty and pd.notnull(match.iloc[0]["EPS Actual"]) and match.iloc[0]["EPS Actual"] != 0:
            prev_eps = match.iloc[0]["EPS Actual"]
            df.at[idx, "YoY Change %"] = round((row["EPS Actual"] - prev_eps) / abs(prev_eps) * 100, 2)

    df["Quarter"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)
    return df[["Quarter", "EPS Actual", "YoY Change %"]]

# =======================
# Anzeige nach Eingabe
# =======================
if submitted and ticker:
    ticker = ticker.strip().upper()

    col1, col2 = st.columns(2)

    # ---------- Finviz ----------
    with col1:
        st.header("News")
        news_items = scrape_finviz_news(ticker)
        news_html = "<div class='finviz-scroll'>"
        for item in news_items:
            if isinstance(item, str):
                st.error(item)
            else:
                time, title, url, src = item
                news_html += f"<div><strong>{time}</strong> — <a href='{url}' target='_blank'>{title}</a> ({src})</div>"
        news_html += "</div>"
        st.markdown(news_html, unsafe_allow_html=True)

    # ---------- EarningsWhispers ----------
    with col2:
        st.header("Last Earnings")
        ew = get_earnings_data(ticker)
        if isinstance(ew, str):
            st.error(ew)
        else:
            block = "<div class='earnings-box'>" + "".join(
                [f"<div><strong>{k}</strong>: {v}</
