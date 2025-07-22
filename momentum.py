# app.py  – Aktienanalyse‑Dashboard (Datum‑Fix v2)
# ===============================================

import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ------------------------------------------------------------
# 1) QQQ‑Trend‑Ampel
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
      .finviz-scroll{font-size:.875rem;font-family:sans-serif;line-height:1.4;max-height:180px;overflow-y:auto;padding-right:10px}
      .earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.4;}
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
        submitted = st.form_submit_button("Daten abrufen")
with c_lamp:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='ampel-hint'>{'*9 EMA > 21 EMA, beide steigend*' if ampel=='🟢' else '*9 EMA < 21 EMA, beide fallend*' if ampel=='🔴' else '*uneindeutig*'}</div>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 4) Finviz‑News  (Link‑Fix)
# ------------------------------------------------------------
def scrape_finviz_news(tic: str):
    base = "https://finviz.com"
    url  = f"{base}/quote.ashx?t={tic}&p=d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return [f"Finviz-Fehler: {e}"]

    soup = BeautifulSoup(r.text, "html.parser")
    rows, out = soup.select("table.fullview-news-outer tr"), []
    for row in rows:
        td = row.find("td", width="130"); a = row.find("a", class_="tab-link-news"); sp = row.find("span")
        if td and a and sp:
            link = a["href"]
            if link.startswith("/"):
                link = base + link
            out.append((td.text.strip(), a.text.strip(), link, sp.text.strip("()")))
    return out

# ------------------------------------------------------------
# 5) EPS‑Datum normalisieren
# ------------------------------------------------------------
def _normalize_epsdate(raw: str) -> str:
    if not raw or not raw.strip():
        return "N/A"
    raw = raw.strip()
    session = "AMC" if "After" in raw else "BMO" if "Before" in raw else ""
    m = re.search(r"[A-Za-z]+,\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", raw)
    if not m:
        return raw
    try:
        dt = datetime.datetime.strptime(m.group(1), "%B %d, %Y")
        return dt.strftime("%d.%m.%Y") + (f" {session}" if session else "")
    except Exception:
        return raw

# ------------------------------------------------------------
# 6) yfinance‑Fallback  (info → calendar)
# ------------------------------------------------------------
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
# 7) EarningsWhispers + robustes Datum
# ------------------------------------------------------------
def get_earnings_data(tic: str):
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Cookie‑Banner akzeptieren
            try:
                pg.locator("text=Accept").click(timeout=3000)
            except Exception:
                pass

            # warten bis #epsdate nicht mehr leer
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
            for sel in ("#earnings .growth", "#earnings .surprise", "#revenue .growth", "#revenue .surprise"):
                pg.wait_for_selector(sel, timeout=15000)
            eg = pg.inner_text("#earnings .growth"); es = pg.inner_text("#earnings .surprise")
            rg = pg.inner_text("#revenue .growth");  rs = pg.inner_text("#revenue .surprise")
        except Exception:
            dt_text = ""; eg = es = rg = rs = "N/A"
        br.close()

    date_norm = _normalize_epsdate(dt_text)
    if date_norm == "N/A":                       # Fallback
        date_norm = _fallback_yf_date(tic)

    clean = lambda t: re.sub(r"[^\d\.-]", "", t)
    try:
        sr_raw = yf.Ticker(tic).info.get("shortRatio")
        sr = str(round(sr_raw, 2)) if isinstance(sr_raw, (int, float)) else "N/A"
    except Exception:
        sr = "N/A"

    return {
        "Date": date_norm,
        "Earnings Growth": f"{clean(eg)}%",
        "Earnings Surprise": clean(es),
        "Revenue Growth": f"{clean(rg)}%",
        "Revenue Surprise": clean(rs),
        "Short Ratio": sr,
    }

