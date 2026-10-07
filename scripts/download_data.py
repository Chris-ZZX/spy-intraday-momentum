#!/usr/bin/env python3
"""Run the notebook's existing data-download section as a command-line script.

The downloader stays in Strategy.ipynb so the notebook and CLI share one
implementation. Credentials come from APCA_API_KEY_ID/APCA_API_SECRET_KEY
or the notebook's interactive getpass prompts.
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=ROOT / "Strategy.ipynb")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--refresh", action="store_true", help="Refresh cached bar downloads.")
    args = parser.parse_args()

    notebook = args.notebook.resolve()
    nb = json.loads(notebook.read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if c["cell_type"] == "code"
             and c.get("metadata", {}).get("annotation", {}).get("original_cell_index") == 0]
    if len(cells) != 9:
        raise ValueError("Expected the nine annotated data-download cells in Strategy.ipynb.")

    # Avoid the notebook's __main__ call until the output path is configured.
    scope = {"__name__": "notebook_data_download", "__file__": str(notebook)}
    for i, cell in enumerate(cells):
        source = cell["source"]
        source = source if isinstance(source, str) else "".join(source)
        exec(compile(source, f"{notebook}:data_cell_{i}", "exec"), scope)
    scope["SAVE_DIR"] = args.output_dir.resolve()
    scope["CACHE_DIR"] = scope["SAVE_DIR"] / "alpaca_cache"
    if args.refresh:
        scope["OVERWRITE"] = True
    scope["download_project_data"]()


if __name__ == "__main__":
    main()
