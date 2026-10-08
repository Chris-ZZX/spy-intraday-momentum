"""Core replay engines extracted from the research notebook."""
import numpy as np
import pandas as pd

import pandas as pd

INITIAL_CASH = 100_000.0
COMMISSION_PER_SHARE = 0.0035
SLIPPAGE_PER_SHARE = 0.001




def backtest_baseline(
    features,
    trading_calendar,
    initial_cash=INITIAL_CASH,
    commission=COMMISSION_PER_SHARE,
    slippage=SLIPPAGE_PER_SHARE,
):
    """Backtest the opposite-band baseline using next-bar opens."""
    if initial_cash <= 0 or commission < 0 or slippage < 0:
        raise ValueError("Invalid cash or cost assumptions.")

    data = features.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()
    data["bar_end_ny"] = (
        pd.to_datetime(data["bar_end_ny"], utc=True)
        .dt.tz_convert("America/New_York")
    )
    data = data.sort_values(["date", "bar_end_ny"])

    if data["bar_end_ny"].duplicated().any():
        raise ValueError("Duplicate minute bars.")

    grouped = data.groupby("date", sort=False)

    sessions = trading_calendar.copy()
    sessions["date"] = pd.to_datetime(sessions["date"]).dt.normalize()

    for column in ["market_open", "market_close"]:
        sessions[column] = pd.to_datetime(sessions[column], utc=True)

    sessions = sessions.loc[
        sessions["split"].isin(["train", "test"])
    ].sort_values("date")

    if sessions.empty or sessions["date"].duplicated().any():
        raise ValueError("Missing or duplicate evaluation sessions.")

    equity = float(initial_cash)
    results, orders = [], []

    for session in sessions.itertuples(index=False):
        if equity <= 0:
            raise ValueError("The portfolio has exhausted its equity.")

        start_equity = equity
        result = {
            "date": session.date,
            "split": session.split,
            "equity_start": start_equity,
            "equity_end": start_equity,
            "gross_pnl": 0.0,
            "commission": 0.0,
            "slippage": 0.0,
            "net_pnl": 0.0,
            "strategy_return": 0.0,
            "orders": 0,
            "missing_signal_points": 0,
            "status": "missing_session",
        }

        # Preserve every evaluation session, including cash-only days.
        if session.date not in grouped.indices:
            results.append(result)
            continue

        day = grouped.get_group(session.date).copy()
        expected = int(session.expected_minutes)

        expected_ends = pd.date_range(
            session.market_open + pd.Timedelta(minutes=1),
            periods=expected,
            freq="min",
        )
        actual_ends = pd.DatetimeIndex(
            day["bar_end_ny"]
        ).tz_convert("UTC")

        prices = day[["open", "close"]].to_numpy(dtype=float)

        complete = (
            len(day) == expected
            and (actual_ends == expected_ends).all()
            and expected_ends[-1] == session.market_close
            and np.isfinite(prices).all()
            and (prices > 0).all()
        )

        # Incomplete price sessions stay in the calendar with zero return.
        if not complete:
            result["status"] = "incomplete_prices"
            results.append(result)
            continue

        # Fix share size at the start of the day, as in the paper.
        quantity = int(
            np.floor(start_equity / float(day["open"].iloc[0]))
        )

        cash, position = start_equity, 0
        total_commission, total_slippage = 0.0, 0.0
        order_count = 0

        def execute(target, reference_price, execution_time, reason):
            nonlocal cash, position
            nonlocal total_commission, total_slippage, order_count

            change = int(target - position)
            if change == 0:
                return

            traded = abs(change)
            fee = traded * commission
            slip_cost = traded * slippage

            # Apply adverse slippage to both purchases and sales.
            fill_price = (
                float(reference_price) + np.sign(change) * slippage
            )

            cash -= change * fill_price + fee
            position = int(target)

            total_commission += fee
            total_slippage += slip_cost
            order_count += 1

            orders.append({
                "date": session.date,
                "split": session.split,
                "execution_time": execution_time,
                "side": "buy" if change > 0 else "sell",
                "shares": traded,
                "reference_price": reference_price,
                "fill_price": fill_price,
                "commission": fee,
                "slippage": slip_cost,
                "position_after": position,
                "reason": reason,
            })

        # A decision uses the completed bar; execution uses the next open.
        day["next_open"] = day["open"].shift(-1)

        decision = (
            day["bar_end_ny"].dt.minute.isin([0, 30])
            & day["bar_end_ny"].lt(session.market_close)
        )

        missing_points = 0

        for bar in day.loc[decision].itertuples(index=False):
            valid_bounds = (
                np.isfinite(bar.upper_bound)
                and np.isfinite(bar.lower_bound)
                and bar.upper_bound >= bar.lower_bound
            )

            if not valid_bounds:
                missing_points += 1
                target, reason = 0, "missing_bounds"

            elif bar.close > bar.upper_bound:
                target, reason = quantity, "upper_breakout"

            elif bar.close < bar.lower_bound:
                target, reason = -quantity, "lower_breakout"

            else:
                target, reason = position, "hold"

            execute(
                target,
                bar.next_open,
                bar.bar_end_ny,
                reason,
            )

        # Simulate a preplanned market-on-close exit, including early closes.
        execute(
            0,
            float(day["close"].iloc[-1]),
            session.market_close.tz_convert("America/New_York"),
            "market_close",
        )

        equity = float(cash)
        net_pnl = equity - start_equity

        result.update({
            "equity_end": equity,
            "gross_pnl": net_pnl + total_commission + total_slippage,
            "commission": total_commission,
            "slippage": total_slippage,
            "net_pnl": net_pnl,
            "strategy_return": net_pnl / start_equity,
            "orders": order_count,
            "missing_signal_points": missing_points,
            "status": (
                "partial_bounds" if missing_points else "complete"
            ),
        })

        results.append(result)

    order_columns = [
        "date", "split", "execution_time", "side", "shares",
        "reference_price", "fill_price", "commission", "slippage",
        "position_after", "reason",
    ]

    return (
        pd.DataFrame(results).set_index("date"),
        pd.DataFrame(orders, columns=order_columns),
    )

