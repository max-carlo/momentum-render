import yfinance as yf
from playwright.sync_api import sync_playwright

def get_earnings_data(ticker):
    """Scrapt die Earnings-Daten von Earnings Whispers mit Playwright."""
    url = f"https://www.earningswhispers.com/stocks/{ticker.lower()}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, timeout=60000)  # 60 Sekunden Timeout
            page.wait_for_selector("table.earnings-table", timeout=30000)

            # Beispiel: Extrahieren der ersten Tabellenzeile
            earnings_data = page.inner_text("table.earnings-table")

        except Exception as e:
            earnings_data = f"Error fetching earnings: {e}"

        finally:
            browser.close()
    
    return earnings_data


def get_short_ratio(ticker):
    """Holt die Short Ratio von der Yahoo Finance API mit yfinance."""
    try:
        stock = yf.Ticker(ticker)
        short_ratio = stock.info.get("shortRatio", "N/A")  # Fallback, falls nicht vorhanden
        return short_ratio
    except Exception as e:
        return f"Error fetching short ratio: {e}"


if __name__ == "__main__":
    ticker = "AAPL"  # Testticker

    earnings = get_earnings_data(ticker)
    short_ratio = get_short_ratio(ticker)

    print(f"Earnings Data for {ticker}:\n{earnings}\n")
    print(f"Short Ratio for {ticker}: {short_ratio}")
