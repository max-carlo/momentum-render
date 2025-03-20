import streamlit as st
from playwright.sync_api import sync_playwright

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
            earnings_summary = page.inner_text("#epssummary")
        except Exception as e:
            earnings_summary = f"Error: {e}"

        browser.close()

    return earnings_summary

# 🎨 Style-Anpassung für schwarzen Hintergrund
st.markdown(
    """
    <style>
        body {
            background-color: black;
            color: white;
        }
        input {
            background-color: #222;
            color: white;
            border-radius: 5px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Hanabi Scraper")

# 🎯 Streamlit-Form für "Enter"-Submit
with st.form(key="ticker_form"):
    ticker = st.text_input("Enter stock ticker:")
    submit_button = st.form_submit_button("Fetch Data")

# 🔎 Falls Enter gedrückt oder Button geklickt:
if submit_button and ticker:
    data = get_earnings_data(ticker)
    st.text_area("Earnings Data", data)
