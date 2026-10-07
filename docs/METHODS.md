# Method correspondence and implementation conventions

The notebook is the primary implementation. This document maps its stages to Zarattini, Aziz and Barbon (2025), then describes the project's additional experiments. Page numbers refer to the supplied February 3, 2025 manuscript's printed pages. Notebook cell indices below are **zero-based**, matching the CSV provenance fields; use the section titles when navigating Jupyter.

## 1. From data to the noise area

The paper describes SPY minute data and VIX in Section 2, p. 6. The notebook's data section (code cells 3–19) instead downloads Alpaca SIP minute bars, raw/adjusted daily prices, corporate actions and Cboe daily VIX. NYSE schedules supply regular-session boundaries, including early closes.

Only regular-session minutes enter the strategy. A source bar timestamp denotes the minute's start; `bar_end_ny` adds one minute. Missing prices are not forward-filled. HLC3 and volume provide a cumulative intraday VWAP approximation:

```math
\widetilde{VWAP}_{t,\tau}
=\frac{\sum_{u\le\tau}[(H_{t,u}+L_{t,u}+C_{t,u})/3]V_{t,u}}
{\sum_{u\le\tau}V_{t,u}}.
```

Section 3, pp. 6–8, defines typical absolute movement from the open at each intraday time. Code cells 21–27 implement a shift followed by a 14-session rolling mean on the **complete trading calendar**:

```math
\widehat{\sigma}^{noise}_{t,\tau}
=\frac{1}{14}\sum_{i=1}^{14}
\left|\frac{C_{t-i,\tau}}{O_{t-i}}-1\right|.
```

The quantity is a mean absolute move, not a return standard deviation. For volatility multiplier $m=1$, the overnight-gap anchors produce:

```math
UB_{t,\tau}=\max(O_t,C_{t-1})[1+m\widehat{\sigma}^{noise}_{t,\tau}],
```

```math
LB_{t,\tau}=\min(O_t,C_{t-1})[1-m\widehat{\sigma}^{noise}_{t,\tau}].
```

The implemented anchors use `prev_close_raw`. The separately calculated ex-dividend-adjusted previous close is not used for these bounds. A missing observation at a given clock time remains missing, including after historical early-close sessions. Cell 29 audits these cases.

## 2. Baseline decisions, fills and costs

Section 3, pp. 9–10, describes half-hour decisions, opposite-band exits/reversals and intraday-only positions. Code cells 31–41 implement this first stage. At eligible completed bars ending at :00 or :30 before the close:

```math
d_{t,\tau}=
\begin{cases}
+1, & C_{t,\tau}>UB_{t,\tau}, \\
-1, & C_{t,\tau}<LB_{t,\tau}, \\
d_{t,\tau^{-}}, & \text{inside the noise area}.
\end{cases}
```

Positions start flat each day. When the noise bounds are unavailable, the strategy selects a flat position.

Fixed-size daily shares are calculated as:

```math
Q_t=\left\lfloor\frac{E_{t-1}}{O_t}\right\rfloor
```

Here, the previous session's ending equity is divided by the current session's opening price and rounded down to an integer number of shares. The quantity remains fixed within that day.

The notebook evaluates completed-bar closes and uses the **next minute's open** as the fill reference. Final liquidation uses the last regular-session minute's close. These are explicit execution assumptions of this implementation.

For an order changing signed shares by $\Delta Q$, with reference price $P$, commission $c=0.0035$ and adverse slippage $s=0.001$ dollars/share:

```math
P^{fill}=P+\mathrm{sign}(\Delta Q)s,
\qquad Fee=c|\Delta Q|,
```

```math
\Delta Cash=-\Delta QP^{fill}-Fee.
```

A reversal from $+Q$ to $-Q$ trades $2Q$ shares and pays proportional costs on all of them. No financing, borrow fee, minimum commission or volume-dependent impact is added.

## 3. VWAP enhancement

