# Saved result files

These files were extracted from `Strategy.ipynb` without executing its code. Return, volatility and drawdown columns use **decimal fractions**. Sharpe is dimensionless, counts are integers, and threshold values labeled `bps` use basis points. Empty Sharpe cells correspond to printed `NaN` for all-cash portfolios.

| File | Rows | Purpose |
| --- | ---: | --- |
| `paper_train_test.csv` | 8 | Three paper stages and SPY benchmark, train/test |
| `er_train_test.csv` | 10 | Original stages, ER filter and benchmark, train/test |
| `lstm_periods.csv` | 15 | Original strategy, LSTM, two fixed-allocation controls and benchmark |
| `tcn_periods.csv` | 12 | Original strategy, Ridge, TCN and benchmark |
| `complete_periods.csv` | 18 | Three original stages, Ridge, TCN and benchmark |
| `test_summary.csv` | 10 | Distinct strategies and controls on the 584-session test period |
| `er_validation_thresholds.csv` | 4 | ER threshold selection and costs |
| `return_filter_validation_thresholds.csv` | 8 | TCN/Ridge threshold selection |

`selected_models.json` records the saved selections. `provenance.json` records source notebook properties, SHA-256 and figure origins. `source_cell_index` is the zero-based position in the notebook's `cells` list.

The performance tables retain the rounded precision displayed in the source. Validation selection tables evaluate standalone portfolios starting from initial capital; later period tables use the continuous-history replay, so small integer-rounding differences are expected. In particular, do not replace the final validation CAGR of 27.29% with the standalone threshold-selection figure of 27.27%.

`test_summary.csv` combines six rows from `complete_periods.csv`, the ER row from `er_train_test.csv`, and the LSTM/two control rows from `lstm_periods.csv`. It preserves each row's source index and introduces no synthetic strategy returns.

Refresh these files and figures with `python scripts/export_saved_results.py` after saving an executed notebook. See [reproduction instructions](../docs/REPRODUCIBILITY.md) for limitations.
