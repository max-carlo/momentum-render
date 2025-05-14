import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, json, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ============================================================
# 1) Ampel: QQQ Trend – robust gegen leere Daten
# ============================================================

def get_ampel():
    try:
        qqq = yf.download("QQQ", period="3mo", interval="1d")
    except Exception:
        return "⚪"  # neutral bei Netzfehler
    if len(qqq) < 3:
        return "⚪"  # nicht genug Daten

    qqq["EMA9"]  = qqq["Close"].ewm(span=9).mean()
    qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()

    if (
        qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
        and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
        and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
    ):
        return "🟢"
    elif (
        qqq["EMA9"].iloc[-1] < qqq["EMA21"].iloc[-1]
        and qqq["EMA9"].iloc[-1] < qqq["EMA9"].iloc[-2]
        and qqq["EMA21"].iloc[-1] < qqq["EMA21"].iloc[-2]
    ):
        return "🔴"
    else:
        return "🟡"  # seitwärts / uneindeutig

ampel = get_ampel()

qqq = yf.download("QQQ", period="3mo", interval="1d")
qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
ampel = "🟢" if (
    qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
    and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
    and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
) else "🔴"

# ============================================================
# 2) CSS Styling
# ============================================================
st.markdown(
    """
    <style>
      .ampel-box{font-size:80px;line-height:1;text-align:right;padding-right:20px}
      .ampel-hint{font-size:0.95rem;font-style:italic;text-align:right;padding-right:10px;margin-top:10px;color:gray}
      h1,.stHeader,.stMarkdown h2,.stMarkdown h3{font-size:1.5rem!important;font-weight:600}
      .finviz-scroll{font-size:.875rem;font-family:sans-serif;line-height:1.4;max-height:180px;overflow-y:auto;padding-right:10px}
      .earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.4;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 3) Eingabeformular & Ampel
# ============================================================
col_input, col_ampel = st.columns([4, 1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_ampel:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)
    hint_text = "*9 EMA > 21 EMA, beide steigend*" if ampel == "🟢" else ("*9 EMA < 21 EMA, beide fallend*" if ampel == "🔴" else "*uneindeutig*")
    st.markdown(f"<div class='ampel-hint'>{hint_text}</div>", unsafe_allow_html=True)

# ============================================================
# 4) Finviz News Scraper
# ============================================================

def scrape_finviz_news(tic: str):
    url = f"https://finviz.com/quote.ashx?t={tic}&p=d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return [f"Finviz-Fehler: {e}"]
    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")
    out = []
    for row in rows:
        td = row.find("td", width="130"); a = row.find("a", class_="tab-link-news"); sp = row.find("span")
        if td and a and sp:
            out.append((td.text.strip(), a.text.strip(), a["href"], sp.text.strip("()")))
    return out

# ============================================================
# 5) EarningsWhispers (mit Datum)
# ============================================================

def get_earnings_data(tic: str):
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            dt_text = pg.inner_text("#epsdate")
            for sel in ("#earnings .growth", "#earnings .surprise", "#revenue .growth", "#revenue .surprise"):
                pg.wait_for_selector(sel, timeout=15000)
            eg = pg.inner_text("#earnings .growth"); es = pg.inner_text("#earnings .surprise")
            rg = pg.inner_text("#revenue .growth"); rs = pg.inner_text("#revenue .surprise")
        except Exception:
            dt_text = "N/A"; eg = es = rg = rs = "N/A"
        br.close()

    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    try:
        sr_raw = yf.Ticker(tic).info.get("shortRatio"); sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    except Exception:
        sr = "N/A"

    try:
        parts = dt_text.split(",", 1)[-1].replace("ET", "").strip()
        dt_obj = datetime.datetime.strptime(parts, "%B %d %Y %I:%M %p")
        dt_text = dt_obj.strftime("%d.%m.%Y")
    except Exception:
        pass

    return {
        "Date": dt_text,
        "Earnings Growth": f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth": f"{clean(rg)}%",
        "Revenue Surprise": clean(rs),
        "Short Ratio": sr,
    }

# Der Rest des Codes bleibt unverändert
# ============================================================
# 6) SEC EPS (XBRL CompanyFacts)
# ============================================================
# ...
# 7) Ausgabe
# ============================================================
# ...
