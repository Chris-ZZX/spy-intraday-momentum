"""Download and prepare the notebook dataset; run explicitly from the project root."""
import os
import json
from io import StringIO
from pathlib import Path
from getpass import getpass

import pandas as pd
import requests
import pandas_market_calendars as mcal

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.corporate_actions import CorporateActionsClient
from alpaca.data.requests import StockBarsRequest, CorporateActionsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment


# ================= USER CONFIGURATION =================

API_KEY = ""  # Use environment variables or the existing getpass prompt.
API_SECRET = ""  # Use environment variables or the existing getpass prompt.

DATA_START = "2016-01-04"
ANALYSIS_START = "2016-03-01"     # Earlier observations are used for warm-up.
TRAIN_END = "2021-12-31"
END_DATE = "2024-04-30"

# Find the project root when launched from the root or notebooks directory.
_cwd = Path.cwd().resolve()
PROJECT_ROOT = next(
    (p for p in (_cwd, _cwd.parent)
     if (p / "notebooks").is_dir() and (p / "README.md").is_file()),
    _cwd,
)
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass  # Environment variables and getpass also work without python-dotenv.

_default_data = PROJECT_ROOT / "data" if (PROJECT_ROOT / "notebooks").is_dir() else PROJECT_ROOT
_data_setting = Path(os.getenv("SPY_DATA_DIR", str(_default_data))).expanduser()
SAVE_DIR = (
    _data_setting if _data_setting.is_absolute()
    else PROJECT_ROOT / _data_setting
).resolve()
RUN_DOWNLOADS = os.getenv("SPY_RUN_DOWNLOADS", "0").lower() in {"1", "true", "yes"}

OVERWRITE = False               # Set to True to refresh cached data.

# ======================================================

SYMBOL = "SPY"
NY = "America/New_York"
CACHE_DIR = SAVE_DIR / "alpaca_cache"




def save_csv(df, path):
    """Write to a temporary file before replacing the destination."""
    temp = path.with_suffix(".tmp")
    df.to_csv(temp, index=False, encoding="utf-8-sig")
    temp.replace(path)


def normalize_bars(df):
    """Standardize timestamps and numeric fields, then validate the bars."""
    df = df.copy()

    df["timestamp"] = pd.to_datetime(df.timestamp, utc=True)
    df["date"] = (
        df.timestamp.dt.tz_convert(NY)
        .dt.strftime("%Y-%m-%d")
    )
    df = df.sort_values("timestamp").reset_index(drop=True)

    if df.timestamp.duplicated().any():
        raise ValueError("Duplicate bar timestamps detected.")

    numeric = [
        "open", "high", "low", "close",
        "volume", "vwap", "trade_count",
    ]
    df[numeric] = df[numeric].apply(
        pd.to_numeric, errors="raise"
    )

    if df[numeric].isna().any().any() or df.volume.le(0).any():
        raise ValueError("Missing values or non-positive volume detected.")

    if df[
        ["open", "high", "low", "close", "vwap"]
    ].le(0).any().any():
        raise ValueError("Non-positive prices detected.")

    return df




def fetch_bars(client, schedule, timeframe, adjustment, tag):
    """Download bars in monthly batches with automatic SDK pagination."""
    frames = []

    for month, part in schedule.groupby(
        schedule.index.to_period("M")
    ):
        first = part.index[0].strftime("%Y-%m-%d")
        last = part.index[-1].strftime("%Y-%m-%d")

        # Include the requested date range in each cache filename.
        path = CACHE_DIR / (
            f"{SYMBOL}_sip_{tag}_{first}_{last}.csv"
        )

        if path.exists() and not OVERWRITE:
            batch = pd.read_csv(path)
            print(f"{tag} {month}: loaded from cache")

        else:
            req = StockBarsRequest(
                symbol_or_symbols=SYMBOL,
                timeframe=timeframe,

                # Midnight is required to include the first daily bar.
                start=pd.Timestamp(
                    first, tz=NY
                ).to_pydatetime(),

                end=(
                    part.market_close.iloc[-1]
                    - pd.Timedelta(microseconds=1)
                ).to_pydatetime(),

                feed="sip",
                adjustment=adjustment,

                # Do not cap the total number of bars across all pages.
                limit=None,
            )

            batch = client.get_stock_bars(req).df

            if batch.empty:
                raise RuntimeError(
                    f"{tag} {month}: no bars returned by the API."
                )

            batch = batch.reset_index()
            save_csv(batch, path)

            print(
                f"{tag} {month}: downloaded {len(batch):,} bars"
            )

        frames.append(batch)

    return normalize_bars(
        pd.concat(frames, ignore_index=True)
    )




