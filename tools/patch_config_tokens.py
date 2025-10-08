#!/usr/bin/env python3
# tools/patch_config_tokens.py
"""
Patch 'config' sheet in data/seeds.xlsx with intent tokens table.

- Creates a timestamped backup of the Excel file before writing.
- If 'config' sheet is missing, it will be created with defaults.
- Adds or updates rows for (token, weight, enabled) in a robust, case-insensitive way.
- Preserves all other sheets and cells (by re-writing with pandas).

Usage:
  python -u tools/patch_config_tokens.py \
    --excel-in data/seeds.xlsx \
    --dry-run  # optional, show changes only
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

KST = timezone(timedelta(hours=9))

# Default token set (Korean apparel context)
DEFAULT_TOKENS: List[Tuple[str, float, bool]] = [
    ("빅사이즈", 1.00, True),
    ("임산부", 0.90, True),
    ("하객", 0.70, True),
    ("홈웨어", 0.60, True),
    ("니트", 0.50, True),
    ("롱", 0.50, True),
    ("후드", 0.40, True),
    ("맨투맨", 0.40, True),
    ("폴라", 0.40, True),
    ("기모", 0.30, True),
]

# ---------- small utils ----------

def _now_str() -> str:
    return datetime.now(KST).strftime("%Y%m%d_%H%M%S")

def _detect_col(cols: List[str], names: List[str]) -> Optional[str]:
    cl = [c.lower() for c in cols]
    for n in names:
        if n.lower() in cl:
            return cols[cl.index(n.lower())]
    return None

def _ensure_cols(df: pd.DataFrame, required: List[str]) -> pd.DataFrame:
    for c in required:
        if c not in df.columns:
            df[c] = pd.Series([None] * len(df))
    # move required to the rightmost end for readability (keep original order otherwise)
    other = [c for c in df.columns if c not in required]
    return df[other + required]

def _to_bool(x) -> Optional[bool]:
    s = str(x).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off"}:
        return False
    return None

# ---------- main patcher ----------

def patch_tokens(excel_in: Path, tokens: List[Tuple[str, float, bool]], dry_run: bool = False) -> Dict[str, int]:
    if not excel_in.exists():
        raise SystemExit(f"ERROR: Excel not found → {excel_in}")

    # read all sheets
    xls = pd.read_excel(excel_in, sheet_name=None, engine="openpyxl")

    # ensure config sheet
    if "config" not in xls:
        cfg = pd.DataFrame({
            "W_intent": [0.55],
            "W_competition": [0.45],
        })
        xls["config"] = cfg

    cfg = xls["config"].copy()
    cfg_cols = list(cfg.columns)

    # find or create token/weight/enabled columns (case-insensitive)
    token_col = _detect_col(cfg_cols, ["token", "tokens", "intent_token"]) or "token"
    weight_col = _detect_col(cfg_cols, ["weight", "w", "score"]) or "weight"
    enabled_col = _detect_col(cfg_cols, ["enabled", "enable", "active"]) or "enabled"

    if token_col not in cfg.columns:
        cfg[token_col] = pd.Series([None] * len(cfg))
    if weight_col not in cfg.columns:
        cfg[weight_col] = pd.Series([None] * len(cfg))
    if enabled_col not in cfg.columns:
        cfg[enabled_col] = pd.Series([None] * len(cfg))

    # build a lookup for existing tokens (case-insensitive, trimmed)
    existing: Dict[str, int] = {}
    if cfg[token_col].notna().any():
        for idx, val in cfg[token_col].items():
            key = str(val).strip().lower()
            if key:
                existing[key] = idx

    added, updated = 0, 0
    for tok, w, en in tokens:
        key = str(tok).strip()
        if not key:
            continue
        k_lower = key.lower()
        if k_lower in existing:
            i = existing[k_lower]
            # update weight/enabled (keep other columns intact)
            prev_w = cfg.at[i, weight_col]
            prev_e = cfg.at[i, enabled_col]
            cfg.at[i, weight_col] = float(w)
            cfg.at[i, enabled_col] = bool(en)
            # count update only if changed
            if prev_w != float(w) or _to_bool(prev_e) != bool(en):
                updated += 1
        else:
            # append new row with token values (others NaN)
            new_row = {c: None for c in cfg.columns}
            new_row[token_col] = key
            new_row[weight_col] = float(w)
            new_row[enabled_col] = bool(en)
            cfg = pd.concat([cfg, pd.DataFrame([new_row])], ignore_index=True)
            added += 1

    # reorder to keep token block at the end (preserve other columns first)
    cfg = _ensure_cols(cfg, [token_col, weight_col, enabled_col])

    if dry_run:
        print("---- DRY RUN (no write) ----")
        print(f"Would add: {added}, update: {updated}")
        print(cfg.tail(max(5, len(tokens))).to_string(index=False))
        return {"added": added, "updated": updated, "written": 0}

    # backup original xlsx
    bak = excel_in.with_suffix(excel_in.suffix + f".bak_{_now_str()}")
    shutil.copy(excel_in, bak)

    # write back all sheets (replace config only)
    xls["config"] = cfg
    with pd.ExcelWriter(excel_in, engine="openpyxl", mode="w") as xw:
        for name, df in xls.items():
            # ensure at least 1 row
            if isinstance(df, pd.DataFrame) and df.shape[0] == 0:
                df = pd.DataFrame({c: [] for c in df.columns})
            df.to_excel(xw, index=False, sheet_name=name)

    print(f"[OK] Patched tokens in: {excel_in}")
    print(f"[OK] Backup: {bak}")
    print(f"[OK] Added: {added}, Updated: {updated}")
    return {"added": added, "updated": updated, "written": 1}

# ---------- CLI ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel-in", type=Path, default=Path("data/seeds.xlsx"))
    ap.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = ap.parse_args()

    stats = patch_tokens(args.excel_in, DEFAULT_TOKENS, dry_run=args.dry_run)
    # 사용: 결과를 한 줄 요약으로 출력해 F841 회피 + 실행 피드백 제공
    print(f"[SUMMARY] tokens added={stats.get('added',0)}, updated={stats.get('updated',0)}, written={stats.get('written',0)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
