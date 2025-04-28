import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re, requests
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt
from streamlit.components.v1 import html

st.set_page_config(layout="wide")

# ------------------- Ampel -------------------
qqq = yf.download("QQQ", period="3mo", interval="1d")
qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
ampel = "🟢" if (
    qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
    and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
    and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
) else "🔴"

# ------------------- Styling -------------------
st.markdown(
    """
    <style>
    .ampel-box{font-size:80px;line-height:1;text-align:right;padding-right:20px}
    h1,.block-title,.matplot-title,.stHeader,.stMarkdown h2,.stMarkdown h3{font-size:1.5rem!important;font-weight:600}
    .finviz-scroll,.earnings-box{font-size:.875rem;font-family:sans-serif;line-height:1.4;max-height:225px;overflow-y:auto;padding-right:10px}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------- Eingabe -------------------
col_input, col_ampel = st.columns([4,1])
with col_input:
    st.title("Aktienanalyse")
    with st.form("main_form"):
        ticker = st.text_input("Ticker eingeben", "")
        submitted = st.form_submit_button("Daten abrufen")
with col_ampel:
    st.markdown(f"<div class='ampel-box'>{ampel}</div>", unsafe_allow_html=True)

# ------------------- Finviz -------------------

def scrape_finviz_news(tic:str):
    url=f"https://finviz.com/quote.ashx?t={tic}&p=d"
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        r.raise_for_status()
    except Exception as e:
        return [str(e)]
    soup=BeautifulSoup(r.text,"html.parser")
    rows=soup.select("table.fullview-news-outer tr")
    out=[]
    for r in rows:
        td=r.find("td",width="130");a=r.find("a",class_="tab-link-news");sp=r.find("span")
        if td and a and sp:
            out.append((td.text.strip(),a.text.strip(),a["href"],sp.text.strip("()")))
    return out

# ------------------- EarningsWhispers -------------------

def get_earnings_data(tic:str):
    url=f"https://www.earningswhispers.com/epsdetails/{tic}"
    with sync_playwright() as p:
        br=p.chromium.launch(headless=True);pg=br.new_page()
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=60000)
            for sel in ["#earnings .growth","#earnings .surprise","#revenue .growth","#revenue .surprise"]:
                pg.wait_for_selector(sel,timeout=15000)
            eg=pg.inner_text("#earnings .growth");es=pg.inner_text("#earnings .surprise")
            rg=pg.inner_text("#revenue .growth");rs=pg.inner_text("#revenue .surprise")
        except Exception:
            eg=es=rg=rs="N/A"
        br.close()
    cl=lambda t:re.sub(r"[^\d\.-]","",t)
    try:
        sr_raw=yf.Ticker(tic).info.get("shortRatio");sr=str(round(sr_raw,2)) if isinstance(sr_raw,(int,float)) else "N/A"
    except: sr="N/A"
    return {"Earnings Growth":f"{cl(eg)}%","Earnings Surprise":cl(es),"Revenue Growth":f"{cl(rg)}%","Revenue Surprise":cl(rs),"Short Ratio":sr}

# ------------------- Zacks EPS YoY -------------------

def get_zacks_eps_yoy(tic:str):
    url=f"https://www.zacks.com/stock/research/{tic}/earnings-calendar?tab=transcript&icid=quote-eps-quote_nav_tracking-zcom-left_subnav_quote_navbar-earnings_transcripts"
    try:
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20);r.raise_for_status()
    except Exception as e:
        return pd.DataFrame([{"Hinweis":str(e)}])
    soup=BeautifulSoup(r.text,"html.parser")
    tbl=soup.find("table",id="earnings_announcements_earnings_table")
    if not tbl:
        return pd.DataFrame([{"Hinweis":"Keine Daten von Zacks"}])
    rows=tbl.select("tbody tr");data=[]
    for tr in rows:
        tds=[td.get_text(strip=True) for td in tr.find_all("td")]
        if len(tds)<5:continue
        period,eps=tds[1],tds[3]
        try:eps_val=float(re.sub(r"[^\d\.-]","",eps))
        except:eps_val=None
        data.append((period,eps_val))
    df=pd.DataFrame(data,columns=["Period","EPS Actual"])
    df["Period"]=pd.to_datetime(df["Period"]);df["year"]=df["Period"].dt.year;df["quarter"]=df["Period"].dt.quarter
    df.sort_values("Period",ascending=False,inplace=True)
    df["YoY Change %"]=None
    for idx,row in df.iterrows():
        q,y=row["quarter"],row["year"]
        prev=df[(df["quarter"]==q)&(df["year"]==y-1)]
        if not prev.empty and pd.notnull(prev.iloc[0]["EPS Actual"]) and prev.iloc[0]["EPS Actual"]!=0:
            df.at[idx,"YoY Change %"]=round((row["EPS Actual"]-prev.iloc[0]["EPS Actual"])/abs(prev.iloc[0]["EPS Actual"])*100,2)
    df["Quarter"]="Q"+df["quarter"].astype(str)+" "+df["year"].astype(str)
    return df[["Quarter","EPS Actual","YoY Change %"]]

# ------------------- App-Ausgabe -------------------
if submitted and ticker:
    ticker=ticker.upper()

    c1,c2=st.columns(2)
    # Finviz
    with c1:
        st.header("News")
        news=scrape_finviz_news(ticker)
        html_news="<div class='finviz-scroll'>"+"".join([
            f"<div><strong>{t}</strong> — <a href='{u}' target='_blank'>{ttl}</a> ({src})</div>" if not isinstance(item,str) else item
            for (t,ttl,u,src) in ([item] if isinstance(item,str) else [item] )
            for item in [item]  # flatten
        ])+"</div>"
        st.markdown(html_news,unsafe_allow_html=True)

    # EarningsWhispers
    with c2:
        st.header("Last Earnings")
        ew=get_earnings_data(ticker)
        if isinstance(ew,str):st.error(ew)
        else:
            block="<div class='earnings-box'>"+"".join([f"<div><strong>{k}</strong>: {v}</div>" for k,v in ew.items()])+"</div>"
            st.markdown(block,unsafe_allow_html=True)

    # Zacks EPS
    st.header("Historische Earnings")
    d1,d2=st.columns([1,1])
    df_eps=get_zacks_eps_yoy(ticker)
    with d1:
        st.dataframe(df_eps)
    with d2:
        st.subheader("EPS Veränderung % (YoY)")
        fig,ax=plt.subplots(figsize=(4,2))
        ax.plot(df_eps["Quarter"],df_eps["YoY Change %"],marker="o")
        ax.set_ylabel("Change %",fontsize=8);ax.set_xlabel("Quarter",fontsize=8)
        ax.tick_params(labelsize=8);ax.grid(True);plt.xticks(rotation=45)
        st.pyplot(fig)

    st.markdown(f"[→ Earnings auf Seeking Alpha](https://seekingalpha.com/symbol/{
