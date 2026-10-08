"""Small synthetic checks of execution and research mechanics."""
from __future__ import annotations
import contextlib
import io
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.backtest import (
    backtest_baseline, backtest_momentum, backtest_with_sizing,
    performance_metrics,
)


def make_data():
    warmup = list(pd.bdate_range("2020-11-02", periods=14))
    dates = warmup + list(pd.to_datetime([
        "2020-12-01", "2020-12-02", "2021-01-04",
        "2021-01-05", "2022-01-03", "2022-01-04",
    ]))
    calendar, frames = [], []
    for number, date in enumerate(dates):
        split = "warmup" if number < 14 else "train" if number < 18 else "test"
        opening = pd.Timestamp(date).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
        ends = pd.date_range(opening + pd.Timedelta(minutes=1), periods=390, freq="min")
        k = np.arange(390)
        offset = number * 0.01
        closes = np.where(k < 29, 100.1, np.where(k < 119, 100.8, 99.2)) + offset
        opens = np.r_[100.0 + offset, closes[:-1]]
        frames.append(pd.DataFrame({
            "date": date, "split": split, "bar_end_ny": ends,
            "open": opens, "close": closes, "day_open": 100.0 + offset,
            "upper_bound": 100.5 + offset, "lower_bound": 99.5 + offset,
            "vwap": 100.0 + offset,
        }))
        calendar.append({
            "date": date, "split": split, "expected_minutes": 390,
            "market_open": opening.tz_convert("UTC"),
            "market_close": ends[-1].tz_convert("UTC"),
        })
    features = pd.concat(frames, ignore_index=True)
    cal = pd.DataFrame(calendar)
    sigma = pd.Series(0.01, index=pd.DatetimeIndex(cal.date))
    return features, cal, sigma


def upgrade_namespace(features, cal, sigma):
    previous, _ = backtest_with_sizing(features, cal, sigma)
    namespace = {
        "features_vwap": features, "cal_sizing": cal, "sigma_daily": sigma,
        "vol_target_daily": previous, "comparison_dynamic": pd.DataFrame(),
        "performance_metrics": performance_metrics, "INITIAL_CASH": 100_000.0,
        "COMMISSION_PER_SHARE": 0.0035, "SLIPPAGE_PER_SHARE": 0.001,
        "VOL_TARGET_DAILY": 0.02, "MAX_LEVERAGE": 4.0,
    }
    notebook = json.loads((ROOT / "notebooks/SPY_Intraday_Momentum.ipynb").read_text())
    sources = {
        cell.get("metadata", {}).get("source_cell_index"): "".join(cell.get("source", []))
        for cell in notebook["cells"]
    }
    with contextlib.redirect_stdout(io.StringIO()):
        exec(sources[128], namespace)
        exec(sources[130], namespace)
    return namespace, previous


def test_opposite_engines_and_reversal_accounting():
    features, cal, _ = make_data()
    first, _ = backtest_baseline(features, cal)
    second, orders = backtest_momentum(features, cal, stop_mode="opposite")
    np.testing.assert_allclose(first.strategy_return, second.strategy_return)
    np.testing.assert_allclose(second.net_pnl, second.gross_pnl - second.commission - second.slippage)
    for _, day in orders.groupby("date"):
        assert day.position_after.iloc[-1] == 0
        # A direct long-to-short reversal must include closing and opening shares.
        assert day.shares.iloc[1] == 2 * day.shares.iloc[0]


def test_fixed_sizing_special_case_and_costs():
    features, cal, sigma = make_data()
    direct, _ = backtest_momentum(features, cal, stop_mode="band_vwap")
    fixed, _ = backtest_with_sizing(features, cal, sigma, sizing="fixed")
    np.testing.assert_allclose(direct.strategy_return, fixed.strategy_return)
    free, _ = backtest_momentum(
        features, cal.iloc[-1:], stop_mode="band_vwap", commission=0, slippage=0
    )
    paid, _ = backtest_momentum(features, cal.iloc[-1:], stop_mode="band_vwap")
    assert paid.net_pnl.iloc[0] < free.net_pnl.iloc[0]


