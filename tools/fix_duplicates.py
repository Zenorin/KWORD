#!/usr/bin/env python3
# tools/fix_duplicates.py
"""
Fix duplicated keys in scores CSV by keeping the highest-score row per key.

- Key = (seed, keyword) if both exist, else (keyword)
- Sorts by score desc, keeps first occurrence
- Writes cleaned CSV to --out (default: output/keyword_scores_free_dedup.csv)

Usage:
  python -u tools/fix_duplicates.py --in output/keyword_scores_free.csv --out output/keyword_scores_free_dedup.csv
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
import numpy as np

def _read_csv(p: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeError:
        return pd.read_csv(p, encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, default=Path("output/keyword_scores_free.csv"))
    ap.add_argument("--out", dest="out", type=Path, default=Path("output/keyword_scores_free_dedup.csv"))
    args = ap.parse_args()

    df = _read_csv(args.inp)
    if "keyword" not in df.columns:
        raise SystemExit("ERROR: 'keyword' column missing in scores CSV")

    # choose key columns
    keys = ["seed","keyword"] if all(c in df.columns for c in ["seed","keyword"]) else ["keyword"]

    # numeric score for sort
    df["_score_num"] = pd.to_numeric(df.get("score"), errors="coerce")
    df["_score_num"] = df["_score_num"].fillna(-np.inf)

    # stable sort: by score desc, then original order
    df = df.sort_values(by=["_score_num"], ascending=False, kind="mergesort")

    # drop duplicates keeping first
    before = len(df)
    cleaned = df.drop_duplicates(subset=keys, keep="first").drop(columns=["_score_num"])
    after = len(cleaned)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"[OK] wrote dedup → {args.out}  (rows: {before} → {after})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
