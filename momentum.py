# momentum.py – Aktienanalyse-Dashboard
# =======================================

import streamlit as st
import pandas as pd
import yfinance as yf
import re, datetime
from playwright.sync_api import sync_playwright

st.set_page_config(layout="wide")

# ------------------------------------------------------------
# 1) QQQ-Trend-Ampel
# ------------------------------------------------------------
def get_ampel():
    try:
        qqq = yf.download("QQQ", period="3mo", interval="1d")
    except Exception:
        return "⚪"
    if len(qqq) < 3:
        return "⚪"
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
        return "🟡"

ampel = get_ampel()

# ------------------------------------------------------------
# 2) CSS
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      .ampel-box{font-size:80px;line-height:1;text-align:right;padding-right:20px}
      .ampel-hint{font-size:.85rem;font-style:italic;text-align:right;padding-right:10px;margin-top:4px;color:gray}
      h1,.stHeader,.stMarkdown h2,.stMarkdown h3{font-size:1.5rem!important;font-weight:600}
      .earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.8;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 3) Formular & Ampel
# ------------------------------------------------------------
c_in, c_lamp = st.columns([4, 1])
with c_in:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        cb1, cb2 = st.columns(2)
        with cb1:
            open_sa = st.checkbox("SeekingAlpha öffnen")
        with cb2:
            open_zacks = st.checkbox("Zacks öffnen")
        submitted = st.form_submit_button("Daten abrufen")
with c_lamp:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='ampel-hint'>{'*9 EMA > 21 EMA, beide steigend*' if ampel=='🟢' else '*9 EMA < 21 EMA, beide fallend*' if ampel=='🔴' else '*uneindeutig*'}</div>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 4) Hilfsfunktionen
# ------------------------------------------------------------
def _normalize_epsdate(raw: str) -> str:
    if not raw or not raw.strip():
        return "N/A"
    raw = raw.strip()
    m = re.search(r"[A-Za-z]+,\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", raw)
    if not m:
        return raw
    try:
        dt = datetime.datetime.strptime(m.group(1), "%B %d, %Y")
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return raw

def _extract_time(raw: str) -> str:
    """Uhrzeit oder Session (AMC/BMO) aus EarningsWhispers-Datumstext."""
    if not raw:
        return "N/A"
    m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M)", raw, re.IGNORECASE)
    if m:
        return m.group(1)
    if "After" in raw:
        return "AMC (After Market Close)"
    if "Before" in raw:
        return "BMO (Before Market Open)"
    return "N/A"

def _fallback_yf_date(tic: str) -> str:
    try:
        yft = yf.Ticker(tic)
        info = yft.info or {}
        for key in ("nextEarningsDate", "earningsDate"):
            if key in info and info[key]:
                return pd.to_datetime(info[key]).strftime("%d.%m.%Y")
        cal = yft.calendar
        if isinstance(cal, pd.DataFrame) and not cal.empty:
            if "Earnings Date" in cal.index:
                val = cal.loc["Earnings Date"][0]
            else:
                val = next((v for v in cal.values.flatten()
                            if isinstance(v, (pd.Timestamp, datetime.datetime, datetime.date))), None)
            if val is not None:
                return pd.to_datetime(val).strftime("%d.%m.%Y")
    except Exception:
        pass
    return "N/A"

# ------------------------------------------------------------
# 5) EarningsWhispers via Playwright
# ------------------------------------------------------------
def get_earnings_data(tic: str) -> dict:
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)

            try:
                pg.locator("text=Accept").click(timeout=3000)
            except Exception:
                pass

            try:
                pg.wait_for_function(
                    """() => {
                        const n = document.querySelector('#epsdate');
                        return n && n.textContent.trim().length > 0;
                    }""",
                    timeout=10000,
                )
            except Exception:
                pass

            dt_text = pg.inner_text("#epsdate")

            # Uhrzeit: eigenes Element versuchen, sonst aus Datumstext
            try:
                time_raw = pg.inner_text("#epstime").strip()
                time_str = time_raw if time_raw else _extract_time(dt_text)
            except Exception:
                time_str = _extract_time(dt_text)

            for sel in ("#earnings .growth", "#earnings .surprise", "#revenue .growth", "#revenue .surprise"):
                pg.wait_for_selector(sel, timeout=15000)
            eg = pg.inner_text("#earnings .growth")
            es = pg.inner_text("#earnings .surprise")
            rg = pg.inner_text("#revenue .growth")
            rs = pg.inner_text("#revenue .surprise")
        except Exception:
            dt_text = ""
            time_str = "N/A"
            eg = es = rg = rs = "N/A"
        br.close()

    date_norm = _normalize_epsdate(dt_text)
    if date_norm == "N/A":
        date_norm = _fallback_yf_date(tic)

    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    try:
        sr_raw = yf.Ticker(tic).info.get("shortRatio")
        sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    except Exception:
        sr = "N/A"

    return {
        "Datum":            date_norm,
        "Uhrzeit":          time_str,
        "Earnings Growth":  f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth":   f"{clean(rg)}%",
        "Revenue Surprise": clean(rs),
        "Short Ratio":      sr,
    }

# ------------------------------------------------------------
# 6) Ausgabe
# ------------------------------------------------------------
if submitted and ticker:
    tic = ticker.upper()

    # Externe Links
    st.subheader("Externe Links")
    link_items = [("Finviz", f"https://finviz.com/quote.ashx?t={tic}&p=d")]
    if open_sa:
        link_items.append(("SeekingAlpha", f"https://seekingalpha.com/symbol/{tic}"))
    if open_zacks:
        link_items.append(("Zacks", f"https://www.zacks.com/stock/quote/{tic}"))
    cols = st.columns(len(link_items))
    for col, (label, url) in zip(cols, link_items):
        col.link_button(f"↗ {label}", url)

    # Earnings
    st.header("Earnings")
    with st.spinner("Lade EarningsWhispers-Daten..."):
        ew = get_earnings_data(tic)
    box = "<div class='earnings-box'>"
    box += "".join(f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items())
    box += "</div>"
    st.markdown(box, unsafe_allow_html=True)