def backtest_momentum(
    features,
    trading_calendar,
    stop_mode="opposite",
    initial_cash=100_000.0,
    commission=0.0035,
    slippage=0.001,
):
    """Compare stop rules using the same event ledger and sizing."""
    if stop_mode not in ["opposite", "band_vwap"]:
        raise ValueError("Unknown stop_mode.")

    if initial_cash <= 0 or commission < 0 or slippage < 0:
        raise ValueError("Invalid cash or cost assumptions.")

    if stop_mode == "band_vwap" and "vwap" not in features:
        raise ValueError("Merge VWAP into the features first.")

    data = features.copy()
    data["date"] = pd.to_datetime(data["date"]).dt.normalize()

    data["bar_end_ny"] = pd.to_datetime(
        data["bar_end_ny"], utc=True
    ).dt.tz_convert("America/New_York")

    data = data.sort_values(["date", "bar_end_ny"])

    if data["bar_end_ny"].duplicated().any():
        raise ValueError("Duplicate minute bars.")

    grouped = data.groupby("date", sort=False)

    sessions = trading_calendar.copy()
    sessions["date"] = pd.to_datetime(
        sessions["date"]
    ).dt.normalize()

    for column in ["market_open", "market_close"]:
        sessions[column] = pd.to_datetime(
            sessions[column], utc=True
        )

    sessions = sessions.loc[
        sessions["split"].isin(["train", "test"])
    ].sort_values("date")

    if sessions.empty or sessions["date"].duplicated().any():
        raise ValueError("Missing or duplicate evaluation sessions.")

    equity = float(initial_cash)
    results, orders = [], []

    for session in sessions.itertuples(index=False):
        if equity <= 0:
            raise ValueError("The portfolio has exhausted its equity.")

        start = equity
        result = {
            "date": session.date,
            "split": session.split,
            "equity_start": start,
            "equity_end": start,
            "gross_pnl": 0.0,
            "commission": 0.0,
            "slippage": 0.0,
            "net_pnl": 0.0,
            "strategy_return": 0.0,
            "orders": 0,
            "missing_signal_points": 0,
            "status": "missing_session",
        }

        if session.date not in grouped.indices:
            results.append(result)
            continue

        day = grouped.get_group(session.date).copy()
        expected = int(session.expected_minutes)

        expected_ends = pd.date_range(
            session.market_open + pd.Timedelta(minutes=1),
            periods=expected,
            freq="min",
        )
        actual_ends = pd.DatetimeIndex(
            day["bar_end_ny"]
        ).tz_convert("UTC")

        prices = day[["open", "close"]].to_numpy(dtype=float)

        complete = (
            len(day) == expected
            and (actual_ends == expected_ends).all()
            and expected_ends[-1] == session.market_close
            and np.isfinite(prices).all()
            and (prices > 0).all()
        )

        if not complete:
            result["status"] = "incomplete_prices"
            results.append(result)
            continue

        # Both models use the same daily share-sizing formula.
        quantity = int(
            np.floor(start / float(day["open"].iloc[0]))
        )

        # Execution follows the completed signal bar.
        day["next_open"] = day["open"].shift(-1)

        ticks = day.loc[
            day["bar_end_ny"].dt.minute.isin([0, 30])
            & day["bar_end_ny"].lt(session.market_close)
        ]

        valid_bounds = (
            np.isfinite(ticks["upper_bound"])
            & np.isfinite(ticks["lower_bound"])
            & ticks["upper_bound"].ge(ticks["lower_bound"])
        )

        if stop_mode == "opposite":
            # NaN means retain the previous position inside the bands.
            eligible = valid_bounds
            direction = pd.Series(np.nan, index=ticks.index)
            reasons = pd.Series("hold", index=ticks.index)

            direction.loc[~eligible] = 0
            reasons.loc[~eligible] = "missing_bounds"

            long_signal = (
                eligible
                & ticks["close"].gt(ticks["upper_bound"])
            )
            short_signal = (
                eligible
                & ticks["close"].lt(ticks["lower_bound"])
            )

        else:
            # Each decision explicitly selects long, short, or flat.
            valid_vwap = (
                np.isfinite(ticks["vwap"])
                & ticks["vwap"].gt(0)
            )
            eligible = valid_bounds & valid_vwap

            direction = pd.Series(0.0, index=ticks.index)
            reasons = pd.Series(
                "vwap_or_band_exit", index=ticks.index
            )

            reasons.loc[~valid_bounds] = "missing_bounds"
            reasons.loc[
                valid_bounds & ~valid_vwap
            ] = "missing_vwap"

            long_signal = (
                eligible
                & ticks["close"].gt(ticks["upper_bound"])
                & ticks["close"].gt(ticks["vwap"])
            )
            short_signal = (
                eligible
                & ticks["close"].lt(ticks["lower_bound"])
                & ticks["close"].lt(ticks["vwap"])
            )

        direction.loc[long_signal] = 1
        direction.loc[short_signal] = -1
        reasons.loc[long_signal] = "upper_breakout"
        reasons.loc[short_signal] = "lower_breakout"

        # Carry positions only forward within the same trading day.
        direction = direction.ffill().fillna(0)

        # Append the preplanned close-of-session liquidation.
        targets = np.r_[
            direction.to_numpy() * quantity, 0
        ].astype(int)

        changes = np.diff(np.r_[0, targets])

        references = np.r_[
            ticks["next_open"].to_numpy(dtype=float),
            float(day["close"].iloc[-1]),
        ]
        times = ticks["bar_end_ny"].tolist() + [
            session.market_close.tz_convert("America/New_York")
        ]
        reason_list = reasons.tolist() + ["market_close"]

        # A reversal trades twice the position size.
        commissions = np.abs(changes) * commission
        slippages = np.abs(changes) * slippage

        # Positions start and finish flat, so net cash flows equal PnL.
        gross = -float(np.dot(changes, references))
        fees = float(commissions.sum())
        slip = float(slippages.sum())
        net = gross - fees - slip
        equity = start + net

        for i in np.flatnonzero(changes):
            change = int(changes[i])

            orders.append({
                "date": session.date,
                "split": session.split,
                "execution_time": times[i],
                "side": "buy" if change > 0 else "sell",
                "shares": abs(change),
                "reference_price": references[i],
                "fill_price": (
                    references[i] + np.sign(change) * slippage
                ),
                "commission": commissions[i],
                "slippage": slippages[i],
                "position_after": targets[i],
                "reason": reason_list[i],
            })

        missing_points = int((~eligible).sum())

        result.update({
            "equity_end": equity,
            "gross_pnl": gross,
            "commission": fees,
            "slippage": slip,
            "net_pnl": net,
            "strategy_return": net / start,
            "orders": int(np.count_nonzero(changes)),
            "missing_signal_points": missing_points,
            "status": (
                "partial_bounds" if missing_points else "complete"
            ),
        })

        results.append(result)

    order_columns = [
        "date", "split", "execution_time", "side", "shares",
        "reference_price", "fill_price", "commission", "slippage",
        "position_after", "reason",
    ]

    return (
        pd.DataFrame(results).set_index("date"),
        pd.DataFrame(orders, columns=order_columns),
    )

