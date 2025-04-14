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

# Ampel: Trendanzeige für QQQ EMA9 vs EMA21
qqq = yf.download("QQQ", period="3mo", interval="1d")
qqq["EMA9"] = qqq["Close"].ewm(span=9).mean()
qqq["EMA21"] = qqq["Close"].ewm(span=21).mean()
ampel = "🔴"
if (
    qqq["EMA9"].iloc[-1] > qqq["EMA21"].iloc[-1]
    and qqq["EMA9"].iloc[-1] > qqq["EMA9"].iloc[-2]
    and qqq["EMA21"].iloc[-1] > qqq["EMA21"].iloc[-2]
):
    ampel = "🟢"
st.markdown(f"""
<style>
.ampel-box {{
    position: absolute;
    top: 18px;
    left: 10px;
    font-size: 64px;
    line-height: 1;
    z-index: 10;
}}
form {{
    margin-left: 80px;
}}
</style>
<div class='ampel-box'>{ampel}</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
h1, .block-title, .matplot-title, .stHeader, .stMarkdown h2, .stMarkdown h3 {
    font-size: 1.5rem !important;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("Aktienanalyse")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben", "")
    submitted = st.form_submit_button("Daten abrufen")

# (restlicher Code bleibt gleich...)
