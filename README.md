# SPY Intraday Momentum: Replication and Research Extensions

[中文说明](README.zh-CN.md)

Reproduce the main intraday momentum pipeline in Zarattini, Aziz and Barbon's *Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)*, then evaluate entry filters and learned risk allocation on the same trading calendar and cost assumptions.

**The saved test results favor the paper-based volatility-target strategy.** The LSTM reduces volatility and drawdown but also lowers CAGR and Sharpe. Validation selects no filtering for ER and TCN, so their test curves coincide with the volatility-target baseline. These outcomes are part of the research findings.

## Start with the notebook

Open [Strategy.ipynb](Strategy.ipynb) to inspect the code, formulas, saved statistics and figures. It is an unchanged copy of the latest supplied notebook: **128 cells, 62 code cells, 66 Markdown cells and 12 embedded figures**. Its metadata records Python **3.11.9**. The preceding Markdown cells explain each code block and distinguish paper methods from project extensions.

The repository contains saved research outputs. It was assembled without downloading market data or rerunning the backtests/model training. Some cells have saved outputs but no execution counter; see [provenance.json](results/provenance.json).

## What is implemented

| Component | Role |
| --- | --- |
| Noise-area breakout | Paper-based baseline using the previous 14 sessions at the same intraday time |
| Band + VWAP | Paper-based stop enhancement with the notebook's explicit long/short/flat convention |
| Daily volatility targeting | Paper-based position sizing, 2% daily target and 4× leverage cap |
| Efficiency Ratio (ER) | Project experiment: gate new entries using a 30-minute path measure |
| LSTM risk allocation | Project experiment: scale daily risk using 20 prior sessions and 8 features |
| TCN return filter | Project experiment: predict net breakout opportunity returns from 30-minute sequences |
| Ridge filter | Linear control using the same features and targets as TCN |
| SPY buy & hold | Benchmark based on adjusted daily returns |

[Method equations and paper correspondence](docs/METHODS.md) · [Reproduction details](docs/REPRODUCIBILITY.md)

## Saved test results

**2022–2024-04-30, 584 trading sessions.** Values below are the notebook's rounded console outputs. CAGR is geometric; Sharpe uses 252 sessions/year and a zero risk-free rate. Strategy results include the modeled commission and slippage.

| Strategy / control | Total return | CAGR | Annual volatility | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Opposite band | 28.05% | 11.26% | 10.17% | 1.100 | −8.93% |
| Band + VWAP | 32.63% | 12.96% | 7.15% | 1.740 | −4.67% |
| **Band + VWAP + Vol target** | **83.80%** | **30.04%** | **13.49%** | **2.015** | **−9.95%** |
| Vol target + ER filter | 83.80% | 30.04% | 13.49% | 2.015 | −9.95% |
| LSTM risk allocation | 51.05% | 19.48% | 9.26% | 1.969 | −7.59% |
| Ridge return filter | 57.26% | 21.58% | 11.37% | 1.775 | −7.11% |
| TCN return filter | 83.80% | 30.04% | 13.49% | 2.015 | −9.95% |
| Constant 50% allocation | 36.25% | 14.28% | 6.74% | 2.015 | −5.06% |
| Constant matched allocation | 43.36% | 16.82% | 7.87% | 2.015 | −5.89% |
| SPY buy & hold | 9.37% | 3.94% | 18.60% | 0.301 | −24.50% |

The matched constant uses the LSTM's **development-period** mean allocation of 58.39%. Its test Sharpe also exceeds the LSTM's, so lower drawdown alone does not establish an advantage from learned allocation.

![Paper stages, Ridge and TCN across development, validation and test](assets/complete_equity.png)

The final six-strategy figure above omits ER and LSTM. [LSTM equity/control comparison](assets/lstm_equity.png), [LSTM allocation](assets/lstm_allocation.png) and [ER comparison](assets/er_equity.png) are provided separately. The TCN and volatility-target curves overlap because TCN's selected threshold is **All entries**.

## Research setup

| Setting | Notebook value |
| --- | --- |
| Data / warm-up starts | 2016-01-04 / analysis starts 2016-03-01 |
| Paper train period | 2016-03-01 through 2021-12-31 |
| Extension development / validation | Through 2020-12-31 / calendar year 2021 |
| Historical test | After 2021-12-31 through 2024-04-30 |
| Sources | Alpaca SIP SPY bars/corporate actions; Cboe daily VIX; NYSE calendar |
| Initial capital | $100,000 |
| Per execution costs | $0.0035 commission + $0.001 adverse slippage per share |
| Timing | Completed-bar signals at :00/:30; next-minute-open fills; flat at session close |

Development, validation and test contain 1,220, 252 and 584 sessions respectively. Validation selects ER threshold **0**, LSTM epoch **80**, TCN epoch **5**, TCN threshold **All entries**, and Ridge threshold **2 bp**. See [selected models](results/selected_models.json) and [source parameters](config/research_config.json).

## Run locally

Use Python 3.11, matching the notebook's recorded environment. From the repository root:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m jupyterlab
```

Open `Strategy.ipynb` and execute its cells in order. The download section reads `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`, or asks for them using `getpass`. Credentials can remain blank in the notebook. The account must have access to the historical SIP data requested by the code. Downloaded CSVs and the cache are created in the working directory and excluded by `.gitignore`.

Optional commands:

```bash
# Run the same notebook downloader from the CLI:
python scripts/download_data.py
# Re-export saved tables/figures; no credentials or third-party packages needed:
python scripts/export_saved_results.py
```

Full data preparation, cache reuse, missing-minute handling and dependency limitations are described in [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md). To publish this folder, see [上传步骤](docs/UPLOAD.md).

## Repository contents

- `Strategy.ipynb` — primary implementation and explanation.
- `docs/` — method correspondence, reproduction notes and upload instructions.
- `results/` — eight CSV tables, model selections and notebook provenance.
- `assets/` — all twelve original saved figures.
- `config/research_config.json` — reference parameters extracted from notebook source.
- `scripts/` — data-download wrapper and offline output exporter.

## Interpretation limits

This implements the paper's main strategy stages on a different sample and data source; it does not claim to reproduce the paper's full 2007–2024 results. VWAP is approximated from minute HLC3, fills use next-minute opens, and the VWAP variant explicitly requires both the band and VWAP condition for entry. Full-day completeness checks use information available after the session; their retrospective cash-day policy needs redesign for a live simulation. Financing, stock-borrow fees and market impact are not modeled.

The code separates fitting/selection from the historical test, but this project has already inspected that test. The saved results therefore support comparison on this sample, not a claim of prospectively validated profitability. Exact original package versions, raw data and trained checkpoints are not included.

Reference: Carlo Zarattini, Andrew Aziz and Andrea Barbon (2025), *Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)*, manuscript dated February 3, 2025.
