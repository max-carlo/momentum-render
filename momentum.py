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
# 5) EarningsWhispers (mit Datum im passenden Format)
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
        parts = dt_text.split(",")[-1].replace("ET", "").strip()
        parsed = datetime.datetime.strptime(parts, "%B %d %Y %I:%M %p")
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
# 6) SEC EPS + Revenue
# ============================================================
@st.cache_data(ttl=86400)
def get_sec_eps_yoy(tic: str):
    try:
        mapping = requests.get("https://www.sec.gov/files/company_tickers.json", timeout=20, headers={"User-Agent":"Mozilla/5.0 myemail@example.com"}).json()
        cik = next((str(item["cik_str"]).zfill(10) for item in mapping.values() if item["ticker"].upper() == tic.upper()), None)
        if cik is None:
            raise Exception("Ticker nicht gefunden")
        facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers={"User-Agent":"Mozilla/5.0 myemail@example.com"}, timeout=20).json()
    except Exception as e:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"Revenue":None,"YoY Change %":None,"Hinweis":str(e)}])

    def extract_metric(facts, key):
        try:
            units = facts["facts"]["us-gaap"][key]["units"]
            return next(iter(units.values()))
        except Exception:
            return []

    eps_entries = extract_metric(facts, "EarningsPerShareBasic")
    rev_entries = extract_metric(facts, "Revenues")

    def filter_entries(entries):
        out = []
        for e in entries:
            fp = e.get("fp", ""); form = e.get("form", "")
            if ((fp.startswith("Q") and form.startswith("10-Q")) or (fp == "FY" and form.startswith("10-K"))):
                try:
                    out.append((datetime.datetime.fromisoformat(e["end"]), e["val"], fp))
                except Exception:
                    pass
        return out

    eps_data = filter_entries(eps_entries)
    rev_data = filter_entries(rev_entries)
    if not eps_data:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"Revenue":None,"YoY Change %":None,"Hinweis":"Keine EPS-Daten"}])

    df_eps = pd.DataFrame(eps_data, columns=["Period","EPS Actual","fp"])
    df_rev = pd.DataFrame(rev_data, columns=["Period","Revenue","fp"])
    df = pd.merge(df_eps, df_rev, on=["Period","fp"], how="left")
    df.sort_values("Period", ascending=False, inplace=True)
    df["quarter"] = df["fp"].where(df["fp"] != "FY", "Q4").str[1].astype(int)
    df["year"] = df["Period"].dt.year
    df = df.drop_duplicates(subset=["year","quarter"], keep="first")
    df["Quarter"] = "Q" + df["quarter"].astype(str) + " " + df["year"].astype(str)
    df["YoY Change %"] = None
    for idx, row in df.iterrows():
        prev = df[(df["quarter"] == row["quarter"]) & (df["year"] == row["year"] - 1)]
        if not prev.empty and prev.iloc[0]["EPS Actual"] not in (0, None):
            df.at[idx, "YoY Change %"] = round((row["EPS Actual"] - prev.iloc[0]["EPS Actual"]) / abs(prev.iloc[0]["EPS Actual"]) * 100, 2)

    return df[["Quarter", "EPS Actual", "Revenue", "YoY Change %"]]

# ============================================================
# 7) Ausgabe
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
    d1, d2 = st.columns([1, 1])
    eps_df = get_sec_eps_yoy(ticker)

    with d1:
        st.dataframe(eps_df)

    with d2:
        if "Quarter" in eps_df.columns and eps_df["YoY Change %"].notna().any():
            fig, ax = plt.subplots(figsize=(4, 2))
            last_12 = eps_df.iloc[:12].iloc[::-1]
            ax.plot(last_12["YoY Change %"].values, linewidth=1)
            ax.set_xticks(range(len(last_12)))
            ax.set_xticklabels(last_12["Quarter"], rotation=45, fontsize=8)
            ax.set_ylabel("Change %", fontsize=8)
            ax.set_xlabel("Quarter", fontsize=8)
            ax.tick_params(labelsize=8)
            ax.grid(False)
            st.pyplot(fig)

            st.subheader("Revenue Verlauf")
            fig2, ax2 = plt.subplots(figsize=(4, 2))
            ax2.plot(last_12["Revenue"].values, linewidth=1)
            ax2.set_xticks(range(len(last_12)))
            ax2.set_xticklabels(last_12["Quarter"], rotation=45, fontsize=8)
            ax2.set_ylabel("Revenue", fontsize=8)
            ax2.set_xlabel("Quarter", fontsize=8)
            ax2.tick_params(labelsize=8)
            ax2.grid(False)
            st.pyplot(fig2)
        else:
            st.info("YoY-Daten nicht verfügbar")

    st.markdown(
        f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{ticker}/earnings)"
    )
