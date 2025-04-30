import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, json, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ============================================================
# 1) Ampel: QQQ Trend
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
# 2) CSS Styling
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
# 5) EarningsWhispers (unchanged)
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
            eg = pg.inner_text("#earnings .growth"); es = pg.inner_text("#earnings .surprise")
            rg = pg.inner_text("#revenue .growth"); rs = pg.inner_text("#revenue .surprise")
        except Exception:
            eg = es = rg = rs = "N/A"
        br.close()
    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    try:
        sr_raw = yf.Ticker(tic).info.get("shortRatio"); sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
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
# 6) SEC Edgar EPS (XBRL CompanyFacts)
# ============================================================

@st.cache_data(ttl=86400)
def get_sec_eps_yoy(tic: str):
    """Fetch quarterly basic EPS from SEC CompanyFacts and compute YoY."""
    # 6.1 Ticker → CIK mapping (daily JSON from SEC)
    try:
        mapping = requests.get("https://www.sec.gov/files/company_tickers.json", timeout=20, headers={"User-Agent":"Mozilla/5.0 myemail@example.com"}).json()
        cik = None
        for item in mapping.values():
            if item["ticker"].upper() == tic.upper():
                cik = str(item["cik_str"]).zfill(10)
                break
        if cik is None:
            return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"Ticker nicht gefunden"}])
    except Exception as e:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":str(e)}])

    # 6.2 CompanyFacts JSON
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        facts = requests.get(url, headers={"User-Agent":"Mozilla/5.0 myemail@example.com"}, timeout=20).json()
    except Exception as e:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":str(e)}])

    # Search for GAAP EarningsPerShareBasic
    try:
        eps_facts = facts["facts"]["us-gaap"]["EarningsPerShareBasic"]["units"]
        # pick first currency unit e.g. USD/shares
        unit_values = next(iter(eps_facts.values()))
    except Exception:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"EPS nicht gefunden"}])

    rows = []
    for entry in unit_values:
        if entry.get("fp", "").startswith("Q") and entry.get("form") in ("10-Q", "10-Q/A"):
            end = entry.get("end")
            val = entry.get("val")
            try:
                end_date = datetime.datetime.fromisoformat(end)
                rows.append((end_date, val))
            except Exception:
                pass
    if not rows:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"Keine Quartalsdaten"}])

    df = pd.DataFrame(rows, columns=["Period", "EPS Actual"])
    df.sort_values("Period", ascending=False, inplace=True)
    df["year"] = df["Period"].dt.year
    df["quarter"] = df["Period"].dt.quarter
    df["Quarter"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)

    # YoY
    df["YoY Change %"] = None
    for idx, row in df.iterrows():
        prev = df[(df["quarter"] == row["quarter"]) & (df["year"] == row["year"] - 1)]
        if not prev.empty and prev.iloc[0]["EPS Actual"] not in (0, None):
            df.at[idx, "YoY Change %"] = round((row["EPS Actual"] - prev.iloc[0]["EPS Actual"]) / abs(prev.iloc[0]["EPS Actual"]) * 100, 2)

    return df[["Quarter", "EPS Actual", "YoY Change %"]]

# ============================================================
# 7) Ausgabe
# ============================================================
if submitted and ticker:
    ticker = ticker.upper()

    c1, c2 = st.columns(2)
    # ----- Finviz -----
    with c1:
        st.header("News")
        for itm in scrape_finviz_news(ticker):