# ------------------------------------------------------------
# 8) SEC‑EPS‑YoY  (wie gehabt)
# ------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_sec_eps_yoy(tic: str):
    try:
        mapping = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            timeout=20,
            headers={"User-Agent":"Mozilla/5.0 name@example.com"}
        ).json()
        cik = next((str(it["cik_str"]).zfill(10) for it in mapping.values()
                    if it["ticker"].upper()==tic.upper()), None)
        if not cik:
            return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"Ticker nicht gefunden"}])
    except Exception as e:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":str(e)}])

    try:
        facts = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            timeout=20,
            headers={"User-Agent":"Mozilla/5.0 name@example.com"}
        ).json()
        eps_facts = facts["facts"]["us-gaap"]["EarningsPerShareBasic"]["units"]
        unit_values = next(iter(eps_facts.values()))
    except Exception:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"EPS nicht gefunden"}])

    rows=[]
    for e in unit_values:
        fp, form = e.get("fp",""), e.get("form","")
        if ((fp.startswith("Q") and form in ("10-Q","10-Q/A")) or (fp=="FY" and form in ("10-K","10-K/A"))):
            try:
                rows.append((datetime.datetime.fromisoformat(e["end"]), e["val"], fp))
            except Exception:
                pass
    if not rows:
        return pd.DataFrame([{"Quarter":"-","EPS Actual":None,"YoY Change %":None,"Hinweis":"Keine Quartalsdaten"}])

    df = pd.DataFrame(rows, columns=["Period","EPS Actual","fp"]).sort_values("Period", ascending=False)
    df["quarter"] = df["fp"].where(df["fp"]!="FY","Q4").str[1].astype(int)
    df["year"]    = df["Period"].dt.year
    df = df.drop_duplicates(subset=["year","quarter"], keep="first")
    df["Quarter"] = "Q"+df["quarter"].astype(str)+" "+df["year"].astype(str)
    df["YoY Change %"] = None
    for idx,row in df.iterrows():
        prev = df[(df["quarter"]==row["quarter"])&(df["year"]==row["year"]-1)]
        if not prev.empty and prev.iloc[0]["EPS Actual"] not in (0,None):
            df.at[idx,"YoY Change %"]=round((row["EPS Actual"]-prev.iloc[0]["EPS Actual"])
                                            /abs(prev.iloc[0]["EPS Actual"])*100,2)
    return df[["Quarter","EPS Actual","YoY Change %"]]

# ------------------------------------------------------------
# 9) Ausgabe
# ------------------------------------------------------------
if submitted and ticker:
    tic = ticker.upper()

    c1, c2 = st.columns(2)

    # News ----------------------------------------------------
    with c1:
        st.header("News")
        html = "<div class='finviz-scroll'>"
        for itm in scrape_finviz_news(tic):
            if isinstance(itm,str):
                html += f"<div style='color:red'>{itm}</div>"
            else:
                tm, ttl, link, src = itm
                html += f"<div><strong>{tm}</strong> — <a href='{link}' target='_blank' rel='noopener noreferrer'>{ttl}</a> ({src})</div>"
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    # Last Earnings ------------------------------------------
    with c2:
        st.header("Last Earnings")
        ew = get_earnings_data(tic)
        datum = ew.pop("Date","N/A") or "N/A"
        box = "<div class='earnings-box'>"
        box += f"<div><strong>Datum</strong>: {datum}</div>"
        box += "".join(f"<div><strong>{k}</strong>: {v}</div>" for k,v in ew.items())
        box += "</div>"
        st.markdown(box, unsafe_allow_html=True)

    # Historische EPS ----------------------------------------
    st.markdown("<div style='margin-top:2em'><h3>Historische Earnings (SEC Edgar)</h3></div>", unsafe_allow_html=True)
    d1, d2 = st.columns([1,1])
    eps_df = get_sec_eps_yoy(tic)

    with d1:
        st.dataframe(eps_df)

    with d2:
        if eps_df["YoY Change %"].notna().any():
            fig, ax = plt.subplots(figsize=(4,2))
            last12 = eps_df.iloc[:12].iloc[::-1]
            ax.plot(last12["YoY Change %"].values, linewidth=1)
            ax.set_xticks(range(len(last12)))
            ax.set_xticklabels(last12["Quarter"], rotation=45, fontsize=8)
            ax.set_ylabel("Change %", fontsize=8); ax.set_xlabel("Quarter", fontsize=8)
            ax.tick_params(labelsize=8); ax.grid(False)
            st.pyplot(fig)
        else:
            st.info("YoY‑Daten nicht verfügbar")

    st.markdown(f"[➡️ Weitere Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{tic}/earnings)")
