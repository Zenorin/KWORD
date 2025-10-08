#!/usr/bin/env python3
# tools/update_prd_snapshot.py
"""
Update the Snapshot section in the PRD markdown with actual artifacts.

- If PRD file does not exist, it will be created with a minimal header.
- Locates "## 14. Snapshot" (or any "## Snapshot") section; replaces it.
  If not found, appends a fresh snapshot at the end.
- Writes CSV previews (top 3), lists artifacts, and prints a success line.

Usage:
  python -u tools/update_prd_snapshot.py \
    --prd /mnt/data/prd_keyword_scoring_free_edition.md \
    --sanitized output/sanitized_keywords.csv \
    --expanded output/expanded_keywords.csv \
    --competition output/competition_counts.csv \
    --scores-csv output/keyword_scores_free.csv \
    --scores-xlsx output/keyword_scores_free.xlsx \
    --html output/report.html \
    --cmdfile logs/last_cmd.txt   # optional
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

KST = dt.timezone(dt.timedelta(hours=9))


def _exists(p: Optional[Path]) -> bool:
    return bool(p and p.exists())


def _peek_csv(path: Path, n: int = 3) -> Tuple[int, list, str]:
    # Robust read with UTF-8 variants
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeError:
        df = pd.read_csv(path, encoding="utf-8")

    rows = len(df)
    cols = df.columns.tolist()

    # Build a small preview table (Top-N) with truncation per cell
    head = df.head(n).copy()

    def _fmt(val: object) -> str:
        s = str(val)
        return s if len(s) <= 40 else s[:37] + "..."

    # Avoid deprecated DataFrame.applymap; map each column
    for c in head.columns:
        head[c] = head[c].map(_fmt)

    table = head.to_string(index=False)
    return rows, cols, table


def _build_snapshot(args) -> str:
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines: List[str] = []
    lines.append(f"## 14. Snapshot — v0.3.0 — {now}")
    lines.append("**Execution Context**")
    lines.append("- Timezone: Asia/Seoul (KST)")
    lines.append("")
    lines.append("**Artifacts**")

    def _mark(p: Optional[Path]) -> str:
        return f"✅ {p}" if _exists(p) else f"⏳ {p} (pending)"

    lines.append(f"- {_mark(args.sanitized)}")
    lines.append(f"- {_mark(args.expanded)}")
    lines.append(f"- {_mark(args.competition)}")
    lines.append(f"- {_mark(args.scores_csv)}")
    lines.append(f"- {_mark(args.scores_xlsx)}")
    lines.append(f"- {_mark(args.html)}")

    # Commands
    lines.append("\n**Commands (latest)**")
    if args.cmdfile and _exists(args.cmdfile):
        cmd = Path(args.cmdfile).read_text(encoding="utf-8")
        lines.append("```bash")
        lines.append(cmd.strip())
        lines.append("```")
    else:
        lines.append("_Commands not captured; see WBS Cheat Sheet._")

    # CSV previews
    lines.append("\n**Previews (Top 3)**")
    for label, p in [
        ("Sanitized", args.sanitized),
        ("Expanded", args.expanded),
        ("Competition", args.competition),
        ("Scores", args.scores_csv),
    ]:
        if _exists(p):
            rows, cols, table = _peek_csv(p)
            lines.append(f"\n**{label}** — rows={rows} | columns={cols}")
            lines.append("```")
            lines.append(table)
            lines.append("```")
        else:
            lines.append(f"\n**{label}** — pending")

    lines.append("\n> Note: previews truncated to 3 rows; see full CSVs in `output/`.")
    return "\n".join(lines) + "\n"


def _replace_snapshot(prd_md: Path, new_snapshot_md: str) -> str:
    """
    Replace (or append) the Snapshot section inside PRD text.
    """
    text = prd_md.read_text(encoding="utf-8")

    # Find the start of Snapshot section: matches "## 14. Snapshot" or "## Snapshot"
    pat = re.compile(r"(?im)^\s*##\s*(?:14\.\s*)?Snapshot\b.*?$")
    m = pat.search(text)
    if not m:
        # Append at end if not found
        return text.rstrip() + "\n\n" + new_snapshot_md

    start = m.start()

    # Find the next H2 header to delimit the end of snapshot section
    pat_next = re.compile(r"(?m)^\s*##\s+\d+\.\s+")
    m2 = pat_next.search(text, pos=m.end())
    if not m2:
        # Replace until end of file
        return text[:start] + new_snapshot_md
    else:
        end = m2.start()
        return text[:start] + new_snapshot_md + text[end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prd", type=Path, required=True)
    ap.add_argument("--sanitized", type=Path, required=True)
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--competition", type=Path, required=True)
    ap.add_argument("--scores-csv", type=Path, required=True)
    ap.add_argument("--scores-xlsx", type=Path, required=False)
    ap.add_argument("--html", type=Path, required=False)
    ap.add_argument("--cmdfile", type=Path, required=False)
    args = ap.parse_args()

    # Ensure PRD exists (auto-create minimal header)
    if not args.prd.exists():
        args.prd.parent.mkdir(parents=True, exist_ok=True)
        minimal = "# PRD — KWORD: Keyword Scoring (Free Edition)\n\n"
        args.prd.write_text(minimal, encoding="utf-8")

    snapshot_md = _build_snapshot(args)
    updated = _replace_snapshot(args.prd, snapshot_md)
    args.prd.write_text(updated, encoding="utf-8")
    print("[OK] Snapshot updated in:", args.prd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
