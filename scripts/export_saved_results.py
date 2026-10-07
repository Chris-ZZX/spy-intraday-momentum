#!/usr/bin/env python3
"""Export the supplied notebook's saved outputs without executing its code.

Uses only the Python standard library. Exported metrics retain the precision
of the notebook's printed tables; this is not a fresh backtest.
"""

import argparse
import ast
import base64
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
METRICS = [
    "days", "total_return", "annual_return", "annual_volatility",
    "sharpe", "max_drawdown",
]
FIELDS = ["period", "strategy", *METRICS, "source_cell_index"]
NUMBER = r"(?:[-+]?\d+(?:\.\d+)?|NaN|nan)"
PERFORMANCE_ROW = re.compile(
    rf"^(?:(train|test|development|validation)\s+)?"
    rf"(.+?)\s+(\d+)\s+({NUMBER})%\s+({NUMBER})%\s+"
    rf"({NUMBER})%\s+({NUMBER})\s+({NUMBER})%\s*$"
)
TABLES = {
    "paper_train_test.csv": ("comparison_dynamic = comparison.copy()", 8),
    "er_train_test.csv": ("er_comparison = comparison_dynamic.copy()", 10),
    "lstm_periods.csv": ("dl_comparison = pd.DataFrame(index=dl_dates)", 15),
    "tcn_periods.csv": ("tcn_comparison = pd.DataFrame({", 12),
    "complete_periods.csv": ("Complete performance comparison:", 18),
}
FIGURES = {
    39: ["baseline_equity.png"],
    41: ["baseline_metrics.png"],
    49: ["vwap_equity.png", "vwap_metrics.png"],
    59: ["vol_target_equity.png", "vol_target_metrics.png"],
    72: ["er_equity.png", "er_metrics.png"],
    98: ["lstm_equity.png", "lstm_allocation.png"],
    122: ["return_filter_equity.png"],
    126: ["complete_equity.png"],
}
PARAMETERS = {
    "SYMBOL", "NY", "DATA_START", "ANALYSIS_START", "TRAIN_END", "END_DATE",
    "OVERWRITE", "LOOKBACK", "VOL_MULTIPLIER", "INITIAL_CASH",
    "COMMISSION_PER_SHARE", "SLIPPAGE_PER_SHARE", "VOL_TARGET_DAILY",
    "MAX_LEVERAGE", "VOL_LOOKBACK", "ER_WINDOW", "ER_THRESHOLDS",
    "ER_VALIDATION_START", "ER_MIN_ACTIVE_DAYS", "DL_SEQUENCE",
    "DL_VALIDATION_START", "DL_SEED", "DL_HIDDEN", "DL_EPOCHS",
    "DL_PATIENCE", "DL_LEARNING_RATE", "DL_WEIGHT_DECAY", "DL_DEVICE",
    "TCN_WINDOW", "TCN_VALIDATION_START", "TCN_THRESHOLDS",
    "TCN_MIN_ACTIVE_DAYS", "TCN_SEED",
}


def joined(value):
    return value if isinstance(value, str) else "".join(value)


def stream_text(cell):
    return "".join(
        joined(output.get("text", ""))
        for output in cell.get("outputs", [])
        if output.get("output_type") == "stream"
    )


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def pct(value):
    return str(Decimal(value) / 100)


