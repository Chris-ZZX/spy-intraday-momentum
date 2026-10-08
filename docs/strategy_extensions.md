# Original strategy extensions and their status

| Extension | Weakness addressed | Mechanism | Observed status |
|---|---|---|---|
| ER entry filter | Choppy path despite a band breach | Gate new entries using a 30-minute efficiency ratio | Validation selects no additional filtering |
| LSTM risk allocation | State-dependent daily risk | Prior 20-session sequence -> bounded allocation | Lower test risk; no higher test Sharpe |
| TCN / Ridge entry filter | Weak or unprofitable breakout candidates | Predict net hypothetical-trade return using 30-minute sequences | TCN selects All entries; Ridge test Sharpe is lower |
| Persistence confirmation | Fleeting breakout | Require 1, 3 or 5 consecutive qualifying completed minutes | Pending full-SPY execution |
| Intraday shock control | Stale prior-day volatility estimate | Compare cumulative variance with the same minute in prior sessions | Pending full-SPY execution |
| Causal gap handling | Retrospective exclusion of incomplete days | Halt after a detected missing minute, retain earlier trades, liquidate at next available reference | Implemented in the pending engine; requires a common-policy baseline |
| Cost stress and constant-risk control | False improvements from lower exposure or cheap execution | Freeze selection and compare ablations under 1x, 2x, 5x costs | Pending full-SPY execution |

## Persistence confirmation

At an existing half-hour decision, a new long side requires each of the preceding m completed closes to exceed its own contemporaneous upper band and VWAP. Short confirmation is symmetric. Missing minutes and session boundaries break a streak.

Confirmation gates a new side only. Original exits remain unchanged, and a rejected reversal closes the existing side. Use validation Sharpe to choose from m in {1, 3, 5}; break ties toward the smaller m and include m=1 as a no-change control.

## Intraday shock control

Start returns at the actual session open to exclude the overnight gap:

$$
RV_{t,\tau}=\sum_{k=1}^{\tau}
\left[\log(C_{t,k}/C_{t,k-1})\right]^2,
$$

where the first denominator is the session opening price. Compare with a 14-session, same-minute historical median H. Shift the date panel before the rolling median:

$$
g_{t,\tau}=\min(1,\sqrt{H_{t,\tau}/RV_{t,\tau}}).
$$

The multiplier can recover toward one, but it never exceeds the original risk budget. It updates only at the existing decision times. Missing/nonpositive references leave the multiplier at one and must be counted in availability diagnostics.

## Required experiment order

1. Verify that m=1, shock control off and legacy data handling reproduce the saved volatility-sized engine when rerun on the actual dataset.
2. Select confirmation using validation only.
3. Freeze a constant multiplier estimated only from development data.
4. Replay original logic, confirmation, shock control, combined and constant-risk variants under the same causal gap policy.
5. Compare development, validation and historical test using a common calendar.
6. Freeze all choices and rerun the complete equity/share path at commission/slippage multipliers 1, 2 and 5.

This is a predefined ablation study. Faster reaction can still miss profitable trends, and smaller positions can reduce both drawdown and return. A cost multiplier is a sensitivity scenario, not a calibrated market-impact model.
