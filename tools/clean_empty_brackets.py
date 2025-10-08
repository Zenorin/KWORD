#!/usr/bin/env python3
# tools/clean_empty_brackets.py
"""
Post-sanitization cleaner:
- Removes empty square-bracket pairs "[]"
- Collapses multiple spaces and trims
- Works for columns commonly used: keyword, keyword_sanitized (if present)

Usage:
  python tools/clean_empty_brackets.py --in output/sanitized_keywords.csv --out output/sanitized_keywords.csv
"""

import argparse
import csv
import sys
import re
from pathlib import Path


def clean_text(x: str) -> str:
    if x is None:
        return x
    y = re.sub(r"\[\s*\]", "", x)          # remove empty []
    y = re.sub(r"\s{2,}", " ", y).strip()  # collapse spaces
    return y


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV (UTF-8/UTF-8-SIG)")
    ap.add_argument("--out", dest="out", required=True, help="Output CSV path (in-place allowed)")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)

    # Read (detect encoding UTF-8/UTF-8-SIG)
    data = []
    with open(inp, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        headers = r.fieldnames or []
        for row in r:
            for col in ("keyword", "keyword_sanitized"):
                if col in row and row[col] is not None:
                    row[col] = clean_text(row[col])
            data.append(row)

    # Write back
    with open(outp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(data)

    print(f"OK: cleaned empty [] pairs in {len(data)} rows -> {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
