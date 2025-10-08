#!/usr/bin/env python3
# tools/patch_prohibited_lists.py
"""
Patch 'config' sheet in data/seeds.xlsx to upsert prohibited words/symbols.

- Creates a timestamped backup before writing.
- Works with flexible config layouts:
  * If columns ["key","value"] exist -> upsert rows:
      key = "prohibited_words" / "prohibited_symbols"
      value = newline-separated list
  * Else creates a minimal ["key","value"] area and appends the two keys.
- Merges (union) existing entries with provided extras, keeping original order.
- Auto-detects separators: comma / semicolon / pipe / whitespace / newline.

Usage:
  python -u tools/patch_prohibited_lists.py --excel-in data/seeds.xlsx
  # optional custom extras:
  python -u tools/patch_prohibited_lists.py --excel-in data/seeds.xlsx \
      --add-words "특가,세일,할인,쿠폰" \
      --add-symbols "【,】,『,』,★,♡,❤,※"
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import re

KST = timezone(timedelta(hours=9))

# --- Recommended extras (safe defaults for KR e-commerce text noise) ---
DEFAULT_WORDS: List[str] = [
    "특가", "세일", "할인", "쿠폰", "행사", "증정", "무료증정", "무료배송",
    "정품아님", "짝퉁", "광고", "ad", "sponsored"
]

DEFAULT_SYMBOLS: List[str] = [
    "【", "】", "［", "］", "『", "』", "「", "」",
    "★", "☆", "♡", "❤", "♥", "※", "❗", "❕", "❌", "✔",
]

SEP_RE = re.compile(r"[,\|\t;\n\r]+")

def _now_str() -> str:
    return datetime.now(KST).strftime("%Y%m%d_%H%M%S")

def _split_tokens(s: str) -> List[str]:
    s = str(s or "").strip()
    if not s:
        return []
    parts = SEP_RE.split(s)
    out: List[str] = []
    for p in parts:
        for t in p.strip().split():
            tt = t.strip()
            if tt:
                out.append(tt)
    return out

def _merge_tokens(existing: Iterable[str], extras: Iterable[str]) -> List[str]:
    seen = set()
    merged: List[str] = []
    for t in list(existing) + list(extras):
        tt = str(t).strip()
        if not tt or tt in seen:
            continue
        seen.add(tt)
        merged.append(tt)
    return merged

def _detect_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    cl = [c.lower() for c in cols]
    for name in candidates:
        if name.lower() in cl:
            return cols[cl.index(name.lower())]
    return None

def _ensure_kv(cfg: pd.DataFrame) -> Tuple[pd.DataFrame, str, str]:
    cols = list(cfg.columns)
    key_col = _detect_col(cols, ["key", "name", "metric", "k"]) or "key"
    val_col = _detect_col(cols, ["value", "val", "v"]) or "value"
    if key_col not in cfg.columns:
        cfg[key_col] = pd.Series([None] * len(cfg))
    if val_col not in cfg.columns:
        cfg[val_col] = pd.Series([None] * len(cfg))
    other = [c for c in cfg.columns if c not in (key_col, val_col)]
    cfg = cfg[other + [key_col, val_col]]
    return cfg, key_col, val_col

def _get_row_index_for_key(cfg: pd.DataFrame, key_col: str, target_key: str) -> Optional[int]:
    if key_col not in cfg.columns:
        return None
    for i, v in cfg[key_col].items():
        if str(v).strip().lower() == target_key.lower():
            return i
    return None

def _read_tokens_from_val(val: object) -> List[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    return _split_tokens(str(val))

def _write_tokens_to_val(tokens: List[str]) -> str:
    return "\n".join(tokens)

def patch_prohibited(excel_in: Path, add_words: List[str], add_symbols: List[str]) -> Tuple[int, int, Path]:
    if not excel_in.exists():
        raise SystemExit(f"ERROR: Excel not found → {excel_in}")

    xls = pd.read_excel(excel_in, sheet_name=None, engine="openpyxl")

    if "config" not in xls:
        xls["config"] = pd.DataFrame({"key": [], "value": []})
    cfg = xls["config"].copy()

    cfg, key_col, val_col = _ensure_kv(cfg)

    idx_words = _get_row_index_for_key(cfg, key_col, "prohibited_words")
    idx_symbols = _get_row_index_for_key(cfg, key_col, "prohibited_symbols")

    cur_words: List[str] = _read_tokens_from_val(cfg.at[idx_words, val_col]) if idx_words is not None else []
    cur_symbols: List[str] = _read_tokens_from_val(cfg.at[idx_symbols, val_col]) if idx_symbols is not None else []

    new_words = _merge_tokens(cur_words, add_words)
    new_symbols = _merge_tokens(cur_symbols, add_symbols)

    if idx_words is None:
        cfg.loc[len(cfg)] = {key_col: "prohibited_words", val_col: _write_tokens_to_val(new_words)}
    else:
        cfg.at[idx_words, val_col] = _write_tokens_to_val(new_words)

    if idx_symbols is None:
        cfg.loc[len(cfg)] = {key_col: "prohibited_symbols", val_col: _write_tokens_to_val(new_symbols)}
    else:
        cfg.at[idx_symbols, val_col] = _write_tokens_to_val(new_symbols)

    bak = excel_in.with_suffix(excel_in.suffix + f".bak_{_now_str()}")
    shutil.copy(excel_in, bak)

    xls["config"] = cfg
    with pd.ExcelWriter(excel_in, engine="openpyxl", mode="w") as xw:
        for name, df in xls.items():
            if isinstance(df, pd.DataFrame) and df.shape[0] == 0:
                df = pd.DataFrame({c: [] for c in df.columns})
            df.to_excel(xw, index=False, sheet_name=name)

    return len(new_words), len(new_symbols), bak

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel-in", type=Path, default=Path("data/seeds.xlsx"))
    ap.add_argument("--add-words", type=str, default="")
    ap.add_argument("--add-symbols", type=str, default="")
    args = ap.parse_args()

    extra_words = _merge_tokens(DEFAULT_WORDS, _split_tokens(args.add_words))
    extra_symbols = _merge_tokens(DEFAULT_SYMBOLS, _split_tokens(args.add_symbols))

    w_count, s_count, bak = patch_prohibited(args.excel_in, extra_words, extra_symbols)
    print(f"[OK] Prohibited lists upserted. words={w_count}, symbols={s_count}")
    print(f"[OK] Backup saved at: {bak}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
