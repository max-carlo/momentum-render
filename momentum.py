def get_earnings_history(ticker):
    url = f"https://seekingalpha.com/symbol/{ticker}/earnings"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=90000)

        try:
            st.write("🔍 Warte auf Earnings-Tabelle...")  # Debugging

            # Warte auf die Tabelle (90 Sek. Timeout)
            page.wait_for_selector("table[data-test-id='table']", timeout=90000)

            st.write("✅ Earnings-Tabelle gefunden!")  # Debugging

            rows = page.query_selector_all("table[data-test-id='table'] tbody tr")

            if not rows:
                raise Exception("Keine Tabellenzeilen gefunden!")

            earnings_data = []
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) < 6:
                    continue

                period = row.query_selector("th").inner_text().strip()
                eps = cols[0].inner_text().strip()
                eps_beat_miss = cols[1].inner_text().strip()
                revenue = cols[2].inner_text().strip()
                yoy_growth = cols[3].inner_text().strip()
                revenue_beat_miss = cols[4].inner_text().strip()

                earnings_data.append(f"{period}: EPS {eps} ({eps_beat_miss}), Revenue {revenue} ({revenue_beat_miss}), YoY: {yoy_growth}")

            browser.close()

            return "\n".join(earnings_data) if earnings_data else "⚠️ Keine Earnings-Daten gefunden."

        except Exception as e:
            browser.close()
            return f"❌ Fehler beim Laden der Earnings-History: {e}"