def find_cell(cells, marker):
    matches = [
        (i, cell) for i, cell in enumerate(cells)
        if cell["cell_type"] == "code"
        and marker in (joined(cell["source"]) + "\n" + stream_text(cell))
        and "Performance comparison:".lower() in stream_text(cell).lower()
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one saved performance table for {marker!r}.")
    return matches[0]


def performance_rows(text, cell_index):
    rows = []
    period = None
    for line in text.splitlines():
        match = PERFORMANCE_ROW.fullmatch(line.strip())
        if match is None:
            continue
        group, strategy, days, total, annual, vol, sharpe, drawdown = match.groups()
        period = group or period
        if period is None:
            raise ValueError("A table row has no period label.")
        rows.append({
            "period": period, "strategy": strategy, "days": int(days),
            "total_return": pct(total), "annual_return": pct(annual),
            "annual_volatility": pct(vol),
            "sharpe": "" if sharpe.lower() == "nan" else sharpe,
            "max_drawdown": pct(drawdown), "source_cell_index": cell_index,
        })
    return rows


def numeric(value):
    return "" if value.lower() == "nan" else value


def export_thresholds(cells, results):
    er_rows = []
    filter_rows = []
    for i, cell in enumerate(cells):
        text = stream_text(cell)
        if "Validation threshold comparison:" in text and "Selected ER threshold:" in text:
            for line in text.splitlines():
                parts = line.split()
                if len(parts) != 11 or not re.fullmatch(r"\d+\.\d+", parts[0]):
                    continue
                er_rows.append(dict(zip(
                    ["threshold", *METRICS, "active_days", "orders",
                     "rejected_entries", "cost"],
                    map(numeric, parts),
                ), source_cell_index=i))
        if "TCN: validation threshold comparison" in text:
            model = None
            for line in text.splitlines():
                if line.startswith("TCN: validation"):
                    model = "TCN"
                elif line.startswith("Ridge: validation"):
                    model = "Ridge"
                parts = line.split()
                if len(parts) != 12 or not parts[0].isdigit():
                    continue
                label = " ".join(parts[1:3])
                row = dict(zip(
                    METRICS + ["active_days", "orders", "rejected_entries"],
                    map(numeric, parts[3:]),
                ))
                row.update(model=model, candidate=parts[0],
                           filter_enabled=label != "All entries",
                           threshold_bps="" if label == "All entries" else parts[1],
                           source_cell_index=i)
                filter_rows.append(row)
    if len(er_rows) != 4 or len(filter_rows) != 8:
        raise ValueError("Saved threshold tables are missing or have changed layout.")
    write_csv(results / "er_validation_thresholds.csv", er_rows,
              ["threshold", *METRICS, "active_days", "orders",
               "rejected_entries", "cost", "source_cell_index"])
    write_csv(results / "return_filter_validation_thresholds.csv", filter_rows,
              ["model", "candidate", "filter_enabled", "threshold_bps", *METRICS,
               "active_days", "orders", "rejected_entries", "source_cell_index"])


def selection(cells, pattern, convert):
    for i, cell in enumerate(cells):
        match = re.search(pattern, stream_text(cell))
        if match:
            return {"value": convert(match.group(1)), "source_cell_index": i}
    raise ValueError(f"Missing saved selection: {pattern}")


def export_parameters(cells, path):
    values = {}
    for i, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        for node in ast.parse(joined(cell["source"])).body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name) or target.id not in PARAMETERS:
                    continue
                value = node.value
                if (isinstance(value, ast.Call)
                    and ast.unparse(value.func) in {"pd.Timestamp", "torch.device"}
                    and len(value.args) == 1):
                    value = value.args[0]
                values[target.id] = {
                    "value": ast.literal_eval(value), "source_cell_index": i,
                }
    if values.keys() != PARAMETERS:
        raise ValueError(f"Missing parameters: {sorted(PARAMETERS - values.keys())}")
    write_json(path, {
        "description": "Parameters read from notebook source without execution.",
        "execution_note": "This is a reference snapshot. Edit Strategy.ipynb to change a run.",
        "parameters": dict(sorted(values.items())),
    })