def fetch_actions(client):
    """Download corporate actions and filter by their effective ex-dates."""
    # The endpoint filters by process_date rather than ex_date.
    # Query a broad processing window before applying the local ex-date filter.
    today = pd.Timestamp.now(tz="UTC").date()

    path = CACHE_DIR / (
        f"{SYMBOL}_actions_1993_{today}.json"
    )

    if path.exists() and not OVERWRITE:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )

    else:
        payload = client.get_corporate_actions(
            CorporateActionsRequest(
                symbols=[SYMBOL],
                start=pd.Timestamp("1993-01-01").date(),
                end=today,
                limit=None,
            )
        )

        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    records = []

    for kind, items in payload.items():
        if isinstance(items, list):
            records.extend(
                dict(item, action_group=kind)
                for item in items
            )

    actions = pd.DataFrame(records)

    if actions.empty or "ex_date" not in actions:
        raise RuntimeError(
            "No SPY corporate actions retrieved. "
            "Missing dividend data must not be treated as zero."
        )

    actions["ex_date"] = pd.to_datetime(
        actions.ex_date, errors="raise"
    ).dt.strftime("%Y-%m-%d")

    actions = actions.loc[
        actions.ex_date.between(DATA_START, END_DATE)
    ].copy()

    if "id" in actions:
        actions = actions.drop_duplicates("id")

    dividends = actions.loc[
        actions.action_group.eq("cash_dividends")
    ].copy()

    if dividends.empty:
        raise RuntimeError(
            "No SPY cash dividends retrieved for the selected period."
        )

    dividends["rate"] = pd.to_numeric(
        dividends.rate, errors="raise"
    )

    dividends = dividends.rename(
        columns={
            "ex_date": "date",
            "rate": "dividend",
        }
    ).sort_values("date")

    # Preserve split-related records for subsequent adjustment checks.
    splits = actions.loc[
        actions.action_group.isin([
            "forward_splits",
            "reverse_splits",
            "unit_splits",
            "stock_dividends",
        ])
    ].copy()

    return actions, dividends, splits




def fetch_vix():
    """Download official daily VIX observations from Cboe."""
    url = (
        "https://cdn-api.cboe.com/api/global/"
        "us_indices/daily_prices/VIX_History.csv"
    )

    path = CACHE_DIR / (
        f"VIX_{DATA_START}_{END_DATE}.csv"
    )

    if path.exists() and not OVERWRITE:
        return pd.read_csv(path, dtype={"date": str})

    response = requests.get(url, timeout=(10, 60))
    response.raise_for_status()

    vix = pd.read_csv(StringIO(response.text))
    vix.columns = vix.columns.str.strip().str.lower()

    vix["date"] = pd.to_datetime(
        vix.date,
        format="%m/%d/%Y",
        errors="raise",
    ).dt.strftime("%Y-%m-%d")

    vix = vix.loc[
        vix.date.between(DATA_START, END_DATE)
    ].copy()

    if vix.empty or vix.date.duplicated().any():
        raise ValueError("Empty VIX data or duplicate dates detected.")

    cols = ["open", "high", "low", "close"]
    vix[cols] = vix[cols].apply(
        pd.to_numeric, errors="raise"
    )

    if (
        vix[cols].isna().any().any()
        or vix[cols].le(0).any().any()
    ):
        raise ValueError("Missing or non-positive VIX values detected.")

    vix = vix.sort_values("date").reset_index(drop=True)
    save_csv(vix, path)

    return vix




