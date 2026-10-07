# Reproduction and saved-output provenance

## Two ways to review the project

**Read the saved study:** open `Strategy.ipynb`, the README, and `results/`. The notebook includes figures and statistics. `scripts/export_saved_results.py` reads the saved outputs without executing notebook code and needs only the Python standard library.

**Recompute the study:** obtain the requested market data, install the notebook's dependencies, and execute the cells in order. This requires external data access and training the models again. The repository does not contain raw price data or trained checkpoints.

## Environment

The supplied notebook records Python **3.11.9**. `requirements.txt` lists its direct third-party imports plus JupyterLab. The original package versions were not saved, so this is a dependency list rather than a historical lock file. Numerical or API differences across installed versions can change a new run; no exact-version reproduction is claimed.

Create a virtual environment and install the requirements from the repository root. Start JupyterLab in that directory so `Path.cwd()` resolves to the project root. On a new machine, choose the virtual environment's Python kernel.

The data downloader reads credentials in this order:

1. Notebook `API_KEY` / `API_SECRET` constants, both empty in this repository.
2. Environment variables `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`.
3. Interactive `getpass` prompts.

No `.env` loader is implemented. A `.env` file alone will not populate the process environment. Interactive prompts are sufficient; avoid entering keys into a committed notebook cell.

## Data preparation

The source uses Alpaca's SIP feed for SPY minute bars, raw daily bars and fully adjusted daily bars, plus corporate actions. It fetches Cboe daily VIX and uses `pandas_market_calendars` for the NYSE schedule. Your data account must support the requested historical feed and corporate-action endpoints.

You can run the notebook's data section, or run its CLI wrapper:

```bash
python scripts/download_data.py
```

The wrapper executes the same nine annotated data cells, then calls their existing `download_project_data()` function. It does not maintain a second implementation of the API requests or transformations. Its default output directory is the repository root. For a separate data folder:

```bash
python scripts/download_data.py --output-dir /absolute/path/to/data
```

For that alternative, update the notebook's `SAVE_DIR` and `DATA_DIR` consistently before using the files. `--refresh` sets `OVERWRITE=True` for cached bar downloads; it is not a guarantee that every external endpoint has identical historical revisions.

The download section produces:

| File | Content |
| --- | --- |
| `SPY_1min.csv` | Regular-session minute prices, volume and VWAP fields |
| `SPY_daily_raw.csv` | Raw daily bars |
| `SPY_daily_adjusted.csv` | Fully adjusted daily bars |
| `SPY_dividends.csv` | Dividend records |
| `SPY_splits.csv` | Split records |
| `SPY_corporate_actions.csv` | Corporate-action records |
| `VIX_daily.csv` | Daily VIX observations |
| `NYSE_calendar.csv` | Trading schedule, expected minutes and split labels |
| `SPY_daily_features.csv` | Aligned daily prices, returns and research features |
| `quality_report.csv` | Session-level data completeness |
| `project_config.json` | Download settings and quality summaries, without credentials |

`alpaca_cache/` stores monthly bar-request results. `OVERWRITE=False` reuses those cached bars. Other endpoint requests can still run when repeating the data section. If the CSVs are already prepared by the CLI, begin the notebook at **Noise area construction**, after the data-download section, to avoid downloading twice.

The imported download output reports **814,246 minute rows**, **2,095 calendar sessions** including warm-up, and **8 sessions with missing minute bars**. These are historical saved logs, not counts rechecked against a bundled dataset. Sessions with no bars or missing required daily prices trigger errors; incomplete minute grids are handled by the retrospective cash-day rule described in [METHODS.md](METHODS.md).

## Execution order and checks

| Stage | Required state | Saved check / output |
| --- | --- | --- |
| Data preparation | External data access | Calendar and quality reports |
| Noise area | Prepared minute/daily/calendar CSVs | Missing-bound audit |
| Opposite band baseline | `minute_features` | Daily P&L, order ledger and metrics |
| VWAP enhancement | Baseline state and minute VWAP | Opposite-mode comparison |
| Volatility target | VWAP strategy and lagged daily volatility | Fixed-1× regression check passed |
| ER filter | Original volatility-target state | Zero-threshold baseline check passed |
| LSTM allocation | Daily features and original per-share P&L | All-ones daily replay check passed |
| TCN/Ridge filter | Original state and minute volume | Unfiltered TCN replay check passed |
| Final comparison | Replayed original and filtered returns | Common-calendar assertions and six-strategy table |

All these statements describe the source notebook's saved checks. The repository build did not repeat the market-data backtest. Reexecuting cells out of order can reuse stale variables; use a fresh kernel for a full reproduction.

## Refresh the exported materials

After running and saving the notebook:

```bash
python scripts/export_saved_results.py
```

The exporter expects the supplied annotated notebook's current table and figure layout. It checks expected row/figure counts and fails if the saved layout no longer matches. If you add/remove cells, rename strategies or change printed table formats, update the exporter accordingly.

The script regenerates eight CSV tables, twelve images, model selections, source parameters and provenance. It does not rewrite README tables or prose. Update those descriptions if a new run changes the reported results.

## Result precision and provenance

Metrics in the CSVs are parsed from printed console tables. Percentage fields become decimal fractions, e.g. `30.04%` becomes `0.3004`; Sharpe remains dimensionless. CSV precision is limited by the original formatting. These are not full-precision return series and cannot reconstruct the equity curves. Images are decoded directly from the notebook's saved PNG outputs.

`results/provenance.json` records the copied notebook's SHA-256, format, cell counts, execution-counter coverage, saved error cells and figure source indices. `config/research_config.json` records top-level parameters read from source; it is a reference snapshot, not a runtime configuration file. Editing that JSON does not change notebook behavior.

The supplied notebook has **47 of 62 code cells with execution counters**. Saved outputs alongside missing counters do not prove a clean, single-kernel full run. A new complete execution is the way to establish that on another environment. No package lock or model checkpoint was available from the supplied file.
