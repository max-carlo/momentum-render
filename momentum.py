import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
import yfinance as yf

# 📌 Finviz News
def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
        except Exception as e:
            browser.close()
            return [f"Fehler beim Laden der Finviz-Seite: {e}"]
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table.fullview-news-outer tr")

    news_items = []
    for row in rows:
        time_cell = row.find("td", width="130")
        link_tag = row.find("a", class_="tab-link-news")
        source = row.find("span")
        if time_cell and link_tag and source:
            time = time_cell.text.strip()
            title = link_tag.text.strip()
            url = link_tag["href"]
            src = source.text.strip("()")
            news_items.append((time, title, url, src))

    return news_items[:15]

# 📌 TradingView Earnings Data
def scrape_tradingview_eps(ticker):
    url = f"https://www.tradingview.com/symbols/{ticker}/financials-earnings/?earnings-period=FQ&revenues-period=FQ"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US")
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)  # Give JS time to render
            html = page.content()
        except Exception as e:
            with open("tradingview_error.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            browser.close()
            return pd.DataFrame([[f"Fehler beim Laden der TradingView-Seite: {e}", "", "", ""]],
                                columns=["Quarter", "Reported EPS", "Estimate EPS", "Surprise"])
        browser.close()

    soup = BeautifulSoup(html, "html.parser")

    quarters = [div.text.strip() for div in soup.select('div[class*="title-C9MdAMrq"] span.titleText-C9MdAMrq') if "Reported" not in div.text]
    reported = [div.text.strip() for div in soup.select('div[data-name="Reported"] div.value-OxVAcLqi')]
    estimates = [div.text.strip() for div in soup.select('div[data-name="Estimate"] div.value-OxVAcLqi')]
    surprises = [div.text.strip() for div in soup.select('div[data-name="Surprise"] div.value-OxVAcLqi')]

    length = min(len(quarters), len(reported), len(estimates), len(surprises))
    data = []
    for i in range(length):
        data.append([quarters[i], reported[i], estimates[i], surprises[i]])

    return pd.DataFrame(data, columns=["Quarter", "Reported EPS", "Estimate EPS", "Surprise"])

# 📌 EarningsWhispers
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("#epsdate", timeout=60000)
            earnings_date = page.inner_text("#epsdate")
            earnings_surprise = page.inner_text("#earnings .surprise")
            earnings_growth = page.inner_text("#earnings .growth")
            revenue_growth = page.inner_text("#revenue .growth")
            revenue_surprise = page.inner_text("#revenue .surprise")
        except Exception as e:
            return f"Fehler beim Laden der Earnings-Seite: {e}"
        browser.close()

    def clean(text):
        return re.sub(r"[^\d\.\-%]", "", text).replace(",", "") if text else "N/A"

    def signed(text):
        return f"-{clean(text)}" if "-" in text else clean(text)

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")
    except:
        formatted_date = "N/A"

    eg = clean(earnings_growth).rstrip("%")
    rg = clean(revenue_growth).rstrip("%")
    es = signed(earnings_surprise)
    rs = signed(revenue_surprise)

    try:
        info = yf.Ticker(ticker).info
        sr = info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (float, int)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg}% / RG: {rg}%\nES: {es} / RS: {rs}\nSR: {sr}"

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
            for i, (time, title, url, source) in enumerate(news):
                bg = "#f0f0f0" if i % 2 else "white"
                news_html += (
                    f"<div style='padding:6px; font-size:13px; background-color:{bg}; line-height:1.4;'>"
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

    st.subheader(f"📊 TradingView Earnings für {ticker}")
    df = scrape_tradingview_eps(ticker)
    st.dataframe(df, use_container_width=True)
