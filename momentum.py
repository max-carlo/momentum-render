import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
from datetime import datetime

# Finviz News
def scrape_finviz_news(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}&p=d"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ))
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

# Zacks Earnings Calendar
def scrape_zacks_earnings(ticker):
    url = f"https://www.zacks.com/stock/research/{ticker}/earnings-calendar"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ))
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
        except Exception as e:
            browser.close()
            return pd.DataFrame([["Fehler beim Laden der Zacks-Seite", "", "", "", ""]],
                                columns=["Date", "Period", "Surprise", "% Surprise", "YoY"])
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table#earnings_announcements_earnings_table tr.odd, table#earnings_announcements_earnings_table tr.even")

    if not rows:
        return pd.DataFrame([["Keine Datenzeilen gefunden", "", "", "", ""]],
                            columns=["Date", "Period", "Surprise", "% Surprise", "YoY"])

    data = []
    for row in rows[:8]:
        cells = row.find_all(["th", "td"])
        if len(cells) == 7:
            data.append([c.text.strip() for c in cells])

    df = pd.DataFrame(data, columns=["Date", "Period", "Estimate", "Reported", "Surprise", "% Surprise", "Time"])

    # Vorjahres-Wachstum berechnen
    df["YoY"] = ""
    for i in range(len(df)):
        curr_period = df.loc[i, "Period"]
        try:
            curr_val = float(df.loc[i, "Reported"].replace("$", ""))
            for j in range(i + 1, len(df)):
                if df.loc[j, "Period"] == curr_period:
                    prev_val = float(df.loc[j, "Reported"].replace("$", ""))
                    growth = round((curr_val - prev_val) / abs(prev_val) * 100, 2)
                    df.loc[i, "YoY"] = f"{growth}%"
                    break
        except:
            df.loc[i, "YoY"] = "N/A"

    return df[["Date", "Period", "Surprise", "% Surprise", "YoY"]]

# EarningsWhispers
def get_earnings_data(ticker):
    url = f"https://www.earningswhispers.com/epsdetails/{ticker}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
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

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d/%m/%y %I:%M %p")
    except:
        formatted_date = "N/A"

    def clean(text):
        return re.sub(r"[^\d\.\-%]", "", text).replace(",", "") if text else "N/A"

    def signed(text):
        return f"-{clean(text)}" if "-" in text else clean(text)

    eg = clean(earnings_growth)
    rg = clean(revenue_growth).replace("%%", "%")
    es = signed(earnings_surprise)
    rs = signed(revenue_surprise)

    try:
        info = yf.Ticker(ticker).info
        sr = info.get("shortRatio", "N/A")
        sr = str(round(sr, 2)) if isinstance(sr, (float, int)) else "N/A"
    except:
        sr = "N/A"

    return f"{formatted_date}\nEG: {eg}% / RG: {rg}\nES: {es} / RS: {rs}\nSR: {sr}"

# Streamlit UI
st.set_page_config(layout="wide")
st.title("📈 Hanabi Market Scraper")

with st.form("main_form"):
    ticker = st.text_input("Ticker eingeben (z. B. AAPL)", "")
    submitted = st.form_submit_button("Daten abrufen")

if submitted and ticker:
    ticker = ticker.strip().upper()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"📰 Finviz News zu {ticker}")
        news = scrape_finviz_news(ticker)
        if isinstance(news, list):
            for i, (time, title, url, source) in enumerate(news):
                style = "background-color: #000000; color: white;" if i % 2 == 0 else "background-color: #f0f0f0; color: black;"
                st.markdown(
                    f"<div style='padding:6px; font-size:13px; line-height:1.4; {style}'>"
                    f"<strong>{time}</strong> – <a href='{url}' target='_blank'>{title}</a> ({source})"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.error(news)

    with col2:
        st.subheader(f"📅 Aktuelle Earnings zu {ticker} (EarningsWhispers)")
        result = get_earnings_data(ticker)
        st.text_area("Earnings Summary", result, height=180)

    st.subheader(f"📊 Zacks Earnings History für {ticker}")
    df = scrape_zacks_earnings(ticker)
    st.dataframe(df, use_container_width=True)
