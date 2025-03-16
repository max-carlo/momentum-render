#!/bin/bash
pip install -r requirements.txt
export PLAYWRIGHT_BROWSERS_PATH=/app/.cache/playwright
npx playwright install --with-deps chromium
streamlit run momentum.py --server.port=10000 --server.address=0.0.0.0
python momentum.py