The paper's VWAP stops appear on p. 13:

```math
Stop^{long}_{t,\tau}=\max(UB_{t,\tau},VWAP_{t,\tau}),
\qquad Stop^{short}_{t,\tau}=\min(LB_{t,\tau},VWAP_{t,\tau}).
```

Code cells 43–49 use the approximate VWAP above. The notebook operationalizes the rule by explicitly selecting a new direction at every decision:

```math
d_{t,\tau}=\begin{cases}
+1,&C_{t,\tau}>\max(UB_{t,\tau},\widetilde{VWAP}_{t,\tau}),\\
-1,&C_{t,\tau}<\min(LB_{t,\tau},\widetilde{VWAP}_{t,\tau}),\\
0,&\text{otherwise}.
\end{cases}
```

This applies VWAP to **entry eligibility as well as exits**; it is an explicit convention beyond simply quoting the paper's stop formulas. It also differs from the baseline's inside-band hold rule. Original fills and costs are preserved.

## 4. Daily volatility target

The paper's sizing enhancement appears on p. 15. Code cells 51–59 calculate the sample standard deviation of the prior 14 raw daily close-to-close returns, excluding the current session:

```math
\widehat{\sigma}^{daily}_t
=\mathrm{Std}_{ddof=1}(r_{t-14},\ldots,r_{t-1}),
\qquad \ell_t=\min\left(4,\frac{0.02}{\widehat{\sigma}^{daily}_t}\right),
```

```math
Q_t=\left\lfloor\frac{E_{t-1}\ell_t}{O_t}\right\rfloor.
```

An unavailable/nonpositive volatility estimate leads to a cash day. The daily wrapper uses an effective budget for share sizing and transfers only dollar P&L to actual equity; it does not create an artificial daily capital reset. Cell 55's saved output reports a passed fixed-1× regression check.

## 5. Chronological evaluation

The fixed paper rules need no model fitting. The project adds chronological evaluation for the experiments:

| Period | Purpose | Sessions |
| --- | --- | ---: |
| 2016-03-01 through 2020-12-31 | Development: fit learned models and preprocessing | 1,220 |
| 2021 | Validation: select checkpoints and entry thresholds | 252 |
| 2022 through 2024-04-30 | Historical test comparison | 584 |

The paper strategy's broader `train` table combines development and validation: 1,472 sessions. Development performance for fitted models is in-sample. The plots restart displayed equity at \$100,000 within each panel using already calculated daily returns; the underlying portfolio replay compounds through the evaluation history.

## 6. ER entry filter: rule-based experiment

Code cells 62–74 define the Efficiency Ratio on the most recent 30 completed minute closes:

```math
ER_{t,\tau}=
\frac{|C_{last}-C_{first}|}
{\sum_{u\in window}|C_u-C_{u-1}|}.
```

The filter accepts a new nonzero direction only when $ER\ge h$. Existing same-direction positions keep following the original exit logic. If a proposed reversal is rejected, the existing position closes; it is not retained through a rejected opposite signal.

Validation compares $h\in\{0,0.2,0.4,0.6\}$, requires at least 20 active days and selects the highest finite Sharpe, breaking ties in favor of the smaller threshold. The saved selection is **0**: zero rejected entries and a maximum daily-return difference of approximately $8.67\times10^{-19}$ from the baseline. Therefore the overlapping curves represent an inactive filter, not a plotting error.

## 7. LSTM daily risk allocation

Code cells 76–100 retain the original entry/exit strategy and learn a daily risk multiplier. Eight features describe prior returns, range, candle body, daily volatility, relative volume, VIX level and VIX change. A sequence contains **20 prior completed sessions**, excluding the trading day being sized. Development-only medians, means and standard deviations transform the inputs; scaled values are clipped to $[-5,5]$.

A one-layer LSTM with 16 hidden units and a sigmoid head gives $0<w_t<1$:

