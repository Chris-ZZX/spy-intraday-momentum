"""Validate notebook structure, code syntax, language and saved-data integrity."""
from __future__ import annotations
import ast
import base64
import hashlib
import json
import re
from pathlib import Path
import nbformat
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "notebooks/SPY_Intraday_Momentum.ipynb"
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    code_count = 0
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "code":
            ast.parse(cell.source, filename=f"cell-{index}")
            code_count += 1
        if re.search(r"[\u4e00-\u9fff]", cell.source):
            raise AssertionError(f"Non-English CJK text in source cell {index}.")
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                raise AssertionError(f"Saved execution error in cell {index}.")
            text = output.get("text", "")
            if re.search(r"[\u4e00-\u9fff]", text):
                raise AssertionError(f"Non-English CJK text in output cell {index}.")
        if cell.metadata.get("run_group") == "pending" and cell.cell_type == "code":
            if cell.get("execution_count") is not None or cell.get("outputs"):
                raise AssertionError("Pending SPY experiments must not have invented saved results.")
    for script in ROOT.rglob("*.py"):
        ast.parse(script.read_text(encoding="utf-8"), filename=str(script.relative_to(ROOT)))
    manifest = json.loads((ROOT / "results/saved/figure_manifest.json").read_text())
    for item in manifest:
        content = (ROOT / "results/saved" / item["file"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise AssertionError("Original figure payload changed: " + item["file"])
    metrics = pd.read_csv(ROOT / "results/saved/performance.csv")
    if metrics[["period", "strategy"]].duplicated().any():
        raise AssertionError("Duplicate saved period/strategy rows.")
    test = metrics[metrics.period.eq("test")].set_index("strategy")
    if not test.days.eq(584).all():
        raise AssertionError("Historical-test calendars differ.")
    baseline = test.loc["Band + VWAP + Vol target"]
    for name in ["ER entry filter", "TCN return filter"]:
        if not test.loc[name, [
            "total_return", "annual_return", "annual_volatility", "sharpe", "max_drawdown"
        ]].equals(baseline[[
            "total_return", "annual_return", "annual_volatility", "sharpe", "max_drawdown"
        ]]):
            raise AssertionError("The selected no-filter result differs from the saved baseline.")
    # Check literal credential assignments; never print their values.
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        for node in ast.walk(ast.parse(cell.source)):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if any(name in {"API_KEY", "API_SECRET"} for name in names) and node.value.value:
                    raise AssertionError(f"Nonempty literal credential in cell {index}.")
    print(f"Validated {len(notebook.cells)} cells, {code_count} Python cells, "
          f"{len(manifest)} original figures and {len(metrics)} saved metric rows.")


if __name__ == "__main__":
    main()
