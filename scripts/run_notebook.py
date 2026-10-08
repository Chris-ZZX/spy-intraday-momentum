"""Execute a clean notebook copy using existing local project CSVs."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["paper", "models", "all"], default="paper")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Maximum seconds per executed cell.")
    args = parser.parse_args()
    data = args.data_dir.expanduser().resolve()
    required = ["SPY_1min.csv", "SPY_daily_features.csv", "NYSE_calendar.csv"]
    missing = [name for name in required if not (data / name).is_file()]
    if missing:
        parser.error("Missing CSV inputs: " + ", ".join(missing)
                     + ". Put the prepared files in --data-dir or run the explicit downloader.")
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError as exc:
        parser.error("Install requirements.txt first: " + str(exc))
    os.environ["SPY_DATA_DIR"] = str(data)
    os.environ["SPY_RUN_DOWNLOADS"] = "0"
    notebook = nbformat.read(ROOT / "notebooks/SPY_Intraday_Momentum.ipynb", as_version=4)
    allowed = {"data", "paper"}
    if args.stage in {"models", "all"}:
        allowed.update({"models", "entry_summary", "saved_summary"})
    if args.stage == "all":
        allowed.add("pending")
    notebook.cells = [
        cell for cell in notebook.cells
        if cell.metadata.get("run_group") in allowed
        or cell.metadata.get("source_cell_index") in {0, 1}
    ]
    for cell in notebook.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
            cell.metadata.pop("output_provenance", None)
    notebook.metadata["execution_scope"] = {
        "stage": args.stage, "downloads": False,
        "stale_code_outputs_cleared": True,
    }
    destination = args.output or (
        ROOT / "results/generated" / f"SPY_Intraday_Momentum_{args.stage}.ipynb"
    )
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        NotebookClient(
            notebook, timeout=args.timeout, kernel_name="python3",
            resources={"metadata": {"path": str(ROOT)}},
        ).execute()
    except Exception:
        partial = destination.with_name(destination.stem + "_failed.ipynb")
        nbformat.write(notebook, partial)
        print("Execution stopped; partial diagnostic notebook:", partial, file=sys.stderr)
        raise
    nbformat.write(notebook, destination)
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_outputs import export_outputs
    export_outputs(destination, destination.parent / (destination.stem + "_outputs"))
    print("Fresh executed notebook:", destination)
    print("The original results/saved files were not overwritten.")


if __name__ == "__main__":
    main()
