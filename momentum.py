import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ============================================================
# 1) Ampel-Funktion  (einfach – wie früher)
# ============================================================

def get_ampel():
    qqq = yf.download("QQQ", period="3mo", interval="1d")
    if len(qqq) < 3:
        return "⚪"
    qqq["EMA9"]  = qqq["Close"].ewm(span=9).mean()
    qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
    up   = (qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1] and
            qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]   and
            qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2])
    down = (qqq["EMA9"].iloc[-1] < qqq["EMA21"].iloc[-1] and
            qqq["EMA9"].iloc[-1] < qqq["EMA9"].iloc[-2]   and
            qqq["EMA21"].iloc[-1] < qqq["EMA21"].iloc[-2])
    return "🟢" if up else "🔴" if down else "🟡"

ampel = get_ampel()

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
col_input, col_amp = st.columns([4, 1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_amp:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)

# ============================================================
# 4) Finviz-News (einfach)
# ============================================================

def scrape_finviz_news(tic: str):
    url = f"https://finviz.com/quote.ashx?t={tic}&p=d"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")
    return [
        (td.text.strip(), a.text.strip(), a["href"], sp.text.strip("()"))
        for row in rows
        if (td := row.find("td", width="130"))
        and (a := row.find("a", class_="tab-link-news"))
        and (sp := row.find("span"))
    ]

# ============================================================
# 5) EarningsWhispers (einfach)
# ============================================================

def get_earnings_data(tic: str):
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        sel = (
            "#earnings .growth",
            "#earnings .surprise",
            "#revenue .growth",
            "#revenue .surprise",
        )
        eg, es, rg, rs = (pg.inner_text(s) for s in sel)
        br.close()
    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    sr_raw = yf.Ticker(tic).info.get("shortRatio", "N/A")
    sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    return {
        "Earnings Growth": f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth": f"{clean(rg)}%",
        "Revenue Surprise": clean(rs),
        "Short Ratio": sr,
    }

# ============================================================
# 6) SEC Edgar EPS (roh, keine Filter, minimaler Fehler‑Fallback)
# ============================================================

@st.cache_data(ttl=86400)
def get_sec_eps_raw(tic: str):
    UA = {"User-Agent": "Mozilla/5.0"}
    try:
        mapping = requests.get("https://www.sec.gov/files/company_tickers.json", headers=UA, timeout=20).json()
        cik = next(
            (str(v["cik_str"]).zfill(10) for v in mapping.values() if v["ticker"].upper() == tic.upper()),
            None,
        )
        if not cik:
            raise ValueError("Ticker nicht gefunden")
        facts = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=UA, timeout=20
        ).json()
        units = facts["facts"]["us-gaap"]["EarningsPerShareBasic"]["units"]
        unit_vals = next(iter(units.values()))
    except Exception as e:
        return pd.DataFrame([
            {
                "Quarter": "-",
                "EPS Actual": None,
                "YoY Change %": None,
                "Hinweis": str(e),
            }
        ])

    rows = []
    for e in unit_vals:
        if e.get("fp", "").startswith("Q"):
            try:
                rows.append((datetime.datetime.fromisoformat(e["end"]), e["val"]))
            except Exception:
                pass
    if not rows:
        return pd.DataFrame([
            {"Quarter": "-", "EPS Actual": None, "YoY Change %": None, "Hinweis": "Keine Quartalsdaten"}
        ])

    df = pd.DataFrame(rows, columns=["Period", "EPS Actual"])
    df.sort_values("Period", ascending=False, inplace=True)
    df["year"] = df["Period"].dt.year
    df["quarter"] = df["Period"].dt.quarter
    df["Quarter"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)
    df["YoY Change %"] = df.groupby("quarter")["EPS Actual"].pct_change(1).round(2) * 100
    return df[["Quarter", "EPS Actual", "YoY Change %"]]

# ============================================================
# 7) Ausgabe
# ============================================================
if submitted and ticker:
    tic = ticker.upper()

    col1, col2 = st.columns(2)
    with col1:
        st.header("News")
        for t, ttl, url_n, src in scrape_finviz_news(tic):
            st.markdown(f"**{t}** — [{ttl}]({url_n}) ({src})")

    with col2:
        st.header("Last Earnings")
        ew = get_earnings_data(tic)
        html = (
            "<div class='earnings-box'>"
            + "".join(f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items())
            + "</div>"
        )
        st.markdown(html, unsafe_allow_html=True)

    st.header("Historische Earnings (SEC Edgar – roh)")
    c3, c4 = st.columns([1, 1])
    eps = get_sec_eps_raw(tic)

    with c3:
        st.dataframe(eps)

    with c4:
        if eps["YoY Change %"].notna().any():
            st.subheader("EPS Veränderung % (YoY)")
            fig, ax = plt.subplots(figsize=(4, 2))
            ax.plot(eps["Quarter"], eps["YoY Change %"], marker="o")
            ax.set_ylabel("Change %", fontsize=8)
            ax.set_xlabel("Quarter", fontsize=8)
            ax.tick_params(labelsize=8)
            ax.grid(True)
            plt.xticks(rotation=45)
            st.pyplot(fig)
        else:
            st.info("YoY-Daten nicht verfügbar")

    st.markdown(
        f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{tic}/earnings)"
    )
