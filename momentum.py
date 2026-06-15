# momentum.py – Aktienanalyse-Dashboard
# =======================================

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import yfinance as yf
import re, datetime, time, requests, json
from bs4 import BeautifulSoup
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
      .stApp{background:#f7f8fa;}
      h1,h2,h3,.stMarkdown h2,.stMarkdown h3{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        color:#101828;font-weight:700;letter-spacing:-.01em;}
      h1{font-size:1.9rem!important;}
      .panel-title{font-size:1.05rem;font-weight:700;color:#101828;margin:0 0 10px 2px;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}

      /* Ampel */
      .ampel-box{font-size:72px;line-height:1;text-align:right;padding-right:18px}
      .ampel-hint{font-size:.8rem;font-style:italic;text-align:right;padding-right:10px;margin-top:2px;color:#98a2b3}

      /* News-Karte */
      .news-card{background:#fff;border:1px solid #e8ebef;border-radius:14px;padding:8px 6px 8px 16px;
        box-shadow:0 1px 3px rgba(16,24,40,.06);}
      .news-scroll{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        font-size:.86rem;line-height:1.45;max-height:340px;overflow-y:auto;padding-right:12px;}
      .news-scroll .it{padding:7px 0;border-bottom:1px solid #f2f4f7;}
      .news-scroll .it:last-child{border-bottom:none;}
      .news-scroll .tm{color:#98a2b3;font-weight:600;font-size:.78rem;}
      .news-scroll a{color:#1d6fe0;text-decoration:none;}
      .news-scroll a:hover{text-decoration:underline;}
      .news-scroll .src{color:#98a2b3;}

      /* Externe Link-Buttons */
      .ext-links{display:flex;gap:10px;margin:2px 0 14px 0;}
      .ext-btn{display:inline-flex;align-items:center;gap:6px;font-size:.85rem;font-weight:600;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        padding:8px 16px;border-radius:10px;text-decoration:none;border:1px solid #d0d5dd;
        background:#fff;color:#344054;box-shadow:0 1px 2px rgba(16,24,40,.05);transition:all .15s;}
      .ext-btn:hover{background:#f9fafb;border-color:#98a2b3;transform:translateY(-1px);}
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
        f"<div class='ampel-hint'>{'*9 EMA > 21 EMA, beide steigend*' if ampel=='🟢' else '*9 EMA < 21 EMA, beide fallend*' if ampel=='🔴' else '*uneindeutig*'}</div>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 4) Hilfsfunktionen (identisch mit Original)
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

def _extract_session(raw: str) -> str:
    """Konkrete Uhrzeit (inkl. ET) bzw. AMC/BMO aus dem EarningsWhispers-Datumstext.

    Beispiel-Rohtext: 'Thursday, April 30, 2026 at 4:30 PM ET'
    """
    if not raw:
        return "N/A"
    m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M(?:\s*ET)?)", raw, re.IGNORECASE)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
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
# 5) EarningsWhispers – identische Selektoren wie Original
# ------------------------------------------------------------
@st.cache_data(ttl=3600)
def scrape_finviz(tic: str):
    """Holt die Finviz-Quote-Seite EINMAL (1h app-weit gecacht) und liefert News
    + Kennzahlen. Finviz wird so max. 1x pro Ticker/Stunde gescraped (kein 429),
    und die Short Ratio kommt aus derselben Seite — ganz ohne yfinance/Yahoo
    (dessen .info-Endpoint von Render-IPs rate-limited wird)."""
    base = "https://finviz.com"
    url  = f"{base}/quote.ashx?t={tic}&p=d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return {"news": [f"Finviz-Fehler: {e}"], "short_ratio": "N/A"}

    soup = BeautifulSoup(r.text, "html.parser")

    # News
    news = []
    for row in soup.select("table.fullview-news-outer tr"):
        td = row.find("td", width="130")
        a = row.find("a", class_="tab-link-news")
        sp = row.find("span")
        if td and a and sp:
            link = a["href"]
            if link.startswith("/"):
                link = base + link
            news.append((td.text.strip(), a.text.strip(), link, sp.text.strip("()")))

    # Kennzahlen aus der Snapshot-Tabelle (Label/Wert-Paare)
    cells = soup.select("table.snapshot-table2 td")
    snap = {}
    for i in range(0, len(cells) - 1, 2):
        snap[cells[i].get_text(strip=True)] = cells[i + 1].get_text(strip=True)
    short_ratio = snap.get("Short Ratio") or "N/A"

    return {"news": news, "short_ratio": short_ratio}


def _scrape_earningswhispers(tic: str, max_attempts: int = 10):
    """Scrapt EarningsWhispers mit Retry.

    EarningsWhispers liefert sporadisch HTTP 503 ('The service is unavailable.')
    an Scraper aus. Ein einzelner Versuch scheitert deshalb häufig — wir
    versuchen es mehrfach. Ein 503 lädt sofort (winziger Body), wird also schnell
    erkannt und übersprungen, ohne auf #epsdate-Timeout zu warten.
    """
    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        try:
            for attempt in range(max_attempts):
                pg = br.new_page()
                try:
                    pg.goto(url, wait_until="domcontentloaded", timeout=60000)

                    # 503-Sperrseite schnell erkennen → sofort neuer Versuch
                    if "service is unavailable" in pg.inner_text("body").lower():
                        time.sleep(1.0)
                        continue

                    try:
                        pg.locator("text=Accept").click(timeout=2000)
                    except Exception:
                        pass

                    # warten bis #epsdate echten Inhalt hat (JS-gerendert)
                    pg.wait_for_function(
                        """() => {
                            const n = document.querySelector('#epsdate');
                            return n && n.textContent.trim().length > 0;
                        }""",
                        timeout=8000,
                    )

                    dt_text = pg.inner_text("#epsdate")
                    for sel in ("#earnings .growth", "#earnings .surprise",
                                "#revenue .growth", "#revenue .surprise"):
                        pg.wait_for_selector(sel, timeout=8000)
                    eg = pg.inner_text("#earnings .growth")
                    es = pg.inner_text("#earnings .surprise")
                    rg = pg.inner_text("#revenue .growth")
                    rs = pg.inner_text("#revenue .surprise")
                    return dt_text, eg, es, rg, rs
                except Exception:
                    # noch nicht gerendert o.ä. → nächster Versuch
                    time.sleep(1.0)
                finally:
                    pg.close()
        finally:
            br.close()
    return "", "N/A", "N/A", "N/A", "N/A"


def get_earnings_data(tic: str):
    dt_text, eg, es, rg, rs = _scrape_earningswhispers(tic)

    date_norm = _normalize_epsdate(dt_text)
    if date_norm == "N/A":
        date_norm = _fallback_yf_date(tic)

    session_str = _extract_session(dt_text)

    def clean(t):
        v = re.sub(r"[^\d\.-]", "", t or "")
        return v if v not in ("", ".", "-") else None

    pct = lambda t: f"{clean(t)}%" if clean(t) else "N/A"
    num = lambda t: clean(t) or "N/A"

    # Short Ratio aus dem (gecachten) Finviz-Abruf — kein Yahoo-Rate-Limit
    sr = scrape_finviz(tic).get("short_ratio", "N/A")

    return {
        "Datum":             date_norm,
        "Uhrzeit":           session_str,
        "Earnings Growth":   pct(eg),
        "Earnings Surprise": num(es),
        "Revenue Growth":    pct(rg),
        "Revenue Surprise":  num(rs),
        "Short Ratio":       sr,
    }


def render_earnings_card(ew: dict):
    """Frische, helle Earnings-Karte mit Copy-Button (kopiert die Werte ohne Überschrift)."""
    rows = "".join(
        f"<div class='er-row'><span class='er-k'>{k}</span><span class='er-v'>{v}</span></div>"
        for k, v in ew.items()
    )
    copy_text = "\n".join(f"{k}: {v}" for k, v in ew.items())
    payload = json.dumps(copy_text)
    html = f"""
    <div class="er-card">
      <div class="er-head"><button id="er-copy" class="er-copy">📋 Kopieren</button></div>
      {rows}
    </div>
    <style>
      *{{box-sizing:border-box;}}
      body{{margin:0;}}
      .er-card{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        background:#fff;border:1px solid #e8ebef;border-radius:14px;padding:14px 18px 16px;
        box-shadow:0 1px 3px rgba(16,24,40,.06);}}
      .er-head{{display:flex;justify-content:flex-end;margin-bottom:4px;}}
      .er-row{{display:flex;justify-content:space-between;align-items:center;
        padding:8px 0;border-bottom:1px solid #f2f4f7;font-size:.9rem;}}
      .er-row:last-child{{border-bottom:none;}}
      .er-k{{color:#667085;font-weight:500;}}
      .er-v{{color:#101828;font-weight:700;}}
      .er-copy{{border:1px solid #d0d5dd;background:#f9fafb;color:#344054;border-radius:8px;
        padding:5px 12px;font-size:.78rem;font-weight:600;cursor:pointer;font-family:inherit;
        transition:all .15s;}}
      .er-copy:hover{{background:#f0f1f3;border-color:#98a2b3;}}
      .er-copy.ok{{background:#ecfdf3;border-color:#abefc6;color:#067647;}}
    </style>
    <script>
      (function(){{
        var b=document.getElementById('er-copy'), t={payload};
        function done(){{b.textContent='✓ Kopiert';b.classList.add('ok');
          setTimeout(function(){{b.textContent='📋 Kopieren';b.classList.remove('ok');}},1500);}}
        function fb(){{var ta=document.createElement('textarea');ta.value=t;
          ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);
          ta.focus();ta.select();try{{document.execCommand('copy');done();}}catch(e){{}}
          document.body.removeChild(ta);}}
        b.addEventListener('click',function(){{
          if(navigator.clipboard&&navigator.clipboard.writeText){{
            navigator.clipboard.writeText(t).then(done,fb);
          }}else{{fb();}}
        }});
      }})();
    </script>
    """
    components.html(html, height=46 + 38 * len(ew) + 24)

# ------------------------------------------------------------
# 6) Ausgabe
# ------------------------------------------------------------
if submitted and ticker:
    tic = ticker.upper()

    # Externe Seiten — feste Buttons, öffnen direkt einen neuen Tab
    st.markdown(
        f"""
        <div class="ext-links">
          <a class="ext-btn" href="https://seekingalpha.com/symbol/{tic}/earnings" target="_blank" rel="noopener">SeekingAlpha ↗</a>
          <a class="ext-btn" href="https://www.zacks.com/stock/research/{tic}/earnings-calendar" target="_blank" rel="noopener">Zacks ↗</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    # News (Finviz, 1h gecacht)
    with c1:
        st.markdown("<div class='panel-title'>📰 News</div>", unsafe_allow_html=True)
        with st.spinner("Lade News..."):
            news = scrape_finviz(tic)["news"]
        html = "<div class='news-card'><div class='news-scroll'>"
        for itm in news:
            if isinstance(itm, str):
                html += f"<div class='it' style='color:#d92d20'>{itm}</div>"
            else:
                tm, ttl, link, src = itm
                html += (f"<div class='it'><span class='tm'>{tm}</span><br>"
                         f"<a href='{link}' target='_blank' rel='noopener noreferrer'>{ttl}</a> "
                         f"<span class='src'>({src})</span></div>")
        html += "</div></div>"
        st.markdown(html, unsafe_allow_html=True)

    # Earnings
    with c2:
        st.markdown("<div class='panel-title'>📊 Earnings</div>", unsafe_allow_html=True)
        with st.spinner("Lade EarningsWhispers-Daten..."):
            ew = get_earnings_data(tic)
        render_earnings_card(ew)
