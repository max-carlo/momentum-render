# momentum.py – Aktienanalyse-Dashboard
# =======================================

import streamlit as st
import pandas as pd
import yfinance as yf
import datetime

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
# 4) Earnings-Daten via yfinance
# ------------------------------------------------------------
def get_earnings_data(tic: str) -> dict:
    result = {
        "Nächstes Earnings-Datum": "N/A",
        "Uhrzeit / Session":       "N/A",
        "EPS Surprise (letztes Q)": "N/A",
        "EPS Growth YoY":           "N/A",
        "Revenue Growth YoY":       "N/A",
        "Short Ratio":              "N/A",
    }

    yft = yf.Ticker(tic)

    # --- Datum & Uhrzeit aus earnings_dates ---
    try:
        ed = yft.earnings_dates
        if ed is not None and not ed.empty:
            # Nächster Termin = Zeile ohne gemeldetes EPS
            upcoming = ed[ed["Reported EPS"].isna()]
            if not upcoming.empty:
                dt = upcoming.index[0]
                result["Nächstes Earnings-Datum"] = dt.strftime("%d.%m.%Y")
                h = dt.hour
                if h == 0:
                    result["Uhrzeit / Session"] = "Zeit unbekannt"
                elif 4 <= h <= 11:
                    result["Uhrzeit / Session"] = f"{dt.strftime('%H:%M')} ET  (BMO)"
                else:
                    result["Uhrzeit / Session"] = f"{dt.strftime('%H:%M')} ET  (AMC)"
    except Exception:
        pass

    # Fallback: calendar
    if result["Nächstes Earnings-Datum"] == "N/A":
        try:
            cal = yft.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                d = pd.to_datetime(dates[0] if hasattr(dates, "__len__") else dates)
                result["Nächstes Earnings-Datum"] = d.strftime("%d.%m.%Y")
            elif isinstance(cal, pd.DataFrame) and not cal.empty and "Earnings Date" in cal.index:
                d = pd.to_datetime(cal.loc["Earnings Date"].iloc[0])
                result["Nächstes Earnings-Datum"] = d.strftime("%d.%m.%Y")
        except Exception:
            pass

    # --- EPS Surprise & Growth aus gemeldeten Quartalen ---
    try:
        ed = yft.earnings_dates
        if ed is not None and not ed.empty:
            reported = ed[ed["Reported EPS"].notna()].copy()
            if not reported.empty:
                latest = reported.iloc[0]

                if "Surprise(%)" in reported.columns and pd.notna(latest.get("Surprise(%)")):
                    result["EPS Surprise (letztes Q)"] = f"{latest['Surprise(%)']:.1f}%"

                # YoY: gleicher Quartal vor einem Jahr = 4 Einträge früher
                if len(reported) >= 5:
                    eps_now = latest["Reported EPS"]
                    eps_yoy = reported.iloc[4]["Reported EPS"]
                    if pd.notna(eps_now) and pd.notna(eps_yoy) and eps_yoy != 0:
                        growth = (eps_now - eps_yoy) / abs(eps_yoy) * 100
                        result["EPS Growth YoY"] = f"{growth:.1f}%"
    except Exception:
        pass

    # --- Revenue Growth aus quarterly income statement ---
    try:
        qf = None
        for attr in ("quarterly_income_stmt", "quarterly_financials"):
            qf = getattr(yft, attr, None)
            if qf is not None and not qf.empty:
                break
        if qf is not None and not qf.empty:
            for label in ("Total Revenue", "Revenue"):
                if label in qf.index:
                    rev = qf.loc[label]
                    if len(rev) >= 5:
                        r_now = rev.iloc[0]
                        r_yoy = rev.iloc[4]
                        if pd.notna(r_now) and pd.notna(r_yoy) and r_yoy != 0:
                            growth = (r_now - r_yoy) / abs(r_yoy) * 100
                            result["Revenue Growth YoY"] = f"{growth:.1f}%"
                    break
    except Exception:
        pass

    # --- Short Ratio ---
    try:
        sr_raw = yft.info.get("shortRatio")
        if isinstance(sr_raw, (int, float)):
            result["Short Ratio"] = str(round(sr_raw, 2))
    except Exception:
        pass

    return result

# ------------------------------------------------------------
# 5) Ausgabe
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
    with st.spinner("Lade Daten..."):
        ew = get_earnings_data(tic)
    box = "<div class='earnings-box'>"
    box += "".join(f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items())
    box += "</div>"
    st.markdown(box, unsafe_allow_html=True)
