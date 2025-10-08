#!/usr/bin/env python3
# tools/make_regression_seeds.py
"""
Create a lightweight regression Excel from the existing 'data/seeds.xlsx'.

- Reads 'seeds' sheet, detects keyword/category columns robustly
- Takes up to N rows per category (default 2) to keep it fast
- Copies 'config' sheet as-is (tokens/weights preserved); if missing, creates defaults
- Writes to data/seeds_regression.xlsx

Usage:
  python -u tools/make_regression_seeds.py \
    --excel-in data/seeds.xlsx \
    --out-xlsx data/seeds_regression.xlsx \
    --per-category 2
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import pandas as pd

def _detect_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    low = [c.lower() for c in cols]
    for cand in candidates:
        if cand.lower() in low:
            return cols[low.index(cand.lower())]
    return None

def _guess_keyword_col(df: pd.DataFrame) -> Optional[str]:
    cands = [
        "keyword","키워드","kw","term","query","text","title",
        "expanded_keyword","related_keyword","source"
    ]
    col = _detect_col(list(df.columns), cands)
    if col:
        return col
    # heuristic: the most texty column that's not an index/id
    blacklist = {"seed","seed_index","id","idx","index","category","cat"}
    best, score = None, -1.0
    sample = df.head(50)
    for name in df.columns:
        if name.lower() in blacklist: 
            continue
        vals = sample[name].astype(str).fillna("")
        nonempty = vals[vals.str.strip() != ""]
        if nonempty.empty:
            continue
        avglen = nonempty.str.len().mean()
        uniq = nonempty.nunique()
        fill = len(nonempty) / max(1, len(vals))
        s = avglen * (0.5 + 0.5*fill) + 0.05*uniq
        if s > score:
            score, best = s, name
    return best

def _guess_category_col(df: pd.DataFrame) -> Optional[str]:
    return _detect_col(list(df.columns), ["category","카테고리","cat","group","type"])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel-in", type=Path, default=Path("data/seeds.xlsx"))
    ap.add_argument("--out-xlsx", type=Path, default=Path("data/seeds_regression.xlsx"))
    ap.add_argument("--per-category", type=int, default=2)
    args = ap.parse_args()

    if not args.excel_in.exists():
        raise SystemExit(f"ERROR: Excel not found → {args.excel_in}")

    # Read all sheets
    book = pd.read_excel(args.excel_in, sheet_name=None, engine="openpyxl")
    if "seeds" not in book:
        raise SystemExit("ERROR: sheet 'seeds' not found in Excel")

    seeds = book["seeds"].copy()
    # Drop unnamed columns
    seeds = seeds.loc[:, [c for c in seeds.columns if not str(c).lower().startswith("unnamed")]]

    kw_col = _guess_keyword_col(seeds)
    cat_col = _guess_category_col(seeds)

    if not kw_col:
        raise SystemExit(f"ERROR: could not detect keyword column in seeds; columns={list(seeds.columns)}")

    # If category missing, synthesize a single category so grouping still works
    if not cat_col:
        cat_col = "_category"
        seeds[cat_col] = "default"

    # Keep only the essential columns for regression sheet
    base_cols = [cat_col, kw_col]
    keep = [c for c in base_cols if c in seeds.columns]
    slim = seeds[keep].copy()
    slim = slim.rename(columns={kw_col: "keyword", cat_col: "category"})

    # Remove empty keywords
    slim = slim[slim["keyword"].astype(str).str.strip() != ""].reset_index(drop=True)

    # Take up to N per category (stable head order)
    per = max(1, int(args.per_category))
    reg = (
        slim.groupby("category", group_keys=False)
            .head(per)
            .reset_index(drop=True)
    )

    # Ensure at least 1 row
    if reg.empty:
        raise SystemExit("ERROR: seeds selection is empty after filtering")

    # Prepare output workbook: seeds + config
    out_sheets = {}
    out_sheets["seeds"] = reg

    if "config" in book:
        out_sheets["config"] = book["config"].copy()
    else:
        out_sheets["config"] = pd.DataFrame({"W_intent":[0.55], "W_competition":[0.45]})

    # Write
    args.out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.out_xlsx, engine="openpyxl", mode="w") as xw:
        for name, df in out_sheets.items():
            df.to_excel(xw, index=False, sheet_name=name)

    print(f"[OK] Wrote regression workbook → {args.out_xlsx}")
    print(f"[OK] Rows: {len(reg)} | Categories: {reg['category'].nunique()}")
    print("[OK] Columns(seeds):", list(reg.columns))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