def prepare_minutes(raw, calendar):
    """Filter regular trading hours and calculate two cumulative VWAPs."""
    df = raw.merge(
        calendar[
            ["date", "market_open", "market_close", "split"]
        ],
        on="date",
        how="inner",
        validate="many_to_one",
    )

    # The calendar handles holidays, early closes, and daylight saving time.
    df = df.loc[
        df.timestamp.ge(df.market_open)
        & df.timestamp.lt(df.market_close)
    ].copy().sort_values("timestamp").reset_index(drop=True)

    if df.empty:
        raise ValueError("No minute bars within regular trading hours.")

    df["timestamp_ny"] = df.timestamp.dt.tz_convert(NY)

    # Bar timestamps identify the beginning of each minute.
    # The completed bar becomes available after the corresponding minute ends.
    df["bar_end_ny"] = (
        df.timestamp_ny + pd.Timedelta(minutes=1)
    )

    df["minute_since_open"] = (
        (df.timestamp - df.market_open)
        .dt.total_seconds() / 60
    ).astype(int)

    df = df.rename(columns={"vwap": "vwap_minute"})

    df["hlc3"] = (
        df.high + df.low + df.close
    ) / 3

    # Estimate traded dollar volume using Alpaca's minute VWAP.
    df["dollar_volume"] = df.vwap_minute * df.volume
    df["hlc3_volume"] = df.hlc3 * df.volume

    groups = df.groupby("date", sort=False)
    cum_volume = groups.volume.cumsum()

    # Cumulative VWAP based on the provider's minute trade VWAP.
    df["vwap_sip"] = (
        groups.dollar_volume.cumsum() / cum_volume
    )

    # Cumulative HLC3-based VWAP used in the authors' public Python example.
    df["vwap_paper"] = (
        groups.hlc3_volume.cumsum() / cum_volume
    )

    quality = calendar[
        ["date", "split", "expected_minutes"]
    ].copy()

    quality["downloaded_minutes"] = (
        quality.date.map(df.groupby("date").size())
        .fillna(0)
        .astype(int)
    )

    quality["missing_minutes"] = (
        quality.expected_minutes
        - quality.downloaded_minutes
    )

    first = df.groupby("date").timestamp.min()
    last = df.groupby("date").timestamp.max()

    quality["has_open_bar"] = (
        quality.date.map(first).eq(calendar.market_open)
    )

    quality["has_close_bar"] = (
        quality.date.map(last).eq(
            calendar.market_close
            - pd.Timedelta(minutes=1)
        )
    )

    # Leave missing minutes unfilled.
    return (
        df.drop(
            columns=[
                "market_open",
                "market_close",
                "hlc3_volume",
            ]
        ),
        quality,
    )