def test_legacy_upgrade_identity_and_variance_timing():
    features, cal, sigma = make_data()
    namespace, previous = upgrade_namespace(features, cal, sigma)
    result, _ = namespace["backtest_upgrade"](missing_policy="legacy")
    for column in ["equity_start", "equity_end", "gross_pnl", "commission",
                   "slippage", "net_pnl", "strategy_return"]:
        np.testing.assert_allclose(result[column], previous[column], atol=1e-8)
    info = namespace["up_cache"][cal.date.iloc[-1]]
    assert info["rv_available"].all()
    assert np.all((info["risk_multiplier"] > 0) & (info["risk_multiplier"] <= 1))
    # Perturbing the current session cannot change its historical variance reference.
    before = namespace["up_rv_history"].loc[cal.date.iloc[-1]].copy()
    changed = features.copy()
    current = changed.date.eq(cal.date.iloc[-1])
    changed.loc[current, "close"] *= 1.03
    alternate, _ = upgrade_namespace(changed, cal, sigma)
    pd.testing.assert_series_equal(
        before, alternate["up_rv_history"].loc[cal.date.iloc[-1]]
    )


def test_causal_gap_retains_prior_trade_and_liquidates():
    features, cal, sigma = make_data()
    date = cal.date.iloc[-1]
    indices = features.index[features.date.eq(date)]
    broken = features.drop(indices[80])
    namespace, _ = upgrade_namespace(broken, cal, sigma)
    causal, orders = namespace["backtest_upgrade"](dates=[date], missing_policy="causal")
    legacy, _ = namespace["backtest_upgrade"](dates=[date], missing_policy="legacy")
    assert legacy.orders.iloc[0] == 0
    assert causal.orders.iloc[0] >= 2
    assert orders.reason.iloc[-1] == "data_gap_exit"
    assert orders.position_after.iloc[-1] == 0
    assert np.isfinite(orders.reference_price).all()


def test_confirmation_rejects_new_side_without_blocking_exit():
    features, cal, sigma = make_data()
    namespace, _ = upgrade_namespace(features, cal, sigma)
    date = cal.date.iloc[-1]
    times = list(pd.date_range("2022-01-04 15:00", periods=4, freq="30min", tz="UTC"))
    namespace["up_cache"][date].update({
        "side": np.array([1, 1, -1]),
        "streak": np.array([1, 3, 1]),
        "references": np.array([100.8, 100.9, 99.2, 99.2]),
        "times": times, "idx": np.array([29, 59, 89]),
        "risk_multiplier": np.ones(3), "rv_available": np.ones(3, dtype=bool),
    })
    result, orders = namespace["backtest_upgrade"](confirm_minutes=3, dates=[date])
    assert result.rejected_entries.iloc[0] == 2
    assert len(orders) == 2
    assert orders.position_after.iloc[0] > 0
    assert orders.position_after.iloc[1] == 0
    assert (orders.position_after >= 0).all()


def test_missing_liquidation_reference_raises():
    features, cal, sigma = make_data()
    namespace, _ = upgrade_namespace(features, cal, sigma)
    date = cal.date.iloc[-1]
    namespace["up_cache"][date]["references"][-1] = np.nan
    with pytest.raises(RuntimeError, match="no usable liquidation"):
        namespace["backtest_upgrade"](dates=[date])


def test_metric_definitions_and_invalid_daily_return():
    returns = pd.Series([0.01, -0.02, 0.015, 0.0])
    metrics = performance_metrics(returns)
    expected_wealth = np.prod(1 + returns.to_numpy())
    assert metrics["total_return"] == pytest.approx(expected_wealth - 1)
    assert metrics["annual_return"] == pytest.approx(expected_wealth ** 63 - 1)
    assert metrics["annual_volatility"] == pytest.approx(returns.std(ddof=1) * np.sqrt(252))
    with pytest.raises(ValueError, match="insolvency"):
        performance_metrics(pd.Series([0.1, -1.0]))
