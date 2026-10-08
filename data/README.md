# Local data inputs

Put the prepared project CSVs here, or set SPY_DATA_DIR to another directory. They are not redistributed with this repository.

| File | Required fields used by the notebook |
|---|---|
| SPY_1min.csv | timestamp, open, high, low, close, volume, split, vwap_paper; downloader also retains vwap_sip |
| SPY_daily_features.csv | date, split, open, high, low, close, volume, prev_close_raw, return_raw, return_adjusted, vix_close |
| NYSE_calendar.csv | date, market_open, market_close, expected_minutes, split |
| quality_report.csv | date, split, expected_minutes, downloaded_minutes, missing_minutes, has_open_bar, has_close_bar |

Supplementary downloader outputs are SPY_daily_raw.csv, SPY_daily_adjusted.csv, SPY_dividends.csv, SPY_splits.csv, SPY_corporate_actions.csv and VIX_daily.csv. It also writes project_config.json and monthly caches under alpaca_cache.

Timestamps are timezone-aware and minute timestamps identify the **start** of the bar. The completed close is available one minute later. The NYSE calendar controls regular hours, early closes and daylight-saving time. No missing minute price is forward-filled.

The source pipeline requests unadjusted minute prices. Daily features contain raw and fully adjusted prices, dividends and VIX. Signal anchors and risk estimates use raw observations; the passive benchmark uses adjusted daily returns.

With existing data, leave SPY_RUN_DOWNLOADS=0. When new data are needed, run scripts/download_data.py explicitly with locally supplied Alpaca credentials. The original historical sample settings are retained.
