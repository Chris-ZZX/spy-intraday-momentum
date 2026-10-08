"""Export actual stored PNG and text outputs without executing code."""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path


def export_outputs(notebook_path, destination):
    notebook_path, destination = Path(notebook_path), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    manifest = []
    for i, cell in enumerate(notebook["cells"]):
        texts = []
        for j, output in enumerate(cell.get("outputs", [])):
            data = output.get("data", {})
            png = data.get("image/png")
            if png:
                name = f"cell_{i:03d}_output_{j:02d}.png"
                if isinstance(png, list):
                    png = "".join(png)
                (destination / name).write_bytes(base64.b64decode(png))
                manifest.append({"file": name, "cell": i, "output": j, "kind": "png"})
            text = output.get("text", data.get("text/plain", ""))
            if isinstance(text, list):
                text = "".join(text)
            if text:
                texts.append(text)
        if texts:
            name = f"cell_{i:03d}.txt"
            (destination / name).write_text("\n".join(texts), encoding="utf-8")
            manifest.append({"file": name, "cell": i, "kind": "text"})
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebook", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    export_outputs(args.notebook, args.destination)
