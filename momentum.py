import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
from datetime import datetime
import matplotlib.pyplot as plt

# ... (bestehende Funktionen bleiben unverändert)

# 📌 Streamlit UI
st.set_page_config(layout="wide")
st.title("📈 Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📰 Finviz News zu {ticker}")
        news = scrape_finviz_news(ticker)
        if isinstance(news, list):
            news_html = "<div style='max-height: 225px; overflow-y: auto;'>"
            for time, title, url, source in news:
                news_html += (
                    f"<div style='padding:6px; font-size:13px; background-color:white; color:black; line-height:1.4;'>"
                    f"<strong>{time}</strong> – <a href='{url}' target='_blank'>{title}</a> ({source})"
                    f"</div>"
                )
            news_html += "</div>"
            st.markdown(news_html, unsafe_allow_html=True)
        else:
            st.error(news)

    with col2:
        st.subheader(f"📅 Aktuelle Earnings zu {ticker} (EarningsWhispers)")
        result = get_earnings_data(ticker)
        st.text_area("Earnings Summary", result, height=225)

    st.subheader(f"📊 Zacks Earnings History für {ticker}")
    df = scrape_zacks_earnings(ticker)

    col3, col4 = st.columns([3, 2])
    with col3:
        st.dataframe(df, use_container_width=True)

    with col4:
        if not df.empty:
            df_plot = df.copy()
            df_plot = df_plot.sort_values("Periode")

            df_plot["Earnings YoY"] = pd.to_numeric(df_plot["Earnings YoY"], errors="coerce")
            df_plot["Revenue YoY"] = pd.to_numeric(df_plot["Revenue YoY"], errors="coerce")
            df_plot = df_plot.dropna(subset=["Earnings YoY", "Revenue YoY"], how="all")

            if not df_plot.empty:
                fig, ax = plt.subplots(figsize=(5, 3))
                if df_plot["Earnings YoY"].notna().any():
                    ax.plot(df_plot["Periode"], df_plot["Earnings YoY"], marker="o", label="Earnings YoY")
                if df_plot["Revenue YoY"].notna().any():
                    ax.plot(df_plot["Periode"], df_plot["Revenue YoY"], marker="x", label="Revenue YoY")
                ax.set_title("YoY Wachstum in %")
                ax.set_xlabel("Periode")
                ax.set_ylabel("Wachstum %")
                ax.legend()
                plt.xticks(rotation=45)
                st.pyplot(fig)
