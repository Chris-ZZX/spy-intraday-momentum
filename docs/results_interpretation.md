# Interpretation of the saved outputs

## Chronological evaluation

| Role | Dates | Saved sessions |
|---|---|---:|
| Warm-up | 4 January-29 February 2016 | Not included in performance |
| Development | 1 March 2016-31 December 2020 | 1,220 |
| Validation | Trading sessions in 2021 | 252 |
| Historical test | 3 January 2022-30 April 2024 | 584 |

The source CSV label `train` combines development and validation (1,472 sessions). Learned weights and preprocessing use development history, and validation selects checkpoints/thresholds. The article itself does not specify this machine-learning split.

The test period has already been inspected across experiments. A later untouched period is needed for a new blind evaluation.

## Core strategy sequence

The opposite-band exit waits too long during a reversal. Replacing it with a current-band/VWAP exit raises test Sharpe from 1.100 to 1.740, lowers volatility from 10.17% to 7.15%, and reduces maximum drawdown from 8.93% to 4.67%.

Dynamic sizing raises CAGR from 12.96% to 30.04%, alongside volatility of 13.49% and drawdown of 9.95%. This is a combined risk-allocation result, not evidence that the underlying entry signal changed.

The test is much more favorable than development: the dynamic baseline's development Sharpe is 0.669, versus 2.015 in test. The strong test number should therefore not be generalized to every market regime.

## ER: a rejected extra filter

The 30-minute efficiency ratio compares net displacement with total path movement. Higher values describe a more directional path.

Validation Sharpes are approximately 1.652, 1.383, 0.804 and -0.134 for thresholds 0, 0.2, 0.4 and 0.6. Validation selects zero. The saved full-calendar maximum difference from the unfiltered daily return series is 8.67e-19, so coincident curves are correct. The saved run does not support adding a positive ER threshold.

## LSTM: risk timing rather than price-direction forecasting

The LSTM consumes the preceding 20 sessions and eight daily features: one-day return, five-day return, range, candle body, 14-day volatility, relative volume, VIX level and VIX change. Today is excluded from the input window. A sigmoid allocation head produces a multiplier between zero and one applied to the original volatility-sized position.

Training minimizes negative net-return proxy Sharpe plus a soft allocation penalty. Validation selects epoch 80 and Sharpe about 1.805. The average allocation is 58.39% in development, 64.48% in validation and 67.41% in test.

In test, CAGR is 19.48%, volatility 9.26%, Sharpe 1.969 and maximum drawdown 7.59%. Risk falls, but the dynamic baseline Sharpe is 2.015. A constant 50% allocation has Sharpe about 2.015 and drawdown 5.06%; the frozen development-mean allocation has Sharpe about 2.015 and drawdown 5.89%. These controls prevent lower risk alone from being called superior timing skill.

## TCN and Ridge: predicting a hypothetical trade payoff

Both models see a direction-normalized 30-minute sequence with seven channels, including minute return, displacement from open, VWAP distance, band distance, relative volume, time and side. The label is the net payoff of a hypothetical entry at the next open, followed by an original-rule exit. Labels may overlap within a session.

The TCN selects epoch 5 by validation prediction loss, then the operational threshold is chosen by validation portfolio Sharpe. Every finite tested TCN threshold (0, 1 and 2 bp) admits zero validation trades; validation therefore selects All entries. Its test portfolio is the original strategy. A modest positive rank correlation does not overcome the model's negative prediction calibration in this run.

Ridge selects 2 bp. Its full-calendar validation Sharpe is approximately 1.743 versus 1.653 for the baseline. The threshold-selection replay starts with fresh validation capital, so its printed selection table is slightly different because integer-share rounding depends on the equity path. In test, Ridge Sharpe is 1.775 versus 2.015; CAGR is 21.58%, volatility 11.37%, and drawdown 7.11%.

Candidate diagnostics show test rank correlations of 0.0057 for Ridge and 0.0667 for TCN. Mean test forecasts are approximately 1.0701 and -5.5710 bp, versus mean hypothetical label 6.9564 bp. Ranking, calibration and realized portfolio performance are separate diagnostics.

## Pending additions

No saved full-SPY output exists for persistence, intraday shock control, their combination, the revised causal data-gap baseline or the 1x/2x/5x cost grid. Their formulas and code define experiments; they do not establish additional return or risk improvement.

## What was changed during packaging

The ending now separates consolidated evidence, paper correspondence, pending experiments and interpretation. ER and LSTM appear in the final overview. Original saved figures are retained, and one new metric overview is drawn from the printed statistics.

Data paths are portable, downloads are opt-in, local private path text is removed, and reusable replay functions plus execution/validation scripts are included. The original executed trading rules and saved numerical results are not rewritten as a new backtest.
