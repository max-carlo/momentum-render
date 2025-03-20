import streamlit as st
from playwright.sync_api import sync_playwright
import re

def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        earnings_summary = "N/A"  # Initialisierung

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

        # Formatieren
        formatted_output = f"""{formatted_date}
EG: {earnings}% / RG: {growth}%
ES: {earnings_surprise}%
SR: N/A"""  # Short Ratio ist nicht aus der Earnings-Seite, daher "N/A"

    except Exception as e:
        formatted_output = f"Error: {e}"

    return formatted_output

st.title("Earnings Whispers Scraper")
ticker = st.text_input("Enter stock ticker:", "AAPL")
if st.button("Fetch Data"):
    raw_data = get_earnings_data(ticker)
    formatted_data = format_earnings_data(raw_data)
    st.text(formatted_data)  # Ausgabe im gewünschten Format
