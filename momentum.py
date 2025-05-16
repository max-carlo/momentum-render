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
      .ampel-hint{font-size:0.85rem;font-style:italic;text-align:right;padding-right:10px;margin-top:4px;color:gray}
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
# 5) EarningsWhispers (Datum in richtigem Format)
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
        dt_text = re.search(r"(\w+ \d+, \d{4})", dt_text).group(1)
        parsed = datetime.datetime.strptime(dt_text, "%B %d, %Y")
        dt_text = parsed.strftime("%d.%m.%Y")
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

# ============================================================
# 6) Ausgabe
# ============================================================
if submitted and ticker:
    ticker = ticker.upper()

    c1, c2 = st.columns(2)
    with c1:
        st.header("News")
        news_html = "<div class='finviz-scroll'>"
        for itm in scrape_finviz_news(ticker):
            if isinstance(itm, str):
                news_html += f"<div style='color:red'>{itm}</div>"
            else:
                tm, ttl, url_news, src = itm
                news_html += f"<div><strong>{tm}</strong> — <a href='{url_news}' target='_blank'>{ttl}</a> ({src})</div>"
        news_html += "</div>"
        st.markdown(news_html, unsafe_allow_html=True)

    with c2:
        st.header("Last Earnings")
        ew = get_earnings_data(ticker)
        st.caption(f"Stand: {ew.pop('Date')}")
        block = "<div class='earnings-box'>" + "".join(
            f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items()
        ) + "</div>"
        st.markdown(block, unsafe_allow_html=True)

    st.markdown("""<div style='margin-top:2em'><h3>Historische Earnings (SEC Edgar)</h3></div>""", unsafe_allow_html=True)

    eps_df = get_sec_eps_yoy(ticker)
    st.dataframe(eps_df)

    if "Quarter" in eps_df.columns and eps_df["YoY Change %"].notna().any():
        col1, col2 = st.columns(2)
        last_12 = eps_df.iloc[:12].iloc[::-1]

        with col1:
            st.subheader("EPS YoY Change")
            fig, ax = plt.subplots(figsize=(4, 2))
            ax.plot(last_12["YoY Change %"].values, linewidth=1)
            ax.set_xticks(range(len(last_12)))
            ax.set_xticklabels(last_12["Quarter"], rotation=45, fontsize=8)
            ax.set_ylabel("Change %", fontsize=8)
            ax.set_xlabel("Quarter", fontsize=8)
            ax.tick_params(labelsize=8)
            ax.grid(False)
            st.pyplot(fig)

        with col2:
            st.subheader("Revenue YoY Change")
            yoy_rev = last_12.copy()
            yoy_rev["YoY Rev %"] = None
            for idx, row in yoy_rev.iterrows():
                prev = eps_df[(eps_df["quarter"] == row["quarter"]) & (eps_df["year"] == row["year"] - 1)]
                if not prev.empty and prev.iloc[0]["Revenue"] not in (0, None):
                    yoy_rev.at[idx, "YoY Rev %"] = round((row["Revenue"] - prev.iloc[0]["Revenue"]) / abs(prev.iloc[0]["Revenue"]) * 100, 2)
            fig2, ax2 = plt.subplots(figsize=(4, 2))
            ax2.plot(yoy_rev["YoY Rev %"].values, linewidth=1)
            ax2.set_xticks(range(len(yoy_rev)))
            ax2.set_xticklabels(yoy_rev["Quarter"], rotation=45, fontsize=8)
            ax2.set_ylabel("Revenue YoY %", fontsize=8)
            ax2.set_xlabel("Quarter", fontsize=8)
            ax2.tick_params(labelsize=8)
            ax2.grid(False)
            st.pyplot(fig2)
    else:
        st.info("YoY-Daten nicht verfügbar")

    st.markdown(
        f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{ticker}/earnings)"
    )
