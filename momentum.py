import streamlit as st
from playwright.sync_api import sync_playwright
import yfinance as yf
import re

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_selector("#epssummary", timeout=90000)

            raw_date = page.inner_text("#epsdate").strip()
            earnings_text = page.inner_text("#epssummary").strip()

            # **Korrekte Extraktion aus der Summary**
            earnings_growth_match = re.search(r"Earnings Growth.*?([-+]?\d{1,3}(?:,\d{1,3})*(?:\.\d+)?%)", earnings_text)
            revenue_growth_match = re.search(r"Revenue Growth.*?([-+]?\d{1,3}(?:,\d{1,3})*(?:\.\d+)?%)", earnings_text)
            earnings_surprise_match = re.search(r"Earnings Surprise.*?([-+]?\d{1,3}(?:,\d{1,3})*(?:\.\d+)?%)", earnings_text)

            earnings_growth = earnings_growth_match.group(1) if earnings_growth_match else "N/A"
            revenue_growth = revenue_growth_match.group(1) if revenue_growth_match else "N/A"
            earnings_surprise = earnings_surprise_match.group(1) if earnings_surprise_match else "N/A"

            # **Short Ratio über yfinance abrufen**
            try:
                stock = yf.Ticker(ticker)
                short_ratio = stock.info.get("shortRatio", "N/A")
                short_ratio = round(float(short_ratio), 2) if short_ratio != "N/A" else "N/A"
            except:
                short_ratio = "N/A"

            # **Datumsformatierung**
            date_match = re.search(r"([A-Za-z]+) (\d+), (\d+)", raw_date)
            if date_match:
                month, day, year = date_match.groups()
                months = {
                    "January": "01", "February": "02", "March": "03", "April": "04",
                    "May": "05", "June": "06", "July": "07", "August": "08",
                    "September": "09", "October": "10", "November": "11", "December": "12"
                }
                formatted_date = f"{day}/{months[month]}/{year[2:]}"  # Kürze Jahr auf 2 Stellen
            else:
                formatted_date = "N/A"

            # **Finale Formatierung**
            formatted_output = f"{formatted_date}\nEG: {earnings_growth} / RG: {revenue_growth}\nES: {earnings_surprise}\nSR: {short_ratio}"

        except Exception as e:
            formatted_output = f"N/A\nEG: Error / RG: Error\nES: Error\nSR: {short_ratio}"

        browser.close()

    return formatted_output


# **Dark Mode Styling für die gesamte Seite**
st.markdown(
    """
    <style>
    body {
        background-color: #121212;
        color: #E0E0E0;
    }
    .stApp {
        background-color: #121212;
        color: #E0E0E0;
    }
    h1 {
        color: #ffffff;
    }
    .stTextInput>div>div>input {
        background-color: #1E1E1E;
        color: #E0E0E0;
        border-radius: 5px;
    }
    .stButton>button {
        background-color: #ff9800;
        color: white;
        border-radius: 5px;
        font-weight: bold;
    }
    .stTextArea>div>textarea {
        background-color: #1E1E1E;
        color: #FFD700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Hanabi Scraper")
ticker = st.text_input("Enter stock ticker:")
if st.button("Fetch Data"):
    data = get_earnings_data(ticker)
    st.text_area("Earnings Data", data)