def backtest_with_sizing(
    features,
    trading_calendar,
    volatility,
    sizing="vol_target",
    initial_cash=100_000.0,
    commission=0.0035,
    slippage=0.001,
    target_daily=0.02,
    max_leverage=4.0,
):
    """Reuse the existing execution engine with a daily notional budget."""
    if sizing not in {"fixed", "vol_target"}:
        raise ValueError("sizing must be 'fixed' or 'vol_target'.")
    if initial_cash <= 0 or target_daily <= 0 or max_leverage <= 0:
        raise ValueError("Cash, target volatility and leverage cap must be positive.")
    if commission < 0 or slippage < 0:
        raise ValueError("Trading costs must be nonnegative.")

    cal = trading_calendar.copy()
    cal["date"] = pd.to_datetime(cal["date"]).dt.normalize()
    cal = cal.sort_values("date")
    if cal["date"].duplicated().any():
        raise ValueError("Duplicate calendar sessions.")
    cal = cal[cal["split"].isin(["train", "test"])]

    bars = features.copy()
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    groups = {
        date: group
        for date, group in bars.groupby("date", sort=False)
    }

    equity = float(initial_cash)
    daily_rows = []
    order_frames = []

    for _, session in cal.iterrows():
        date = session["date"]
        equity_start = equity
        if equity_start <= 0:
            raise RuntimeError(
                f"Nonpositive portfolio equity before {date.date()}."
            )

        sigma = float(volatility.get(date, np.nan))
        valid_sigma = np.isfinite(sigma) and sigma > 0
        leverage = (
            1.0 if sizing == "fixed"
            else min(max_leverage, target_daily / sigma) if valid_sigma
            else 0.0
        )
        notional_budget = equity_start * leverage

        if leverage == 0.0:
            # Preserve the session in the return series while holding cash.
            row = {
                "split": session["split"],
                "gross_pnl": 0.0,
                "commission": 0.0,
                "slippage": 0.0,
                "net_pnl": 0.0,
                "orders": 0,
                "missing_signal_points": 0,
                "status": "missing_volatility",
            }
        else:
            day_bars = groups.get(date, bars.iloc[:0])
            one_calendar = session.to_frame().T

            # The engine sizes shares as floor(initial_cash / day_open).
            # Supply the notional budget, then transfer only dollar PnL
            # into the actual portfolio equity. Do not compound the budget.
            day_result, day_orders = backtest_momentum(
                day_bars,
                one_calendar,
                stop_mode="band_vwap",
                initial_cash=notional_budget,
                commission=commission,
                slippage=slippage,
            )
            if len(day_result) != 1:
                raise RuntimeError(
                    f"Expected one daily result for {date.date()}."
                )

            row = day_result.iloc[0].to_dict()
            row.pop("date", None)

            if not day_orders.empty:
                day_orders = day_orders.copy()
                day_orders["leverage"] = leverage
                day_orders["portfolio_equity_start"] = equity_start
                order_frames.append(day_orders)

        equity = equity_start + float(row["net_pnl"])
        if not np.isfinite(equity) or equity <= 0:
            raise RuntimeError(f"Portfolio exhausted on {date.date()}.")

        row.update({
            "date": date,
            "equity_start": equity_start,
            "equity_end": equity,
            "strategy_return": float(row["net_pnl"]) / equity_start,
            "sigma_daily_lagged": sigma,
            "leverage": leverage,
            "notional_budget": notional_budget,
        })
        daily_rows.append(row)

    result = pd.DataFrame(daily_rows).set_index("date").sort_index()
    orders = (
        pd.concat(order_frames, ignore_index=True)
        if order_frames else pd.DataFrame()
    )
    return result, orders






def performance_metrics(returns):
    """Use daily net returns, 252 sessions/year, and zero risk-free rate."""
    values = returns.to_numpy(dtype=float)

    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Missing daily returns.")

    if (values <= -1).any():
        raise ValueError("A daily return implies portfolio insolvency.")

    wealth = np.r_[1.0, np.cumprod(1.0 + values)]
    daily_vol = values.std(ddof=1) if len(values) > 1 else np.nan

    return {
        "days": len(values),
        "total_return": wealth[-1] - 1.0,
        "annual_return": wealth[-1] ** (252.0 / len(values)) - 1.0,
        "annual_volatility": daily_vol * np.sqrt(252.0),
        "sharpe": (
            values.mean() / daily_vol * np.sqrt(252.0)
            if daily_vol > 0 else np.nan
        ),
        "max_drawdown": (
            wealth / np.maximum.accumulate(wealth) - 1.0
        ).min(),
    }
