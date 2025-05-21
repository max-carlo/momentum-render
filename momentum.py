import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests, datetime
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")

# ============================================================
# 1) Ampel – QQQ‑Trend
# ============================================================

def get_ampel():
    qqq = yf.download("QQQ", period="3mo", interval="1d")
    if len(qqq) < 3:
        return "⚪", "uneindeutig"
    qqq["EMA9"]  = qqq["Close"].ewm(span=9).mean()
    qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
    up   = (qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1] and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2] and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2])
    down = (qqq["EMA9"].iloc[-1] < qqq["EMA21"].iloc[-1] and qqq["EMA9"].iloc[-1] < qqq["EMA9"].iloc[-2] and qqq["EMA21"].iloc[-1] < qqq["EMA21"].iloc[-2])
    if up:   return "🟢", "9 EMA > 21 EMA, beide steigend"
    if down: return "🔴", "9 EMA < 21 EMA, beide fallend"
    return "🟡", "uneindeutig"

ampel_symbol, ampel_hint = get_ampel()

# ============================================================
# 2) CSS‑Styling
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
# 3) Eingabe & Ampel
# ============================================================

col_in, col_amp = st.columns([4,1])
with col_in:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_amp:
    st.markdown(f"<div class='ampel-box'>{ampel_symbol}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='ampel-hint'>*{ampel_hint}*</div>", unsafe_allow_html=True)

# ============================================================
# 4) Finviz‑News
# ============================================================

def scrape_finviz_news(tic):
    url=f"https://finviz.com/quote.ashx?t={tic}&p=d"
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15); r.raise_for_status()
    except Exception as e:
        return [f"Finviz‑Fehler: {e}"]
    soup=BeautifulSoup(r.text,"html.parser")
    rows=soup.select("table.fullview-news-outer tr")
    out=[]
    for row in rows:
        td=row.find("td",width="130"); a=row.find("a",class_="tab-link-news"); sp=row.find("span")
        if td and a and sp:
            out.append((td.text.strip(),a.text.strip(),a["href"],sp.text.strip("()")))
    return out

# ============================================================
# 5) EarningsWhispers (kompakt)
# ============================================================

def get_earnings_data(tic):
    url=f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br=p.chromium.launch(headless=True); pg=br.new_page()
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=60000)
            raw_dt=pg.inner_text("#epsdate")
            for sel in ("#earnings .growth","#earnings .surprise","#revenue .growth","#revenue .surprise"):
                pg.wait_for_selector(sel,timeout=15000)
            eg=pg.inner_text("#earnings .growth"); es=pg.inner_text("#earnings .surprise")
            rg=pg.inner_text("#revenue .growth"); rs=pg.inner_text("#revenue .surprise")
        except Exception:
            raw_dt="N/A"; eg=es=rg=rs="N/A"
        br.close()
    try:
        raw_dt=re.search(r"(\w+ \d+, \d{4})",raw_dt).group(1)
        raw_dt=datetime.datetime.strptime(raw_dt,"%B %d, %Y").strftime("%d.%m.%Y")
    except Exception:
        pass
    clean=lambda t: re.sub(r"[^\d\.-]","",t)
    return {"Date":raw_dt,"Earnings Growth":f"{clean(eg)}%","Earnings Surprise":clean(es),"Revenue Growth":f"{clean(rg)}%","Revenue Surprise":clean(rs)}

# ============================================================
# 6) SEC‑Facts: EPS, Revenue & YoY
# ============================================================

