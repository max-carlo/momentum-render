import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, random, json
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# 👉 Alpha‑Vantage‑API‑Key (kostenlos)
AV_KEY = "KEEVSBBKLMOHT4BJ"  # gerne in st.secrets auslagern

# ============================================================
# Ampel basierend auf QQQ‑EMAs
# ============================================================
qqq = yf.download("QQQ", period="3mo", interval="1d")
qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
ampel = "🟢" if (
    qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
    and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
    and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
) else "🔴"

# ============================================================
# CSS styling
# ============================================================
st.markdown(
    """
    <style>
      .ampel-box{font-size:80px;line-height:1;text-align:right;padding-right:20px}
      h1,.stHeader,.stMarkdown h2,.stMarkdown h3{font-size:1.5rem!important;font-weight:600}
      .finviz-scroll,.earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.4;max-height:225px;overflow-y:auto;padding-right:10px}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Eingabeformular & Ampel
# ============================================================
col_input, col_ampel = st.columns([4, 1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_ampel:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)

# ============================================================
# Finviz‑News‑Scraper
# ============================================================

def scrape_finviz_news(tic: str):
    url = f"https://finviz.com/quote.ashx?t={tic}&p=d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return [f"Finviz‑Fehler: {e}"]
    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")
    out = []
    for row in rows:
        td = row.find("td", width="130"); a = row.find("a", class_="tab-link-news"); sp = row.find("span")
        if td and a and sp:
            out.append((td.text.strip(), a.text.strip(), a["href"], sp.text.strip("()")))
    return out

# ============================================================
# EarningsWhispers‑Scraper (robust)
# ============================================================

def get_earnings_data(tic: str):
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            for sel in ("#earnings .growth", "#earnings .surprise", "#revenue .growth", "#revenue .surprise"):
                pg.wait_for_selector(sel, timeout=15000)
            eg = pg.inner_text("#earnings .growth")
            es = pg.inner_text("#earnings .surprise")
            rg = pg.inner_text("#revenue .growth")
            rs = pg.inner_text("#revenue .surprise")
        except Exception:
            eg = es = rg = rs = "N/A"
        br.close()
    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    try:
        sr_raw = yf.Ticker(tic).info.get("shortRatio")
        sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    except Exception:
        sr = "N/A"
    return {
        "Earnings Growth": f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth": f"{clean(rg)}%",
        "Revenue Surprise": clean(rs),
        "Short Ratio": sr,
    }

# ============================================================
# Alpha‑Vantage EPS (20 Quartale) + YoY
# ============================================================

def get_av_eps_yoy(tic: str, key: str):
    url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={tic}&apikey={key}"
    try:
        data = requests.get(url, timeout=20).json()
        q = pd.DataFrame(data["quarterlyEarnings"])
    except Exception as e:
        return pd.DataFrame([{"Quarter": "-", "EPS Actual": None, "YoY Change %": None, "Hinweis": str(e)}])
    if q.empty:
        return pd.DataFrame([{"Quarter": "-", "EPS Actual": None, "YoY Change %": None, "Hinweis": "Keine AV‑Daten"}])

    q["reportedEPS"] = pd.to_numeric(q["reportedEPS"], errors="coerce")
    q["fiscalDateEnding"] = pd.to_datetime(q["fiscalDateEnding"])
    q["year"] = q["fiscalDateEnding"].dt.year
    q["quarter"] = q["fiscalDateEnding"].dt.quarter
    q["Quarter"] = "Q" + q["quarter"].astype(str) + " " + q["year"].astype(str)
    q.sort_values("fiscalDateEnding", ascending=False, inplace=True)

    # YoY Change
    q["YoY Change %"] = q.groupby("quarter")["reportedEPS"].pct_change(1).round(2) * 100
    return q[["Quarter", "reportedEPS", "YoY Change %"]].rename(columns={"reportedEPS": "EPS Actual"})

# ============================================================
# Ausgabe
# ============================================================
if submitted and ticker:
    ticker = ticker.upper()

    c1, c2 = st.columns(2)

    # ---------- Finviz ----------
    with c1:
        st.header("News")
        for itm in scrape_finviz_news(ticker):
            if isinstance(itm, str):
                st.error(itm)
            else:
                tm, ttl, url_news, src = itm
                st.markdown(f"**{tm}** — [{ttl}]({url_news}) ({src})")

    # ---------- EarningsWhispers ----------
    with c2:
        st.header("Last Earnings")
        ew = get_earnings_data(ticker)
        if isinstance(ew, str):
            st.error(ew)
        else:
            block = "<div class='earnings-box'>" + "".join(
                f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items()
            ) + "</div>"
            st.markdown(block, unsafe_allow_html=True)

    # ---------- Alpha‑Vantage EPS ----------
    st.header("Historische Earnings (Alpha Vantage)")
    d1, d2 = st.columns([1, 1])
    eps_df = get_av_eps_yoy(ticker, AV_KEY)

    with d1:
        st.dataframe(eps_df)

    with d2:
        if "Quarter" in eps_df.columns and eps_df["YoY Change %"].notna().any():
            st.subheader("EPS Veränderung % (YoY)")
            fig, ax = plt.subplots(figsize=(4, 2))
            ax.plot(eps_df["Quarter"], eps_df["YoY Change %"], marker="o")
            ax.set_ylabel("Change %", fontsize=8); ax.set_xlabel("Quarter", fontsize=8)
            ax.tick_params(labelsize=8); ax.grid(True); plt.xticks(rotation=45)
            st.pyplot(fig)
        else:
            st.info("YoY‑Daten nicht verfügbar (Alpha Vantage Limit erreicht?)")

    st.markdown(f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{ticker}/earnings)")
