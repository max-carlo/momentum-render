import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import yfinance as yf
import re
import requests
from playwright.sync_api import sync_playwright
import matplotlib.pyplot as plt
from streamlit.components.v1 import html

st.set_page_config(layout="wide")
st.title("Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

# Finhub Earnings (Hybrid-Methode)
def get_finhub_data(ticker, api_key):
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&token={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return pd.DataFrame([{"Hinweis": "Fehler beim Laden von Finhub"}])
    data = res.json()
    if not data:
        return pd.DataFrame([{"Hinweis": "Keine Finhub-Daten verfügbar"}])

    df = pd.DataFrame(data)
    df = df.sort_values("period").tail(8).copy()
    df["EPS Actual"] = pd.to_numeric(df["actual"], errors="coerce")
    df["EPS Change %"] = df["EPS Actual"].pct_change().round(2) * 100
    df.rename(columns={"period": "Quarter"}, inplace=True)
    return df[["Quarter", "EPS Actual", "EPS Change %"]]

# Anzeige
if submitted and ticker:
    ticker = ticker.strip().upper()

    st.header("Historische Earnings")
    api_key = "cvue2t9r01qjg1397ls0cvue2t9r01qjg1397lsg"
    finhub_df = get_finhub_data(ticker, api_key)
    if not finhub_df.empty and "EPS Actual" in finhub_df.columns:
        st.dataframe(finhub_df)

        st.subheader("EPS Veränderung % (Quartal über Quartal)")
        fig, ax = plt.subplots()
        ax.plot(finhub_df["Quarter"], finhub_df["EPS Change %"], marker="o")
        ax.set_ylabel("Change %")
        ax.set_xlabel("Quarter")
        ax.set_title("EPS Change % nach Quartal")
        ax.grid(True)
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.warning("Keine Finhub-Daten gefunden oder nicht genügend Daten für Change %.")
