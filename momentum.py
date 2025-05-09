import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ============================================================
# 1) Ampel‑Funktion (liefert Symbol + Status)
# ============================================================

def get_ampel():
    qqq = yf.download("QQQ", period="3mo", interval="1d")
    if len(qqq) < 3:
        return "⚪", "neutral"
    qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
    qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
    up = (
        qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
        and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
        and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
    )
    down = (
        qqq["EMA9"].iloc[-1] < qqq["EMA21"].iloc[-1]
        and qqq["EMA9"].iloc[-1] < qqq["EMA9"].iloc[-2]
        and qqq["EMA21"].iloc[-1] < qqq["EMA21"].iloc[-2]
    )
    if up:
        return "🟢", "up"
    if down:
        return "🔴", "down"
    return "🟡", "side"

ampel_symbol, ampel_state = get_ampel()

# ============================================================
# 2) CSS Styling
# ============================================================
st.markdown(
    """
    <style>
      .ampel-box{font-size:80px;line-height:1;text-align:right;padding-right:20px}
      .ampel-hint{font-size:0.75rem;font-style:italic;text-align:right;padding-right:8px;margin-top:-8px}
      h1,.stHeader,.stMarkdown h2,.stMarkdown h3{font-size:1.5rem!important;font-weight:600}
      .finviz-scroll{font-size:.875rem;font-family:sans-serif;line-height:1.4;max-height:190px;overflow-y:auto;padding-right:10px}
      .earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.4;}
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
    st.markdown(f"<div class='ampel-box'>{ampel_symbol}</div>", unsafe_allow_html=True)
    if ampel_state == "up":
        hint = "*9‑EMA > 21‑EMA, beide steigend*"
    elif ampel_state == "down":
        hint = "*9‑EMA < 21‑EMA, beide fallend*"
    else:
        hint = "*uneindeutig*"
    st.markdown(f"<div class='ampel-hint'>{hint}</div>", unsafe_allow_html=True)

# ============================================================
# 4) Finviz‑News
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
# 5) EarningsWhispers  (inkl. Datum)
# ============================================================

def get_earnings_data(tic: str):
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Datum auslesen
        pg.wait_for_selector("#epsdate", timeout=15000)
        dt_text = pg.inner_text("#epsdate")

        # Zahlen auslesen
        sel = (
            "#earnings .growth",
            "#earnings .surprise",
            "#revenue .growth",
            "#revenue .surprise",
        )
        eg, es, rg, rs = (pg.inner_text(s) for s in sel)
        br.close()

    # Datum formatieren -> dd.mm.yyyy
    m = re.search(r"([A-Za-z]+) (\d{1,2}), (\d{4})", dt_text)
    if m:
        month, day, year = m.group(1), m.group(2), m.group(3)
        try:
            dt_obj = datetime.datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
            date_str = dt_obj.strftime("%d.%m.%Y")
        except:
            date_str = "N/A"
    else:
        date_str = "N/A"

    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    sr_raw = yf.Ticker(tic).info.get("shortRatio", "N/A")
    sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    return {
        "Earnings Date":     date_str,
        "Earnings Growth":   f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth":    f"{clean(rg)}%",
        "Revenue Surprise":  clean(rs),
        "Short Ratio":       sr,
    }

# ============================================================
# 6) SEC‑Edgar EPS (raw, dedupliziert)
# ============================================================

@st.cache_data(ttl=86400)
def get_sec_eps_raw(tic: str):
    UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        mapping = requests.get("https://www.sec.gov/files/company_tickers.json", headers=UA, timeout=20).json()
        cik = next((str(v["cik_str"]).zfill(10) for v in mapping.values() if v["ticker"].upper()==tic.upper()), None)
        if not cik:
            raise ValueError("Ticker nicht gefunden")
        facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=UA, timeout=20).json()
        units = facts["facts"]["us-gaap"]["EarningsPerShareBasic"]["units"]
        unit_vals = next(iter(units.values()))
    except Exception as e:
        return pd.DataFrame({"Quarter":["-"],"EPS Actual":[None],"YoY Change %":[None],"Hinweis":[str(e)]})

    rows = []
    for e in unit_vals:
        fp = e.get("fp", "")
        form = e.get("form", "")
        if (fp.startswith("Q") and form.startswith("10-Q")) or (fp=="FY" and form.startswith("10-K")):
            try:
                rows.append((datetime.datetime.fromisoformat(e["end"]), e["val"], fp))
            except Exception:
                pass

    if not rows:
        return pd.DataFrame({"Quarter":["-"],"EPS Actual":[None],"YoY Change %":[None],"Hinweis":["Keine Quartalsdaten"]})

    df = pd.DataFrame(rows, columns=["Period", "EPS Actual", "fp"])
    df.sort_values("Period", ascending=False, inplace=True)
    df["quarter"] = df["fp"].where(df["fp"]!="FY","Q4").str[1].astype(int)
    df["year"]    = df["Period"].dt.year
    df = df.drop_duplicates(subset=["year","quarter"], keep="first")
    df["Quarter"] = "Q"+df["quarter"].astype(str)+" "+df["year"].astype(str)
    df["YoY Change %"] = df.groupby("quarter")["EPS Actual"].pct_change(1).round(2)*100
    return df[["Quarter","EPS Actual","YoY Change %"]]

# ============================================================
# 7) Ausgabe
# ============================================================
if submitted and ticker:
    tic = ticker.upper()

    col1, col2 = st.columns(2)
    # ---------------- News ----------------
    with col1:
        st.header("News")
        news_html = "<div class='finviz-scroll'>"
        for t, ttl, url_n, src in scrape_finviz_news(tic):
            news_html += f"<div><strong>{t}</strong> — <a href='{url_n}' target='_blank'>{ttl}</a> ({src})</div>"
        news_html += "</div>"
        st.markdown(news_html, unsafe_allow_html=True)

    # ---------------- Last Earnings ----------------
    with col2:
        st.header("Last Earnings")
        ew = get_earnings_data(tic)
        html = "<div class='earnings-box'>" + "".join(
            f"<div><strong>{k}</strong>: {v}</div>" for k, v in ew.items()
        ) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # ---------------- Historische Earnings ----------------
    st.header("Historische Earnings (SEC Edgar)")
    c3, c4 = st.columns([1, 1])
    eps = get_sec_eps_raw(tic)

    with c3:
        st.dataframe(eps)

    with c4:
        if eps["YoY Change %"].notna().any():
            st.subheader("EPS Veränderung % (YoY)")
            fig, ax = plt.subplots(figsize=(4, 2))
            ax.plot(eps["Quarter"], eps["YoY Change %"], linewidth=1)
            ax.set_ylabel("Change %", fontsize=8)
            ax.set_xlabel("Quarter", fontsize=8)
            step = max(len(eps)//4, 1)
            ax.set_xticks(range(0, len(eps), step))
            ax.set_xticklabels(eps["Quarter"][::step], rotation=45, fontsize=8)
            ax.tick_params(labelsize=8)
            ax.grid(axis="y", linestyle=":", linewidth=0.5)
            st.pyplot(fig)
        else:
            st.info("YoY-Daten nicht verfügbar")

    # Link zu Seeking Alpha
    st.markdown(
        f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{ticker}/earnings)"
    )
