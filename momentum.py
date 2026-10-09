# momentum.py – Aktienanalyse-Dashboard
# =======================================

import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import datetime, requests, json
from bs4 import BeautifulSoup

st.set_page_config(layout="wide")

# ------------------------------------------------------------
# 1) QQQ-Trend-Ampel
# ------------------------------------------------------------
@st.cache_data(ttl=600)   # QQQ-Ampel 10 min app-weit gecacht (über alle User geteilt)
def get_ampel():
    try:
        qqq = yf.download("QQQ", period="3mo", interval="1d")
    except Exception:
        return "⚪"
    if len(qqq) < 3:
        return "⚪"
    qqq["EMA9"]  = qqq["Close"].ewm(span=9).mean()
    qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
    # 🟢 9EMA > 21EMA und beide steigend
    # 🟡 9EMA > 21EMA, aber mind. einer steigt nicht
    # 🔴 21EMA > 9EMA
    if qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]:
        if (
            qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
            and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
        ):
            return "🟢"
        return "🟡"
    return "🔴"

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
        f"<div class='ampel-hint'>{'*9 EMA > 21 EMA, beide steigend*' if ampel=='🟢' else '*21 EMA > 9 EMA*' if ampel=='🔴' else '*9 EMA > 21 EMA, aber nicht beide steigend*'}</div>",
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------
# 5) Finviz – News + Short Ratio
# ------------------------------------------------------------
_FINVIZ_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finviz.com/",
}


@st.cache_resource
def _finviz_lkg():
    """Zuletzt erfolgreich geladener Stand je Ticker (prozessweit, ohne Ablauf).

    Rückfallebene, wenn Finviz mit 429 blockt: dann lieber leicht ältere News
    zeigen als eine rote Fehlermeldung."""
    return {}


