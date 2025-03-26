import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import yfinance as yf
import re
from datetime import datetime
import matplotlib.pyplot as plt

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
        value = clean(text).lstrip("-")
        return f"-{value}" if "-" in text and value else value

    try:
        dt = datetime.strptime(earnings_date.replace(" at", "").replace(" ET", "").split(", ", 1)[-1], "%B %d, %Y %I:%M %p")
        formatted_date = dt.strftime("%d.%m.%Y %H:%M")
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

    return f"{formatted_date}\nEarnings Growth: {eg}%\nRevenue Growth: {rg}%\nEarnings Surprise: {es}\nRevenue Surprise: {rs}\nShort Ratio: {sr}"

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
            return pd.DataFrame([['Fehler beim Laden', '', '', '', '', '']], columns=["Datum", "Periode", "Earnings", "Earnings YoY", "Revenue YoY", "Earnings Surprise"])
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table#earnings_announcements_earnings_table tr.odd, tr.even")

    data = []
    earnings_map = {}
    revenue_map = {}

    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 7:
            date_str = cells[0].text.strip()
            try:
                date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%d.%m.%Y")
            except:
                date = date_str

            period = cells[1].text.strip()
            earnings = cells[3].text.strip().replace("$", "")
            surprise = cells[4].text.strip()
            earnings_map[period] = float(earnings) if earnings.replace('.', '', 1).isdigit() else None

            revenue_tag = cells[6].text.strip()
            revenue_match = re.search(r'Revenues\\s*:\\s*\\$(\\d+\\.?\\d*)', revenue_tag)
            revenue = revenue_match.group(1) if revenue_match else None
            revenue_map[period] = float(revenue) if revenue else None

            data.append([date, period, earnings, surprise, revenue])

    df = pd.DataFrame(data, columns=["Datum", "Periode", "Earnings", "Earnings Surprise", "Revenue"])
    df["Earnings YoY"] = ""
    df["Revenue YoY"] = ""

    for i, row in df.iterrows():
        period = row["Periode"]
        if re.match(r"\d{1,2}/\d{4}", period):
            month, year = period.split("/")
            last_year = f"{month}/{int(year) - 1}"

            if earnings_map.get(period) and earnings_map.get(last_year):
                prev = earnings_map[last_year]
                curr = earnings_map[period]
                if prev:
                    df.at[i, "Earnings YoY"] = round((curr - prev) / abs(prev) * 100, 2)

            if revenue_map.get(period) and revenue_map.get(last_year):
                prev_r = revenue_map[last_year]
                curr_r = revenue_map[period]
                if prev_r:
                    df.at[i, "Revenue YoY"] = round((curr_r - prev_r) / abs(prev_r) * 100, 2)

    return df

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