def prepare_daily(
    raw, adjusted, dividends, actions, vix, calendar
):
    """Combine daily prices, dividends, lagged volatility, and lagged VIX."""
    for frame in [raw, adjusted]:
        if frame.date.duplicated().any():
            raise ValueError("Duplicate daily dates detected.")

    daily = calendar[["date", "split"]].merge(
        raw[
            ["date", "open", "high", "low", "close", "volume"]
        ],
        on="date",
        how="left",
        validate="one_to_one",
    )

    daily = daily.merge(
        adjusted[["date", "close"]].rename(
            columns={"close": "adjusted_close"}
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )

    price_cols = [
        "open", "high", "low", "close", "adjusted_close"
    ]

    if daily[price_cols].isna().any().any():
        raise ValueError(
            "At least one session is missing raw or adjusted daily prices."
        )

    # Flag adjustment-factor changes without corresponding corporate actions.
    # Do not infer or fabricate dividend amounts from price changes.
    factor = daily.adjusted_close / daily.close

    changed = daily.loc[
        factor.pct_change(
            fill_method=None
        ).abs().gt(0.0001),
        "date",
    ]

    missing = sorted(
        set(changed) - set(actions.ex_date)
    )

    if missing:
        raise RuntimeError(
            "Adjustment-factor changes have no corresponding "
            f"corporate-action records on: {missing}. "
            "Downloaded bars remain cached. "
            "Complete the corporate-action data before proceeding."
        )

    div_by_day = dividends.groupby("date").dividend.sum()

    daily["dividend"] = (
        daily.date.map(div_by_day).fillna(0.0)
    )

    daily["prev_close_raw"] = daily.close.shift(1)

    daily["prev_close_ex_dividend"] = (
        daily.prev_close_raw - daily.dividend
    )

    daily["return_raw"] = daily.close.pct_change(
        fill_method=None
    )

    daily["return_adjusted"] = (
        daily.adjusted_close.pct_change(
            fill_method=None
        )
    )

    # Use only the previous 14 completed daily returns for position sizing.
    daily["vol14_lagged"] = (
        daily.return_raw
        .rolling(14)
        .std(ddof=1)
        .shift(1)
    )

    daily = daily.merge(
        vix[["date", "close"]].rename(
            columns={"close": "vix_close"}
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )

    # Today's closing VIX is unavailable at today's market open.
    # Use the previous trading day's closing VIX for an opening-time filter.
    daily["vix_prev_close"] = daily.vix_close.shift(1)

    return daily




def download_project_data():
    if not (
        DATA_START
        <= ANALYSIS_START
        <= TRAIN_END
        < END_DATE
    ):
        raise ValueError(
            "Download, warm-up, training, and test dates are inconsistent."
        )

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    schedule = mcal.get_calendar("NYSE").schedule(
        DATA_START, END_DATE
    )

    if schedule.empty:
        raise ValueError("No trading sessions in the selected period.")

    # Restrict requests to completed historical sessions.
    # A 20-minute buffer accommodates delayed historical SIP access.
    cutoff = (
        pd.Timestamp.now(tz="UTC")
        - pd.Timedelta(minutes=20)
    )

    if schedule.market_close.iloc[-1] > cutoff:
        raise ValueError(
            "The final session must have closed at least 20 minutes ago."
        )

    calendar = schedule.reset_index(names="session_date")

    calendar["date"] = (
        calendar.session_date.dt.strftime("%Y-%m-%d")
    )

    calendar["expected_minutes"] = (
        (calendar.market_close - calendar.market_open)
        .dt.total_seconds() / 60
    ).astype(int)

    # Apply a chronological split without shuffling observations.
    calendar["split"] = "test"
    calendar.loc[
        calendar.date.le(TRAIN_END), "split"
    ] = "train"
    calendar.loc[
        calendar.date.lt(ANALYSIS_START), "split"
    ] = "warmup"

    # Read credentials from configuration, environment variables, or prompts.
    key = (
        API_KEY.strip()
        or os.getenv("APCA_API_KEY_ID", "").strip()
        or getpass("Alpaca API Key ID: ").strip()
    )

    secret = (
        API_SECRET.strip()
        or os.getenv("APCA_API_SECRET_KEY", "").strip()
        or getpass("Alpaca Secret Key: ").strip()
    )

    if not key or not secret:
        raise ValueError("Both API Key and Secret Key are required.")

    stock = StockHistoricalDataClient(key, secret)

    # Raw responses preserve all available corporate-action fields.
    ca_client = CorporateActionsClient(
        key, secret, raw_data=True
    )

    minute_raw = fetch_bars(
        stock,
        schedule,
        TimeFrame.Minute,
        Adjustment.RAW,
        "1min_raw",
    )

    daily_raw = fetch_bars(
        stock,
        schedule,
        TimeFrame.Day,
        Adjustment.RAW,
        "daily_raw",
    )

    daily_adjusted = fetch_bars(
        stock,
        schedule,
        TimeFrame.Day,
        Adjustment.ALL,
        "daily_all",
    )

    actions, dividends, splits = fetch_actions(ca_client)
    vix = fetch_vix()

    minutes, quality = prepare_minutes(
        minute_raw, calendar
    )

    daily = prepare_daily(
        daily_raw,
        daily_adjusted,
        dividends,
        actions,
        vix,
        calendar,
    )

    if quality.downloaded_minutes.eq(0).any():
        raise RuntimeError(
            "At least one trading session has no minute bars. "
            "Check the cached data."
        )

    outputs = {
        "SPY_1min.csv": minutes,
        "SPY_daily_raw.csv": daily_raw,
        "SPY_daily_adjusted.csv": daily_adjusted,
        "SPY_dividends.csv": dividends,
        "SPY_splits.csv": splits,
        "SPY_corporate_actions.csv": actions,
        "VIX_daily.csv": vix,
        "NYSE_calendar.csv": calendar,
        "SPY_daily_features.csv": daily,
        "quality_report.csv": quality,
    }

    for name, frame in outputs.items():
        save_csv(frame, SAVE_DIR / name)

    # Record dataset settings and quality summaries without credentials.
    config = {
        "symbol": SYMBOL,
        "feed": "sip",
        "data_start": DATA_START,
        "analysis_start": ANALYSIS_START,
        "train_end": TRAIN_END,
        "end_date": END_DATE,

        "downloaded_at_utc": (
            pd.Timestamp.now(tz="UTC").isoformat()
        ),

        "minute_rows": len(minutes),

        "missing_minute_days": int(
            quality.missing_minutes.gt(0).sum()
        ),

        "vix_missing_days": int(
            daily.vix_close.isna().sum()
        ),

        "vwap_paper": (
            "cumulative HLC3 * volume / "
            "cumulative volume, RTH only"
        ),

        "vix_signal": (
            "previous trading day's daily close"
        ),
    }

    (SAVE_DIR / "project_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"\nCompleted: {len(minutes):,} minute bars "
        f"across {len(daily):,} trading sessions."
    )
    print("Output directory:", SAVE_DIR.resolve())
    print(
        "Sessions with missing minute bars:",
        config["missing_minute_days"],
    )

    return minutes, daily, quality




if __name__ == "__main__":
    minutes, daily_features, quality = download_project_data()