def export(notebook, destination):
    raw = notebook.read_bytes()
    nb = json.loads(raw)
    cells = nb["cells"]
    results = destination / "results"
    assets = destination / "assets"
    config = destination / "config"
    for folder in (results, assets, config):
        folder.mkdir(parents=True, exist_ok=True)

    tables = {}
    for filename, (marker, expected_count) in TABLES.items():
        index, cell = find_cell(cells, marker)
        rows = performance_rows(stream_text(cell), index)
        if len(rows) != expected_count:
            raise ValueError(f"{filename}: expected {expected_count} rows, got {len(rows)}.")
        write_csv(results / filename, rows, FIELDS)
        tables[filename] = rows

    test_rows = [r for r in tables["complete_periods.csv"] if r["period"] == "test"]
    test_rows += [r for r in tables["er_train_test.csv"]
                  if r["period"] == "test" and r["strategy"] == "Vol target + ER filter"]
    test_rows += [r for r in tables["lstm_periods.csv"]
                  if r["period"] == "test" and r["strategy"] in {
                      "LSTM risk allocation", "Constant 50%", "Constant matched allocation",
                  }]
    if len(test_rows) != 10 or len({r["strategy"] for r in test_rows}) != 10:
        raise ValueError("Expected ten distinct strategies/controls in the test summary.")
    write_csv(results / "test_summary.csv", test_rows, FIELDS)

    export_thresholds(cells, results)
    write_json(results / "selected_models.json", {
        "origin": "Selections printed in the supplied notebook, not newly fitted here.",
        "er_threshold": selection(cells, r"Selected ER threshold:\s*([\d.]+)", float),
        "lstm_epoch": selection(cells, r"Selected epoch:\s*(\d+)", int),
        "lstm_validation_sharpe": selection(cells, r"Best validation Sharpe:\s*([\d.]+)", float),
        "constant_matched_allocation": selection(cells, r"Constant matched allocation:\s*([\d.]+)%", lambda x: float(x) / 100),
        "tcn_epoch": selection(cells, r"Selected TCN epoch:\s*(\d+)", int),
        "tcn_entry_threshold": selection(cells, r"TCN selected threshold:\s*([^\n]+)", str),
        "ridge_entry_threshold": selection(cells, r"Ridge selected threshold:\s*([^\n]+)", str),
    })
    export_parameters(cells, config / "research_config.json")

    figures = []
    for index, names in FIGURES.items():
        outputs = [o["data"]["image/png"] for o in cells[index].get("outputs", [])
                   if "image/png" in o.get("data", {})]
        if len(outputs) != len(names):
            raise ValueError(f"Saved figures changed at cell {index}.")
        for name, payload in zip(names, outputs):
            png = base64.b64decode(joined(payload), validate=True)
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError(f"Invalid PNG: {name}")
            (assets / name).write_bytes(png)
            figures.append({"filename": f"assets/{name}", "source_cell_index": index})

    code = [(i, c) for i, c in enumerate(cells) if c["cell_type"] == "code"]
    errors = [i for i, c in code for o in c.get("outputs", [])
              if o.get("output_type") == "error"]
    write_json(results / "provenance.json", {
        "notebook": notebook.name,
        "notebook_sha256": hashlib.sha256(raw).hexdigest(),
        "notebook_bytes": len(raw),
        "nbformat": nb["nbformat"], "nbformat_minor": nb["nbformat_minor"],
        "python_version_in_metadata": nb["metadata"]["language_info"].get("version"),
        "cell_count": len(cells), "code_cell_count": len(code),
        "markdown_cell_count": sum(c["cell_type"] == "markdown" for c in cells),
        "code_cells_with_execution_count": sum(c.get("execution_count") is not None for _, c in code),
        "code_cells_without_execution_count": [i for i, c in code if c.get("execution_count") is None],
        "saved_error_cells": errors,
        "source_cell_index_convention": "Zero-based index in Strategy.ipynb.",
        "metric_origin": "Saved console tables. Percentages converted to decimal fractions.",
        "precision_note": "Exported metrics are rounded printed values, not raw daily-return recomputations.",
        "fresh_backtest_performed_for_repository_build": False,
        "raw_market_data_included": False,
        "trained_model_checkpoints_included": False,
        "figures": figures,
    })
    print(f"Exported {len(tables) + 3} CSV tables and {len(figures)} saved figures to {destination}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=ROOT / "Strategy.ipynb")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    export(args.notebook.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
