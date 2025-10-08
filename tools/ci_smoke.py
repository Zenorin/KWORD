#!/usr/bin/env python3
# tools/ci_smoke.py
"""
CI smoke test for Free Edition scoring.

- Uses the GOLDEN regression inputs (sanitized/expanded/competition)
  to re-run compute_scores deterministically (no network).
- Compares produced scores CSV with golden scores CSV:
  * same row count
  * same key set (seed,keyword) — seed optional
  * score numeric equality within tolerance (default: 1e-9)
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REQ_COLS = ["keyword","keyword_sanitized","comp_combined","intent_norm","competition_norm","score"]

def _read_csv(p: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeError:
        return pd.read_csv(p, encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden-dir", type=Path, default=Path("output/golden/regression"))
    ap.add_argument("--excel-in", type=Path, default=Path("data/seeds_regression.xlsx"))
    ap.add_argument("--tolerance", type=float, default=1e-9)
    args = ap.parse_args()

    gdir = args.golden_dir
    g_sani   = gdir / "sanitized_keywords.csv"
    g_expd   = gdir / "expanded_keywords.csv"
    g_comp   = gdir / "competition_counts.csv"
    g_scores = gdir / "keyword_scores_free.csv"

    for p in [g_sani, g_expd, g_comp, g_scores]:
        if not p.exists():
            print(f"❌ Missing golden file: {p}")
            return 1

    out_dir = Path("output/_ci_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_scores = out_dir / "ci_scores.csv"

    cmd = [
        sys.executable, "-u", "tools/compute_scores.py",
        "--excel-in", str(args.excel_in),
        "--sanitized-in", str(g_sani),
        "--expanded-in", str(g_expd),
        "--competition-in", str(g_comp),
        "--out-csv", str(out_scores),
        "--topn", "10",
    ]
    print("[RUN]", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0 or not out_scores.exists():
        print("❌ compute_scores failed or output missing")
        return 1

    gold = _read_csv(g_scores)
    new  = _read_csv(out_scores)

    miss = [c for c in REQ_COLS if c not in new.columns]
    if miss:
        print("❌ missing required columns:", miss)
        return 1

    if len(gold) != len(new):
        print(f"❌ row count mismatch: golden={len(gold)} vs new={len(new)}")
        return 1

    keys = [c for c in ["seed","keyword"] if c in gold.columns and c in new.columns]
    if not keys:
        keys = ["keyword"]

    g = gold[keys + ["score"]].copy()
    n = new[keys + ["score"]].copy()
    merged = g.merge(n, on=keys, how="outer", suffixes=("_gold","_new"), indicator=True)
    if (merged["_merge"] != "both").any():
        diff = merged[merged["_merge"] != "both"]
        print("❌ key set mismatch. sample:\n", diff.head().to_string(index=False))
        return 1

    merged["delta"] = (merged["score_new"] - merged["score_gold"]).abs()
    max_delta = float(merged["delta"].max())
    if np.isnan(max_delta) or max_delta > args.tolerance:
        print(f"❌ score delta too large. max_delta={max_delta:.3g} tol={args.tolerance}")
        print(merged.sort_values("delta", ascending=False).head(5).to_string(index=False))
        return 1

    print(f"✅ CI smoke passed. rows={len(new)}, max_delta={max_delta:.3g}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