```math
w_t=\mathrm{sigmoid}(a^Th_{t-1}+b),
\qquad Q_t=\left\lfloor\frac{E_{t-1}\ell_tw_t}{O_t}\right\rfloor.
```

Training uses a differentiable net-return proxy before integer-share rounding:

```math
\mathcal L=-\sqrt{252}\frac{\mathrm{mean}(w_t\widetilde r_t)}
{\max[\mathrm{Std}(w_t\widetilde r_t),10^{-6}]}
+0.05\mathrm{mean}[(w_t-0.75)^2].
```

Validation replays integer shares and original per-share costs. The best validation portfolio Sharpe selects the checkpoint; the saved run selects **epoch 80** with printed Sharpe **1.805**. The all-ones replay check reports agreement with the volatility-target baseline.

Controls allocate a fixed 50%, or the LSTM's development-period mean **58.39%**. These controls separate the effect of lowering exposure from the effect of predicting risk. In the historical test, LSTM CAGR is **19.48%**, Sharpe **1.969** and max drawdown **−7.59%**, versus **30.04%**, **2.015** and **−9.95%** for the original volatility target.

## 8. TCN opportunity prediction and Ridge control

Code cells 102–122 build a 30-minute, seven-channel sequence ending at each nonzero breakout decision. Channels encode signed minute returns, movement from the open, VWAP/band distances, relative volume, time in session and trade direction. There can be overlapping candidate labels even while the original strategy is already holding a position; samples are not independent realized trades.

For direction $d$, next-open entry $P^{entry}$ and the exit under the unfiltered original direction logic:

```math
y=10^4\frac{d(P^{exit}-P^{entry})-2(c+s)}{P^{entry}}.
```

Labels end within the same session. Development-only channel imputation/scaling is clipped to $[-8,8]$. The causal TCN has three residual blocks, each with two left-padded kernel-3 convolutions, 16 channels and dilation 1, 2 or 4. Smooth-L1 validation prediction loss selects **epoch 5**. A Ridge regression with $\alpha=10$ sees the same flattened $30\times7$ inputs and targets.

For each model, validation selects an entry threshold from **All entries, 0 bp, 1 bp, 2 bp**, maximizing portfolio Sharpe with at least 20 active days. Scores gate new entries/reversals; they do not replace the original exits or sizing.

The saved TCN selects **All entries**, reproducing the baseline. Ridge selects **2 bp**; test CAGR is **21.58%**, Sharpe **1.775** and max drawdown **−7.11%**. Neither selection improves test Sharpe over the original volatility target. Candidate validation portfolios restart capital independently; integer-share rounding can cause small differences from the later continuous-history validation statistics.

## 9. Metrics and implementation boundaries

Code cell 35 defines daily-net-return metrics. With $N$ observations and normalized equity $W_0=1$, $W_t=\prod_{i=1}^{t}(1+r_i)$:

```math
TotalReturn=W_N-1,\qquad CAGR=W_N^{252/N}-1,
```

```math
Vol=\sqrt{252}\mathrm{Std}_{ddof=1}(r),
\qquad Sharpe=\sqrt{252}\frac{\mathrm{mean}(r)}{\mathrm{Std}_{ddof=1}(r)},
```

```math
MDD=\min_t\left(\frac{W_t}{\max_{0\le u\le t}W_u}-1\right).
```

Cash/no-trade days remain in the common calendar. The SPY benchmark uses adjusted daily returns, without modeled trading costs.

For session completeness, the current replay checks the entire day's minute grid before trading and makes incomplete-price sessions cash days. That check uses end-of-session information and is a **retrospective data-quality convention**. It is not a causal policy for handling an unexpected live feed outage. A future live-style test needs a missing-data policy applied as bars arrive and a fresh evaluation sample.

The repository preserves these choices and saved findings. It does not convert them into a claim of exact paper-table replication or newly verified out-of-sample improvement.