@st.cache_data(ttl=86400)
def sec_eps_rev_yoy(tic):
    UA={"User-Agent":"Mozilla/5.0"}
    try:
        mapping=requests.get("https://www.sec.gov/files/company_tickers.json",headers=UA,timeout=20).json()
        cik=next((str(v["cik_str"]).zfill(10) for v in mapping.values() if v["ticker"].upper()==tic.upper()),None)
        if not cik:
            raise ValueError("Ticker nicht gefunden")
        facts=requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",headers=UA,timeout=20).json()
    except Exception as e:
        return pd.DataFrame([{"Quarter":"-","EPS":None,"Revenue":None,"EPS YoY%":None,"Rev YoY%":None,"Hinweis":str(e)}])

    def pull(key):
        try:
            return next(iter(facts["facts"]["us-gaap"][key]["units"].values()))
        except Exception:
            return []

    eps=pull("EarningsPerShareBasic"); rev=pull("Revenues")

    def filt(lst):
        rows=[]
        for e in lst:
            fp=e.get("fp",""); form=e.get("form","")
            if ((fp.startswith("Q") and form.startswith("10-Q")) or (fp=="FY" and form.startswith("10-K"))):
                try:
                    rows.append((datetime.datetime.fromisoformat(e["end"]),e["val"],fp))
                except Exception:
                    pass
        return rows

    eps_df=pd.DataFrame(filt(eps),columns=["Period","EPS","fp"])
    rev_df=pd.DataFrame(filt(rev),columns=["Period","Revenue","fp"])
    df=pd.merge(eps_df,rev_df,on=["Period","fp"],how="left")
    df.sort_values("Period",ascending=False,inplace=True)
    df["q"]=df["fp"].where(df["fp"]!="FY","Q4").str[1].astype(int)
    df["y"]=df["Period"].dt.year
    df=df.drop_duplicates(subset=["y","q"],keep="first")
    df["Quarter"]="Q"+df["q"].astype(str)+" "+df["y"].astype(str)
    df["EPS YoY%"]=df.groupby("q")["EPS"].pct_change()*100
    df["Rev YoY%"]=df.groupby("q")["Revenue"].pct_change()*100
    df[["EPS YoY%","Rev YoY%"]]=df[["EPS YoY%","Rev YoY%"].].round(2)
    return df[["Quarter","EPS","Revenue","EPS YoY%","Rev YoY%"]]

# ============================================================
# 7) Ausgabe
# ============================================================

if submitted and ticker:
    tic=ticker.upper()

    colN,colE=st.columns(2)
    # ---- News ----
    with colN:
        st.header("News")
        html="<div class='finviz-scroll'>"
        for itm in scrape_finviz_news(tic):
            if isinstance(itm,str):
                html+=f"<div style='color:red'>{itm}</div>"
            else:
                tm,ttl,url,src=itm
                html+=f"<div><strong>{tm}</strong> — <a href='{url}' target='_blank'>{ttl}</a> ({src})</div>"
        html+="</div>"
        st.markdown(html,unsafe_allow_html=True)

    # ---- Last Earnings ----
    with colE:
        st.header("Last Earnings")
        ew=get_earnings_data(tic)
        st.caption(f"Stand: {ew.pop('Date')}")
        block="<div class='earnings-box'>"+"".join(f"<div><strong>{k}:</strong> {v}</div>" for k,v in ew.items())+"</div>"
        st.markdown(block,unsafe_allow_html=True)

    # ---- Historische Earnings / Revenue ----
    st.markdown("""<div style='margin-top:2em'><h3>Historische Earnings (SEC Edgar)</h3></div>""",unsafe_allow_html=True)
    full_df=sec_eps_rev_yoy(tic)
    st.dataframe(full_df,use_container_width=True)

    # letzte 12 Quartale (chronologisch)
    last12=full_df.dropna(subset=["EPS YoY%","Rev YoY%"]).head(12)[::-1]
    col_eps,col_rev=st.columns(2)
    if not last12.empty:
        with col_eps:
            st.subheader("EPS YoY %")
            fig,ax=plt.subplots(figsize=(4,2))
            ax.plot(last12["EPS YoY%"].values,linewidth=1)
            ax.set_xticks(range(len(last12)))
            ax.set_xticklabels(last12["Quarter"],rotation=45,fontsize=8)
            ax.set_ylabel("EPS YoY %",fontsize=8); ax.set_xlabel("Quarter",fontsize=8); ax.grid(False)
            st.pyplot(fig)
        with col_rev:
            st.subheader("Revenue YoY %")
            fig2,ax2=plt.subplots(figsize=(4,2))
            ax2.plot(last12["Rev YoY%"].values,linewidth=1)
            ax2.set_xticks(range(len(last12)))
            ax2.set_xticklabels(last12["Quarter"],rotation=45,fontsize=8)
            ax2.set_ylabel("Revenue YoY %",fontsize=8); ax2.set_xlabel("Quarter",fontsize=8); ax2.grid(False)
            st.pyplot(fig2)
    else:
        st.info("Nicht genügend YoY‑Daten vorhanden")

    st.markdown(f"[➡️ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{tic}/earnings)")
