"""Rebuilds the study report from the sessions in this folder.

Reads analysis/data (recorder files: P##.csv + P##.json; exported files: P##.json with the events inside) and writes
analysis/results: report.html (every chart), summary.md (the comparison table), tasks.csv (one row per task) and
paths_P##.png (mouse paths). Usage, from the A11yNav folder:
    .venv\\Scripts\\python.exe analysis\\run_analysis.py
"""
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("analyze", HERE / "code" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)

if __name__ == "__main__":
    raise SystemExit(analyze.main(HERE / "data", HERE / "results"))
