# SPY Intraday Momentum: Replication and Original Research

A chronological Python research project implementing the paper's time-of-day noise bands, breakout rules, current-band/VWAP exits and volatility-based position sizing, then testing ER, LSTM, TCN and Ridge extensions.

**Main observed result:** the saved 2022-2024 historical test supports the tighter exit and dynamic sizing, but none of the completed original extensions improves on the dynamic baseline's Sharpe. The persistence and intraday shock-control code is present but has **no saved full-SPY results**.

![Historical-test metrics](results/saved/figures/13_test_metrics_overview.png)

## Saved historical-test results

3 January 2022-30 April 2024, 584 trading sessions; daily net returns, 252 sessions/year and zero risk-free rate.

| Strategy | CAGR | Annual volatility | Sharpe | Maximum drawdown |
|---|---:|---:|---:|---:|
| Opposite-band baseline | 11.26% | 10.17% | 1.100 | -8.93% |
| Current band + VWAP | 12.96% | 7.15% | 1.740 | -4.67% |
| Band + VWAP + volatility sizing | 30.04% | 13.49% | 2.015 | -9.95% |
| ER, selected threshold 0 | 30.04% | 13.49% | 2.015 | -9.95% |
| LSTM risk allocation | 19.48% | 9.26% | 1.969 | -7.59% |
| Ridge, selected threshold 2 bp | 21.58% | 11.37% | 1.775 | -7.11% |
| TCN, selected All entries | 30.04% | 13.49% | 2.015 | -9.95% |
| SPY buy and hold | 3.94% | 18.60% | 0.301 | -24.50% |

These are reported saved results, not results from a new full-SPY run during packaging. The original CSVs and fitted weights were not supplied. Rounded statistics and the 12 original figures are preserved under `results/saved`; the overview figure is rebuilt from those statistics. See [evidence provenance](results/saved/provenance.json).

## Open and understand the project

- [Research notebook](notebooks/SPY_Intraday_Momentum.ipynb)
- [Read-only HTML notebook](docs/notebook_preview.html): download and open locally to see all saved outputs.
- [Paper correspondence](docs/paper_correspondence.md)
- [Results and model interpretation](docs/results_interpretation.md)
- [Pending experiments](docs/strategy_extensions.md)
- [Data schema and execution assumptions](data/README.md)
- [Validation record](docs/validation.md)

Sections 0-5 implement the data pipeline and paper-inspired strategies. Sections 6-9 introduce the research protocol and completed original experiments. Section 10 consolidates observed evidence, Section 11 defines pending experiments, and Section 12 states conclusions and limitations.

## Installation

Use Python 3.11. The source notebook reports Python 3.11.9, but it does not record exact dependency versions. These requirement files list direct dependencies rather than claiming an original locked environment.

~~~bash
python -m venv .venv
~~~

Activate the environment on Windows:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

Or on macOS/Linux:

~~~bash
source .venv/bin/activate
~~~

Install the notebook and paper-stage dependencies:

~~~bash
python -m pip install -r requirements.txt
~~~

For LSTM, TCN and Ridge, additionally install:

~~~bash
python -m pip install -r requirements-models.txt
~~~

## Data and execution

Put your existing project CSVs in `data/`. Alternatively, set `SPY_DATA_DIR` to their absolute directory. The essential input names are `SPY_1min.csv`, `SPY_daily_features.csv` and `NYSE_calendar.csv`.

To request and prepare data explicitly, copy `.env.example` to `.env`, enter your Alpaca credentials locally, then run from the repository root:

~~~bash
python scripts/download_data.py
~~~

The downloader retains the source project's 2016-2024 date settings, SIP feed request and monthly caches. Your data account must authorize the requested feed/history. Source data, private credentials and fitted weights are not bundled.

Run only the replicated paper stages:

~~~bash
python scripts/run_notebook.py --stage paper --data-dir data
~~~

Run the completed model experiments as well:

~~~bash
python scripts/run_notebook.py --stage models --data-dir data
~~~

Include the pending persistence, risk-control, ablation and cost-grid experiments:

~~~bash
python scripts/run_notebook.py --stage all --data-dir data
~~~

The runner disables downloads, clears stale code outputs in its execution copy, and writes a fresh notebook, figures and console outputs to `results/generated/`. Original saved evidence stays separate. Notebook Section 10 can also be run independently: it displays an embedded saved snapshot if live strategy returns are unavailable.

## Verification

~~~bash
python -m pip install -r requirements-dev.txt
python scripts/validate_project.py
python -m pytest -q
~~~

Tests cover replay accounting, reversals, fixed-size equivalence, confirmation and causal gap handling using small synthetic fixtures. They do not measure profitability. The GitHub Actions workflow runs this offline verification; it does not download market data or train models.

## Upload to GitHub

Unzip the package and upload the **contents of this repository folder**, with `README.md` at the repository root. For a browser upload, use **Add file -> Upload files**. Upload the source folder contents rather than the ZIP archive.

With Git, run from the unpacked folder:

~~~bash
git init
git add .
git commit -m "Add SPY intraday momentum research project"
git branch -M main
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
~~~

Replace `YOUR_REPOSITORY_URL` with the URL of your repository. Local credentials, market data, caches and new fitted model files are excluded by `.gitignore`.

## Reference and scope

Zarattini, C., Aziz, A. and Barbon, A. (2025). *Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY).* Version 3 February 2025, Swiss Finance Institute research paper series 24-97.

The article's main sample is May 2007-April 2024 using IQFeed/Matlab. This project's analysis starts in March 2016 and uses Alpaca/Python. It reproduces the core signal/exit/sizing construction, not all VIX, weekday, technical-pattern, gamma or significance analyses. The reference PDF is not redistributed in the repository.

The historical test has already been inspected. Further modifications require a later untouched period to establish new evidence; the saved results are not a fresh blind test.
