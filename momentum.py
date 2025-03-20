import streamlit as st
from playwright.sync_api import sync_playwright
import re

# Setzt das Design mit einem dunklen Hintergrund
st.markdown(
    """
    <style>
    body {
        background-color: #000000;
        color: #ffffff;
    }
    .stTextInput, .stTextArea, .stButton>button {
        background-color: #222222;
        color: #ffffff;
        border-radius: 8px;
        font-size: 16px;
    }
    .stTextInput>div>div>input {
        color: #ffffff;
    }
    .stButton>button {
        background-color: #ff007f;
        color: white;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
    }
    .stButton>button:hover {
        background-color: #ff4500;
    }
    h1 {
        color: #ff007f;
        text-align: center;
        font-size: 36px;
    }
    .stTextArea textarea {
        background-color: #111111;
        color: #33ffcc;
        font-size: 16px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        earnings_summary = "N/A"  

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)  
            page.wait_for_selector("#epssummary", timeout=90000)  
            earnings_summary = page.inner_text("#epssummary")  
        except Exception as e:
            earnings_summary = f"Error: {e}"

        browser.close()

    return earnings_summary

def format_earnings_data(raw_data):
    try:
        # Datum extrahieren
        date_match = re.search(r"ended (\w+ \d+, \d+)", raw_data)
        date = date_match.group(1) if date_match else "N/A"

        # Werte extrahieren
        earnings_match = re.search(r"earnings of \$([\d.]+)", raw_data)
        revenue_match = re.search(r"revenue of \$([\d.]+)", raw_data)
        growth_match = re.search(r"revenue grew ([\d.]+)%", raw_data)
        miss_match = re.search(r"missed expectations by ([\d.]+)%", raw_data)

        earnings = earnings_match.group(1) if earnings_match else "N/A"
        revenue = revenue_match.group(1) if revenue_match else "N/A"
        growth = growth_match.group(1) if growth_match else "N/A"
        earnings_surprise = miss_match.group(1) if miss_match else "N/A"

        # Datumsformat anpassen (Monat -> Tag/Monat/Jahr)
        from datetime import datetime
        try:
            formatted_date = datetime.strptime(date, "%B %d, %Y").strftime("%d/%m/%y")
        except ValueError:
            formatted_date = "N/A"

        # Formatierte Ausgabe
        formatted_output = f"""
        🎆 **{formatted_date}** 🎆
        **EG:** {earnings}% / **RG:** {growth}%
        **ES:** {earnings_surprise}%
        **SR:** N/A
        """

    except Exception as e:
        formatted_output = f"Error: {e}"

    return formatted_output

# Titel der App
st.markdown("<h1>Hanabi Scraper 🎇</h1>", unsafe_allow_html=True)

# Eingabefeld ohne Platzhalter
ticker = st.text_input("🔍 Enter stock ticker:", "")

if st.button("🚀 Fetch Data"):
    raw_data = get_earnings_data(ticker)
    formatted_data = format_earnings_data(raw_data)
    st.text_area("📊 Earnings Data", formatted_data, height=150)
