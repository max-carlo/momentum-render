import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
from datetime import datetime

# 📌 Finviz News
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

# 📌 Zacks Earnings
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
    rows = soup.select("table#earnings_announcements_earnings_table tr.odd, tr.even")

    if not rows:
        return pd.DataFrame([["Keine Datenzeilen gefunden", "", "", "", ""]],
                            columns=["Date", "Period", "Surprise", "% Surprise", "YoY"])

    data = []
    for row in rows:
        cells = row.find_all(["th", "td"])
        if len(cells) == 7:
            date = cells[0].text.strip()
            period = cells[1].text.strip()
            reported = cells[3].text.strip().replace("$", "")
            surprise = cells[4].text.strip()
            surprise_pct = cells[5].text.strip()
            data.append([date, period, reported, surprise, surprise_pct])

    df = pd.DataFrame(data, columns=["Date", "Period", "Reported", "Surprise", "% Surprise"])

    # Berechne YoY-Wachstum auf Basis der Perioden
    df["YoY"] = ""
    period_map = {row["Period"]: float(row["Reported"]) for _, row in df.iterrows() if row["Reported"].replace(".", "", 1).isdigit()}
    for idx, row in df.iterrows():
        period = row["Period"]
        if re.match(r"\d{1,2}/\d{4}", period):
            month, year = period.split("/")
            last_year = str(int(year) - 1)
            compare_period = f"{month}/{last_year}"
            if compare_period in period_map:
                current = float(row["Reported"])
                previous = period_map[compare_period]
                if previous != 0:
                    growth = round((current - previous) / abs(previous) * 100, 2)
                    df.at[idx, "YoY"] = f"{growth}%"

    return df[["Date", "Period", "Surprise", "% Surprise", "YoY"]]

# 📌 EarningsWhispers
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

    st.subheader(f"📊 Zacks Earnings History für {ticker}")
    df = scrape_zacks_earnings(ticker)
    st.dataframe(df, use_container_width=True)

    # 📈 Earnings Change %
    if "YoY" in df.columns:
        chart_data = df[["Period", "YoY"]].dropna()
        chart_data = chart_data[chart_data["YoY"].str.endswith("%")]
        if not chart_data.empty:
            chart_data["YoY"] = chart_data["YoY"].str.replace("%", "").astype(float)
            chart_data = chart_data[::-1]
            st.line_chart(chart_data.set_index("Period"))
