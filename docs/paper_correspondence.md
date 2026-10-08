# Correspondence with the paper

| Notebook section | Paper location | What is implemented | Saved output |
|---|---|---|---|
| 1: Data | Section 2, p. 6 | Minute OHLCV, regular-hours calendar, raw/adjusted daily observations, VIX and corporate actions | 814,246 minute bars; 2,095 sessions; eight sessions with missing bars |
| 2: Noise area | Section 3, pp. 6-8 | Prior 14-session mean absolute open-to-minute move and overnight-gap-adjusted upper/lower anchors | 769,813 minute observations with available bounds |
| 3: Opposite band | Section 3, pp. 9-11 | Half-hour decisions, opposite-band exit, end-of-session liquidation and linear costs | Test CAGR 11.26%, volatility 10.17%, Sharpe 1.100 |
| 4: Current band + VWAP | Section 3, pp. 12-14 | Explicit long/short/flat target; tighter current-band and VWAP exit | Test CAGR 12.96%, volatility 7.15%, Sharpe 1.740 |
| 5: Volatility sizing | Section 3, pp. 14-15 | Prior 14-return sample standard deviation; 2% daily target; maximum 4x exposure; integer shares | Test CAGR 30.04%, volatility 13.49%, Sharpe 2.015 |
| 7-9: ER / LSTM / TCN / Ridge | Original research | Entry filtering or pre-session risk allocation | Model-selection and test tables |
| 11: Persistence and shock control | Original research, pending | Consecutive confirmation, same-time intraday variance reference, causal gap handling, ablation and cost stress | No saved full-SPY results |

## The two volatility quantities

The band width is the mean absolute movement from the open at the same intraday minute:

$$
a_{t,\tau}=\frac1{14}\sum_{i=1}^{14}
\left|\frac{C_{t-i,\tau}}{O_{t-i}}-1\right|.
$$

It is not a standard deviation. The daily sizing variable is a sample standard deviation of the previous 14 completed daily returns. Both use lagged data, but they estimate different quantities.

## Exits and allocation

The current-band/VWAP direction is +1 above both upper band and VWAP, -1 below both lower band and VWAP, and zero otherwise, at permitted decision times. Initial sizing is based on session-start equity and the opening price:

$$
Q_t=\left\lfloor
\frac{E_{t-1}\min(4,0.02/\widehat\sigma_t)}{O_t}
\right\rfloor.
$$

The 2% target sets the planned SPY notional risk; it does not guarantee that the strategy's realized daily volatility is 2%.

## Comparable statements and differences

The paper reports final full-sample CAGR 19.6%, volatility 14.3%, Sharpe 1.33 and maximum drawdown 25%. The notebook's 2022-2024 test is shorter and has Sharpe 2.015. These are different samples and vendors, so the numerical difference does not establish a superior replication.

Other implementation differences:

- The notebook's completed signal bar executes at the next minute open, plus adverse linear slippage; the closing reference is a preplanned end-of-session liquidation proxy.
- Session VWAP uses cumulative HLC3 times volume, a specified bar-based convention.
- The boundary anchor uses raw previous close, while passive returns use adjusted daily prices.
- Fixed commission is 0.0035 dollars/share; the source paper also discusses volume-related commission discounts.
- The saved engines keep incomplete sessions in cash after a retrospective full-session quality check. This can use future knowledge of the day's eventual completeness and is not a causal live rule.
- Pending Section 11 changes the missing-data policy. Its new original-rule control must be used for fair comparisons.
- Financing, stock borrow, execution latency and size-dependent market impact are not fully modeled.

## Paper investigations not implemented here

The notebook does not provide the paper's full opening-VIX regime study, eight daily-pattern tests, weekday t-statistics, RSI/Gamma proxy regression, market alpha/beta significance study or calibrated I-Star market-impact analysis. The LSTM's VIX input is an original feature, not a reproduction of those investigations.