@st.cache_data(ttl=300)   # 5 min – News bleiben frisch, Finviz wird nicht geflutet
def scrape_finviz(tic: str):
    """Holt die Finviz-Seite und liefert News + Kennzahlen.

    Drei Maßnahmen gegen das 429-Rate-Limit (Render hat eine feste Ausgangs-IP):
    1. Direkt /stock statt /quote.ashx – letzteres leitet zweimal um und kostet
       damit drei Requests pro Abruf statt einem.
    2. Vollständige Browser-Header statt nacktem 'Mozilla/5.0'.
    3. 5-Minuten-Cache: News bleiben aktuell genug, wiederholte Aufrufe
       desselben Tickers treffen Finviz aber nicht erneut.

    Schlägt der Abruf trotzdem fehl, wird der letzte erfolgreiche Stand
    ausgeliefert (als 'stale' markiert) statt einer Fehlermeldung."""
    base = "https://finviz.com"
    url  = f"{base}/stock?t={tic}&p=d"
    lkg  = _finviz_lkg()
    try:
        r = requests.get(url, headers=_FINVIZ_HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        stale = lkg.get(tic)
        if stale:
            return {**stale, "stale": True}
        return {"news": [f"Finviz gerade nicht erreichbar ({e})"],
                "short_ratio": "N/A", "stale": False}

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

    result = {"news": news, "short_ratio": short_ratio, "stale": False}
    if news:                      # nur brauchbare Antworten als Rückfall merken
        lkg[tic] = result
    return result


class _EarningsUnavailable(Exception):
    """Fehlgeschlagener Earnings-Abruf → Ergebnis NICHT cachen, aber anzeigen.

    reason: 'unknown'     = Ticker von EarningsWhispers nicht abgedeckt
            'unavailable' = temporaer nicht abrufbar"""
    def __init__(self, result, reason="unavailable"):
        super().__init__(f"earnings fetch failed ({reason})")
        self.result = result
        self.reason = reason


def _fmt_pct(v):
    """Ratio (0.2632) → '+26.32%'. Kein Zahlwert → 'N/A'."""
    if isinstance(v, (int, float)):
        return f"{v * 100:+.2f}%"
    return "N/A"


def _ew_gauges(soup):
    """Liest die Kennzahl-Gauges der epsdetails-Seite: {Label: Ratio}.

    Surprise steht als Rohwert in data-surprise (Ratio), Growth nur als
    Gauge-Text ("21.7 %"). Fehlt ein Wert (Gauge zeigt "—"), bleibt er weg."""
    out = {}
    for g in soup.select(".eps-metric .gauge"):
        lbl = g.select_one(".gauge-lbl")
        if not lbl:
            continue
        key = lbl.get_text(strip=True)
        surp = g.select_one(".eps-surp[data-surprise]")
        txt = g.select_one(".gauge-center")
        try:
            if surp is not None:
                out[key] = float(surp["data-surprise"])
            elif txt is not None:
                out[key] = float(txt.get_text(strip=True)
                                 .replace("%", "").replace(",", "").strip()) / 100
        except ValueError:
            pass
    return out


@st.cache_data(ttl=3600)   # Earnings 1h app-weit gecacht (über alle User geteilt)
def _fetch_earnings_data(tic: str):
    """Liest die Earnings-Kennzahlen aus der EarningsWhispers-Seite
    /epsdetails/<Ticker>. Seit dem Relaunch (Okt. 2026) gibt es den früheren
    JSON-Endpunkt /api/epsdetails nicht mehr (404); die Werte stehen jetzt
    serverseitig gerendert im HTML (.eps-date, .eps-metric-Gauges).

    Short Ratio kommt weiter aus dem (gecachten) Finviz-Abruf.
    """
    sr = scrape_finviz(tic).get("short_ratio", "N/A")

    url = f"https://www.earningswhispers.com/epsdetails/{tic}"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml",
    }

    result = {
        "Datum": "N/A", "Uhrzeit": "N/A",
        "Earnings Growth": "N/A", "Earnings Surprise": "N/A",
        "Revenue Growth": "N/A", "Revenue Surprise": "N/A",
        "Short Ratio": sr,
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        status = r.status_code
        soup = BeautifulSoup(r.text, "html.parser") if status == 200 else None
    except Exception:
        status, soup = None, None

    # 404 = Ticker von EarningsWhispers nicht abgedeckt (kein Tippfehler-Indiz:
    # z.B. SUJA existiert bei Finviz, wird von EW aber nicht gefuehrt)
    if status == 404:
        raise _EarningsUnavailable(result, "unknown")

    # Kein Datensatz → nicht cachen, damit der nächste Abruf frisch versucht.
    date_el = soup.select_one(".eps-date") if soup else None
    if date_el is None:
        raise _EarningsUnavailable(result, "unavailable")

    # z.B. "Thursday, July 30, 2026 · 4:30 PM ET" (Uhrzeit kann fehlen)
    parts = [p.strip() for p in date_el.get_text(" ", strip=True).split("·")]
    try:
        dt = datetime.datetime.strptime(parts[0], "%A, %B %d, %Y")
        result["Datum"] = dt.strftime("%d.%m.%Y")
    except ValueError:
        pass
    if len(parts) > 1:
        try:
            t = datetime.datetime.strptime(
                parts[1].replace("ET", "").strip(), "%I:%M %p").time()
            session = ("AMC" if t >= datetime.time(16, 0)
                       else "BMO" if t <= datetime.time(9, 30)
                       else "During Market")
            result["Uhrzeit"] = f"{t.strftime('%H:%M')} ET ({session})"
        except ValueError:
            pass

    g = _ew_gauges(soup)
    for key in ("Earnings Growth", "Earnings Surprise",
                "Revenue Growth", "Revenue Surprise"):
        result[key] = _fmt_pct(g.get(key))

    return result


def get_earnings_data(tic: str):
    """Cached-Wrapper: erfolgreiche Abrufe kommen aus dem geteilten Cache,
    fehlgeschlagene werden (ungecacht) durchgereicht, damit sie beim nächsten
    Aufruf erneut versucht werden.

    Rückgabe: (werte, grund) mit grund in {'ok', 'unknown', 'unavailable'}."""
    try:
        return _fetch_earnings_data(tic), "ok"
    except _EarningsUnavailable as e:
        return e.result, e.reason


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
            fv = scrape_finviz(tic)
        news = fv["news"]
        if fv.get("stale"):
            st.caption("⚠️ Finviz blockt gerade – gezeigt wird der zuletzt "
                       "erfolgreich geladene Stand.")
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
            ew, ew_status = get_earnings_data(tic)
        render_earnings_card(ew)
        if ew_status == "unknown":
            st.info(f"EarningsWhispers führt „{tic}“ nicht – das kommt bei kleineren "
                    "oder erst kürzlich gelisteten Titeln vor und ist kein Fehler. "
                    "News und Short Ratio stammen von Finviz; Earnings-Termine "
                    "lassen sich über die SeekingAlpha-/Zacks-Buttons oben prüfen.")
        elif ew_status == "unavailable":
            st.warning("Earnings-Daten gerade nicht abrufbar – bitte in ein paar "
                       "Minuten erneut versuchen.")
