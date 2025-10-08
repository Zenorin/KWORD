#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Keyword Scoring (Free Edition)

✅ Stage 1-1: Excel Loader (preserve seed duplicates)
✅ Stage 1-2: Parse scoring weights from 'config' sheet + auto re-normalize (sum=1)
✅ Stage 1-3: Parse intent tokens from 'config' sheet (token/weight/enabled)
✅ Stage 1-4: Parse extra prohibited words from 'config' sheet and merge with JSON defaults
✅ Stage 1-5: Apply precedence (CLI > Excel > Defaults) for weights & tokens
✅ Stage 2-1: Sanitizer — partial-match removal (KR), normalization, logging
✅ Stage 2-2: Expansion — Naver Suggest (free), sanitized related keywords per seed

Next stages (to be implemented later):
- Competition (Coupang/Naver search counts), Scoring, Outputs
"""

import argparse
import json
import math
import os
import re
import sys
import time
from typing import Tuple, Dict, Any, Optional, List

import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone,timezone
import datetime as _dt

BASE_DIR = os.environ.get("BASE_DIR", "/workspaces/KWORD")

DEFAULT_WEIGHTS = {"W_intent": 0.55, "W_competition": 0.45}

DEFAULT_TOKENS = [
    {"token": "빅사이즈", "weight": 1.0, "enabled": True},
    {"token": "임산부", "weight": 0.9, "enabled": True},
    {"token": "하객", "weight": 0.7, "enabled": True},
    {"token": "홈웨어", "weight": 0.6, "enabled": True},
    {"token": "니트", "weight": 0.5, "enabled": True},
    {"token": "롱", "weight": 0.5, "enabled": True},
    {"token": "후드", "weight": 0.4, "enabled": True},
    {"token": "맨투맨", "weight": 0.4, "enabled": True},
    {"token": "폴라", "weight": 0.4, "enabled": True},
    {"token": "기모", "weight": 0.3, "enabled": True},
]

DEFAULT_PROHIBITED = {
    "words": [
        "즉시 할인",
        "선착순",
        "무료",
        "무료 배송",
        "1위",
        "인기",
        "신상품",
        "신제품",
        "베스트",
        "추천",
        "특가",
        "이벤트",
        "적립",
        "가격",
        "쿠폰",
        "배송비",
        "할인율",
        "세일",
        "한정",
        "좋은",
        "최고",
        "초강력",
        "완벽",
        "최상",
        "가성비",
        "품질",
        "긴급",
        "특별 할인",
        "정품",
        "오리지널",
        "병행수입",
        "가짜",
        "진품",
    ],
    "symbols": [
        "!",
        "?",
        "★",
        "☆",
        "◆",
        "◇",
        "■",
        "□",
        "●",
        "○",
        "✔",
        "✅",
        "※",
        "【",
        "】",
        "「",
        "」",
        "『",
        "』",
        "◀",
        "▶",
        "▲",
        "▼",
        "☞",
        "☜",
    ],
}


# -------------------------
# Utilities
# -------------------------
def _normalize_colnames(cols):
    """Trim and lower-case column names for robust matching."""
    return [str(c).strip().lower() for c in cols]


def _cell_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def _ieq(a: str, b: str) -> bool:
    """Case-insensitive, trimmed equality."""
    return str(a).strip().lower() == str(b).strip().lower()


def _to_bool(s: str) -> bool:
    s = str(s).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def _safe_float(s: str, default: float = 0.0) -> float:
    try:
        f = float(str(s).strip())
        return max(f, 0.0)
    except Exception:
        return default


def _clean_term(s: str) -> str:
    """Trim and collapse internal whitespace to single spaces."""
    s = _cell_str(s)
    return " ".join(s.split())


def _collapse_spaces(s: str) -> str:
    # collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    # tidy spaces around common punctuation
    s = re.sub(r"\s+([,./~\-_:;])", r"\1", s)
    s = re.sub(r"([,./~\-_:;])\s+", r"\1 ", s)
    return s.strip()


def _sorted_desc_by_len(terms: List[str]) -> List[str]:
    # longest first to avoid partial-overlap issues (e.g., "무료 배송" vs "무료")
    return sorted({t for t in (terms or []) if t}, key=lambda x: len(x), reverse=True)


# -------------------------
# Stage 1-1: Load seeds (duplicates preserved)
# -------------------------
def load_seeds_excel(path: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load 'seeds' sheet from the Excel file, preserving duplicates.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input Excel not found: {path}")
    try:
        df = pd.read_excel(path, sheet_name="seeds", dtype=str)
    except ValueError as e:
        raise ValueError(f"Failed to read sheet 'seeds' from {path}: {e}")
    if df.empty:
        raise ValueError("Sheet 'seeds' is empty. Please provide at least one row.")

    df.columns = _normalize_colnames(df.columns)
    if "keyword" not in df.columns:
        raise ValueError(
            "Sheet 'seeds' must contain a 'keyword' column (case-insensitive)."
        )
    if "category" not in df.columns:
        df["category"] = ""

    df["keyword"] = df["keyword"].astype(str)
    df["category"] = df["category"].astype(str)

    total_rows = len(df)
    unique_rows = df["keyword"].nunique(dropna=False)
    duplicate_count = total_rows - unique_rows

    meta = {
        "path": path,
        "rows_total": total_rows,
        "rows_unique_by_keyword": unique_rows,
        "rows_duplicates_by_keyword": duplicate_count,
        "head_preview": df.head(min(5, len(df))).to_dict(orient="records"),
    }
    return df, meta


# -------------------------
# Stage 1-2 helper: locate header blocks in config
# -------------------------
def _find_header_position(
    conf_df: pd.DataFrame, header_seq: List[str]
) -> Optional[Tuple[int, int]]:
    """
    Find a header row/col in a headerless DataFrame (sheet read with header=None),
    matching the sequence in header_seq (e.g., ["key","value"] or ["token","weight","enabled"]).
    Returns (row_idx, col_idx) of the first header cell or None.
    """
    H, W = conf_df.shape
    n = len(header_seq)
    for r in range(H):
        for c in range(W - n + 1):
            ok = True
            for k in range(n):
                if not _ieq(_cell_str(conf_df.iat[r, c + k]), header_seq[k]):
                    ok = False
                    break
            if ok:
                return r, c
    return None


# -------------------------
# Stage 1-2: Parse weights from 'config' sheet
# -------------------------
def _parse_weights_block(conf_df: pd.DataFrame) -> Dict[str, float]:
    if conf_df is None or conf_df.empty:
        return DEFAULT_WEIGHTS.copy()

    pos = _find_header_position(conf_df, ["key", "value"])
    if not pos:
        return DEFAULT_WEIGHTS.copy()

    r0, c0 = pos
    weights: Dict[str, float] = {}
    r = r0 + 1
    H, W = conf_df.shape
    while r < H:
        key = _cell_str(conf_df.iat[r, c0]) if c0 < W else ""
        val = _cell_str(conf_df.iat[r, c0 + 1]) if (c0 + 1) < W else ""
        if key == "" and val == "":
            break
        if key != "":
            fval = _safe_float(val, default=float(DEFAULT_WEIGHTS.get(key, 0.0)))
            weights[key] = fval
        r += 1

    merged = DEFAULT_WEIGHTS.copy()
    for k, v in weights.items():
        merged[k] = v

    w_intent = float(merged.get("W_intent", DEFAULT_WEIGHTS["W_intent"]))
    w_comp = float(merged.get("W_competition", DEFAULT_WEIGHTS["W_competition"]))
    total = w_intent + w_comp
    if not math.isfinite(total) or total <= 0:
        w_intent, w_comp = (
            DEFAULT_WEIGHTS["W_intent"],
            DEFAULT_WEIGHTS["W_competITION"]
            if "W_competITION" in DEFAULT_WEIGHTS
            else DEFAULT_WEIGHTS["W_competition"],
        )
        total = w_intent + w_comp

    return {"W_intent": w_intent / total, "W_competition": w_comp / total}


def parse_weights_from_config(xls_path: str) -> Dict[str, float]:
    if not os.path.exists(xls_path):
        return DEFAULT_WEIGHTS.copy()
    try:
        conf_df = pd.read_excel(xls_path, sheet_name="config", header=None, dtype=str)
    except Exception:
        return DEFAULT_WEIGHTS.copy()
    return _parse_weights_block(conf_df)


# -------------------------
# Stage 1-3: Parse intent tokens from 'config' sheet
# -------------------------
def _parse_tokens_block(conf_df: pd.DataFrame) -> Dict[str, float]:
    if conf_df is None or conf_df.empty:
        return {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }

    pos = _find_header_position(conf_df, ["token", "weight", "enabled"])
    if not pos:
        return {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }

    r0, c0 = pos
    enabled_tokens: Dict[str, float] = {}
    r = r0 + 1
    H, W = conf_df.shape
    while r < H:
        tok = _cell_str(conf_df.iat[r, c0]) if c0 < W else ""
        w_s = _cell_str(conf_df.iat[r, c0 + 1]) if (c0 + 1) < W else ""
        en_s = _cell_str(conf_df.iat[r, c0 + 2]) if (c0 + 2) < W else ""

        if tok == "" and w_s == "" and en_s == "":
            break

        if tok != "":
            weight = _safe_float(w_s, default=0.0)
            enabled = _to_bool(en_s) if en_s != "" else True
            if enabled and weight > 0.0:
                enabled_tokens[tok] = weight
        r += 1

    if not enabled_tokens:
        return {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }
    return enabled_tokens


def parse_tokens_from_config(xls_path: str) -> Dict[str, float]:
    if not os.path.exists(xls_path):
        return {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }
    try:
        conf_df = pd.read_excel(xls_path, sheet_name="config", header=None, dtype=str)
    except Exception:
        return {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }
    return _parse_tokens_block(conf_df)


# -------------------------
# Stage 1-4: Parse extra prohibited words from 'config' sheet + merge
# -------------------------
def _parse_prohibited_words_block(conf_df: pd.DataFrame) -> List[str]:
    if conf_df is None or conf_df.empty:
        return []
    pos = _find_header_position(conf_df, ["word", "enabled"])
    if not pos:
        return []
    r0, c0 = pos
    out: List[str] = []
    r = r0 + 1
    H, W = conf_df.shape
    while r < H:
        w = _clean_term(conf_df.iat[r, c0]) if c0 < W else ""
        en_s = _cell_str(conf_df.iat[r, c0 + 1]) if (c0 + 1) < W else ""
        if w == "" and en_s == "":
            break
        if w != "":
            if _to_bool(en_s) if en_s != "" else True:
                out.append(w)
        r += 1
    return out


def _parse_prohibited_symbols_block(conf_df: pd.DataFrame) -> List[str]:
    if conf_df is None or conf_df.empty:
        return []
    pos = _find_header_position(conf_df, ["symbol", "enabled"])
    if not pos:
        return []
    r0, c0 = pos
    out: List[str] = []
    r = r0 + 1
    H, W = conf_df.shape
    while r < H:
        s = _cell_str(conf_df.iat[r, c0]) if c0 < W else ""
        en_s = _cell_str(conf_df.iat[r, c0 + 1]) if (c0 + 1) < W else ""
        if s == "" and en_s == "":
            break
        if s != "":
            if _to_bool(en_s) if en_s != "" else True:
                out.append(s)
        r += 1
    return out


def load_default_prohibited(json_path: str) -> Dict[str, List[str]]:
    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            words = [
                _clean_term(w) for w in (data.get("words") or []) if _clean_term(w)
            ]
            symbols = [
                _cell_str(s) for s in (data.get("symbols") or []) if _cell_str(s)
            ]
            return {"words": words, "symbols": symbols}
        except Exception:
            pass
    return {
        "words": [_clean_term(w) for w in DEFAULT_PROHIBITED["words"]],
        "symbols": list(DEFAULT_PROHIBITED["symbols"]),
    }


def parse_prohibited_from_config(xls_path: str) -> Dict[str, List[str]]:
    if not os.path.exists(xls_path):
        return {"words": [], "symbols": []}
    try:
        conf_df = pd.read_excel(xls_path, sheet_name="config", header=None, dtype=str)
    except Exception:
        return {"words": [], "symbols": []}
    extra_words = _parse_prohibited_words_block(conf_df)
    extra_symbols = _parse_prohibited_symbols_block(conf_df)
    return {"words": extra_words, "symbols": extra_symbols}


def merge_prohibited(
    base: Dict[str, List[str]], extra: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    def _merge(a: List[str], b: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in (a or []) + (b or []):
            x2 = _clean_term(x)
            if x2 and x2 not in seen:
                seen.add(x2)
                out.append(x2)
        return out

    return {
        "words": _merge(base.get("words", []), extra.get("words", [])),
        "symbols": _merge(base.get("symbols", []), extra.get("symbols", [])),
    }


# -------------------------
# Stage 1-5: Precedence (CLI > Excel > Defaults)
# -------------------------
def _parse_tokens_cli(cli_str: Optional[str]) -> Dict[str, float]:
    """
    Parse CLI tokens string like "빅사이즈:1.2;임산부:0.9,하객:0.7"
    separators: ';' or ',' ; each item is "token:weight"
    """
    out: Dict[str, float] = {}
    if not cli_str:
        return out
    raw = [p for p in cli_str.replace(";", ",").split(",") if p.strip()]
    for part in raw:
        if ":" not in part:
            continue
        tok, w = part.split(":", 1)
        tok = _clean_term(tok)
        wv = _safe_float(w, default=0.0)
        if tok and wv > 0:
            out[tok] = wv
    return out


def apply_precedence(
    weights_excel: Dict[str, float],
    tokens_excel: Dict[str, float],
    args: argparse.Namespace,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Returns (effective_weights, effective_tokens)
    Precedence: CLI > Excel > Defaults.
    """
    # Weights
    w_intent = (
        args.W_intent
        if args.W_intent is not None
        else weights_excel.get("W_intent", DEFAULT_WEIGHTS["W_intent"])
    )
    w_comp = (
        args.W_competition
        if args.W_competition is not None
        else weights_excel.get("W_competition", DEFAULT_WEIGHTS["W_competition"])
    )
    total = (w_intent or 0.0) + (w_comp or 0.0)
    if not math.isfinite(total) or total <= 0:
        w_intent, w_comp = (
            DEFAULT_WEIGHTS["W_intent"],
            DEFAULT_WEIGHTS.get("W_competition", 0.45),
        )
        total = w_intent + w_comp
    eff_weights = {"W_intent": w_intent / total, "W_competition": w_comp / total}

    # Tokens
    tokens_cli = _parse_tokens_cli(args.tokens)
    if tokens_cli:
        eff_tokens = tokens_cli
    elif tokens_excel:
        eff_tokens = tokens_excel
    else:
        eff_tokens = {
            t["token"]: t["weight"] for t in DEFAULT_TOKENS if t.get("enabled", True)
        }

    return eff_weights, eff_tokens


# -------------------------
# Stage 2-1: Sanitizer — partial-match removal (KR), normalization, logging
# -------------------------
def sanitize_text(
    text: str, words: List[str], symbols: List[str]
) -> Tuple[str, Dict[str, Any]]:
    """
    Remove prohibited words (partial match) and symbols (literal) from text.
    Only the matched substring is removed; surrounding content stays.
    Returns (sanitized_text, detail_log).
    """
    original = _cell_str(text)
    cur = original
    removed_words: List[str] = []
    removed_symbols: List[str] = []

    # Remove words (longest match first), case-insensitive for safety
    for w in _sorted_desc_by_len(words):
        pat = re.compile(re.escape(w), flags=re.IGNORECASE)
        cur, n = pat.subn("", cur)
        if n > 0:
            removed_words.append(w)

    # Remove symbols literally (log which were present)
    if symbols:
        before_scan = cur
        present_syms = [s for s in symbols if s and s in before_scan]
        if present_syms:
            sym_class = "[" + "".join(re.escape(s) for s in present_syms) + "]"
            cur, n = re.subn(sym_class, "", cur)
            if n > 0:
                removed_symbols = present_syms

    # Normalize spaces / simple punctuation spacing
    cur = _collapse_spaces(cur)

    detail = {
        "original": original,
        "sanitized": cur,
        "removed_words": removed_words,
        "removed_symbols": removed_symbols,
        "changed": original != cur,
    }
    return cur, detail


def sanitize_df(
    df: pd.DataFrame, words: List[str], symbols: List[str]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    logs = []
    out = df.copy()
    out["keyword_sanitized"] = df["keyword"].astype(str)
    out["sanitized_changed"] = False

    for idx, row in out.iterrows():
        sanitized, info = sanitize_text(row["keyword"], words, symbols)
        out.at[idx, "keyword_sanitized"] = sanitized
        out.at[idx, "sanitized_changed"] = info["changed"]
        logs.append(
            {
                "row_index": idx,
                "keyword_original": info["original"],
                "keyword_sanitized": info["sanitized"],
                "removed_words": ", ".join(info["removed_words"])
                if info["removed_words"]
                else "",
                "removed_symbols": ", ".join(info["removed_symbols"])
                if info["removed_symbols"]
                else "",
                "changed": info["changed"],
            }
        )

    log_df = pd.DataFrame(logs)
    return out, log_df


# -------------------------
# Stage 2-2: Expansion — Naver Suggest
# -------------------------
NAVER_SUGGEST_URL = "https://ac.search.naver.com/nx/ac"


def _walk_strings(x):
    """Extract all string leaves from nested lists/dicts."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for y in x:
            yield from _walk_strings(y)
    elif isinstance(x, dict):
        for y in x.values():
            yield from _walk_strings(y)


def fetch_naver_suggest(
    seed: str, ua: str, timeout: float, retries: int, sleep_sec: float
) -> List[str]:
    """
    Call Naver Suggest (unofficial). Returns a list of suggestion strings.
    Robust to minor shape changes by walking all string leaves.
    """
    params = {
        "q": seed,
        "st": 111,
        "r_format": "json",
        "q_enc": "utf-8",
        "r_or": 0,
        "frm": "shopping",
        "con": "1",
    }
    headers = {"User-Agent": ua, "Accept": "application/json,*/*"}
    last_err = None
    for attempt in range(max(1, retries)):
        try:
            r = requests.get(
                NAVER_SUGGEST_URL, params=params, headers=headers, timeout=timeout
            )
            if r.ok:
                data = r.json()
                strings = list(_walk_strings(data.get("items", [])))
                # Post-filter: keep near the seed topic (simple heuristic)
                cands = []
                seen = set()
                for s in strings:
                    s2 = _clean_term(s)
                    if not s2 or s2 in seen:
                        continue
                    seen.add(s2)
                    cands.append(s2)
                return cands
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(sleep_sec)
    # On failure, return empty list (pipeline continues)
    if last_err:
        print(
            f"[WARN] Naver suggest failed for seed='{seed}': {last_err}",
            file=sys.stderr,
        )
    return []


def expand_for_seed(
    seed_idx: int,
    seed_orig: str,
    seed_sanitized: str,
    max_each: int,
    ua: str,
    timeout: float,
    retries: int,
    sleep_sec: float,
    proh_words: List[str],
    proh_symbols: List[str],
) -> List[Dict[str, Any]]:
    """
    Expand one seed via Naver Suggest; also sanitize the suggestions.
    Returns list of rows.
    """
    if not seed_sanitized:
        return []
    # fetch
    suggestions = fetch_naver_suggest(
        seed_sanitized, ua=ua, timeout=timeout, retries=retries, sleep_sec=sleep_sec
    )
    out_rows: List[Dict[str, Any]] = []
    seen_rel = set()
    rank = 0
    for raw in suggestions:
        if raw.strip() == "" or _ieq(raw, seed_sanitized):
            continue
        # sanitize related
        rel_sanitized, _log = sanitize_text(raw, proh_words, proh_symbols)
        if rel_sanitized == "" or _ieq(rel_sanitized, seed_sanitized):
            continue
        # dedup per-seed by sanitized value
        if rel_sanitized in seen_rel:
            continue
        seen_rel.add(rel_sanitized)
        rank += 1
        out_rows.append(
            {
                "seed_index": seed_idx,
                "seed_original": seed_orig,
                "seed_sanitized": seed_sanitized,
                "related_original": raw,
                "related_sanitized": rel_sanitized,
                "source": "naver_suggest",
                "rank": rank,
            }
        )
        if rank >= max_each:
            break
    return out_rows


def expand_all(
    df_sanitized: pd.DataFrame,
    max_each: int,
    ua: str,
    timeout: float,
    retries: int,
    sleep_sec: float,
    proh_words: List[str],
    proh_symbols: List[str],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for idx, row in df_sanitized.iterrows():
        rows.extend(
            expand_for_seed(
                seed_idx=int(idx),
                seed_orig=row["keyword"],
                seed_sanitized=row["keyword_sanitized"],
                max_each=max_each,
                ua=ua,
                timeout=timeout,
                retries=retries,
                sleep_sec=sleep_sec,
                proh_words=proh_words,
                proh_symbols=proh_symbols,
            )
        )
        time.sleep(sleep_sec)
    return pd.DataFrame(rows)


# -------------------------
# Stage 3-1: Competition — Coupang / Naver search result counts
# -------------------------
def get_search_count_coupang(
    query: str, ua: str, timeout: float, retries: int, sleep_sec: float
) -> Optional[int]:
    url = "https://www.coupang.com/np/search"
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"}
    params = {"q": query}
    for _ in range(max(1, retries)):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.ok and r.text:
                m = re.search(r"검색\s*결과\s*([\d,]+)\s*개", r.text)
                if m:
                    return int(m.group(1).replace(",", ""))
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.select("ul.search-product-list li.search-product")
                if cards:
                    return len(cards)
        except Exception:
            pass
        time.sleep(sleep_sec)
    return None


def get_search_count_naver(
    query: str, ua: str, timeout: float, retries: int, sleep_sec: float
) -> Optional[int]:
    url = "https://search.shopping.naver.com/search/all"
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"}
    params = {"query": query}
    for _ in range(max(1, retries)):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.ok and r.text:
                t = r.text
                m = (
                    re.search(r"검색결과\s*([\d,]+)\s*개", t)
                    or re.search(r"총\s*([\d,]+)\s*건", t)
                    or re.search(r'"totalCount"\s*:\s*([\d,]+)', t)
                    or re.search(r'"total"\s*:\s*([\d,]+)', t)
                )
                if m:
                    return int(m.group(1).replace(",", ""))
        except Exception:
            pass
        time.sleep(sleep_sec)
    return None


def collect_competition(
    expanded_df: pd.DataFrame,
    site_mode: str,
    ua: str,
    timeout: float,
    retries: int,
    sleep_sec: float,
) -> pd.DataFrame:
    """
    For each related_sanitized, fetch Coupang/Naver result counts and compute comp_combined.
    comp_combined = log1p(coupang) + log1p(naver), missing -> 0.0
    """
    if expanded_df is None or expanded_df.empty:
        return pd.DataFrame(
            columns=[
                "seed_index",
                "seed_sanitized",
                "related_sanitized",
                "comp_coupang",
                "comp_naver",
                "comp_combined",
                "ts",
            ]
        )
    rows: List[Dict[str, Any]] = []
    for _, r in expanded_df.iterrows():
        kw = str(r.get("related_sanitized", "")).strip()
        if not kw:
            continue
        cpn = nav = None
        if site_mode in ("both", "coupang"):
            cpn = get_search_count_coupang(
                kw, ua=ua, timeout=timeout, retries=retries, sleep_sec=sleep_sec
            )
        if site_mode in ("both", "naver"):
            nav = get_search_count_naver(
                kw, ua=ua, timeout=timeout, retries=retries, sleep_sec=sleep_sec
            )
        comp_combined = (math.log1p(cpn) if cpn is not None else 0.0) + (
            math.log1p(nav) if nav is not None else 0.0
        )
        rows.append(
            {
                "seed_index": r.get("seed_index"),
                "seed_sanitized": r.get("seed_sanitized"),
                "related_sanitized": kw,
                "comp_coupang": cpn,
                "comp_naver": nav,
                "comp_combined": round(comp_combined, 6),
                "ts": datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            }
        )
        time.sleep(sleep_sec)
    return pd.DataFrame(rows)


# -------------------------
# CLI & main
# -------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Keyword Scoring (Free Edition) — Stages 1-1..2-2 (config + precedence + sanitizer + expansion)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Primary input
    p.add_argument(
        "--in",
        dest="in_path",
        default=os.path.join(BASE_DIR, "data/seeds.xlsx"),
        help="Path to Excel file with 'seeds' and 'config' sheets",
    )

    # Config paths
    p.add_argument(
        "--prohibited-json",
        default=os.path.join(BASE_DIR, "config/prohibited_words_ko.json"),
        help="Path to default prohibited words/symbols JSON",
    )

    # CLI overrides
    p.add_argument(
        "--W-intent",
        dest="W_intent",
        type=float,
        default=None,
        help="Override weight for intent component (CLI > Excel > Defaults)",
    )
    p.add_argument(
        "--W-competition",
        dest="W_competition",
        type=float,
        default=None,
        help="Override weight for competition component (CLI > Excel > Defaults)",
    )
    p.add_argument(
        "--tokens",
        type=str,
        default=None,
        help="Override tokens as '토큰:가중치;토큰:가중치' or comma-separated",
    )

    # Outputs
    p.add_argument(
        "--competition-out",
        default=os.path.join(BASE_DIR, "output/competition_counts.csv"),
        help="Path to write competition counts CSV",
    )
    p.add_argument(
        "--sanitized-out",
        default=os.path.join(BASE_DIR, "output/sanitized_keywords.csv"),
        help="Path to write sanitized keyword preview CSV",
    )
    p.add_argument(
        "--expanded-out",
        default=os.path.join(BASE_DIR, "output/expanded_keywords.csv"),
        help="Path to write expanded related keywords CSV",
    )

    # Expansion controls
    p.add_argument(
        "--expand",
        type=int,
        default=20,
        help="Related keywords per seed (after sanitization)",
    )
    p.add_argument(
        "--sleep", type=float, default=0.7, help="Delay between HTTP requests (seconds)"
    )
    p.add_argument("--retries", type=int, default=2, help="Max retries per request")
    p.add_argument(
        "--timeout", type=float, default=6.0, help="Per-request timeout seconds"
    )
    p.add_argument(
        "--site-mode",
        choices=["both", "coupang", "naver"],
        default="both",
        help="(reserved for later stages)",
    )
    p.add_argument("--ua", default="Mozilla/5.0 (Codespaces Expansion Stage)")

    p.add_argument("--topN-report", type=int, default=0)
    p.add_argument("--no-html", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    in_path = args.in_path

    print("=== Stage 1-1: Excel Loader (preserve duplicates) ===")
    print(f"[INFO] Base dir     : {BASE_DIR}")
    print(f"[INFO] Input Excel  : {in_path}")

    try:
        df_seeds, meta = load_seeds_excel(in_path)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("[OK] Loaded 'seeds' sheet")
    print(f" - rows_total                 : {meta['rows_total']}")
    print(f" - rows_unique_by_keyword     : {meta['rows_unique_by_keyword']}")
    print(f" - rows_duplicates_by_keyword : {meta['rows_duplicates_by_keyword']}")
    print(" - head_preview (first rows):")
    for i, row in enumerate(meta["head_preview"], 1):
        print(
            f"   {i:02d}. keyword='{row.get('keyword', '')}', category='{row.get('category', '')}'"
        )

    # 1-2: weights (Excel)
    print("\n=== Stage 1-2: Parse weights from 'config' sheet (Excel) ===")
    weights_excel = parse_weights_from_config(in_path)
    print(
        f" - excel weights (normalized) : W_intent={weights_excel['W_intent']:.4f}, W_competition={weights_excel['W_competition']:.4f}"
    )

    # 1-3: tokens (Excel)
    print("\n=== Stage 1-3: Parse intent tokens from 'config' sheet (Excel) ===")
    tokens_excel = parse_tokens_from_config(in_path)
    print(f" - excel tokens count         : {len(tokens_excel)}")
    preview_items = list(tokens_excel.items())[:10]
    preview_str = (
        ", ".join([f"{k}:{v:.2f}" for k, v in preview_items])
        if preview_items
        else "(none)"
    )
    print(f" - excel tokens preview       : {preview_str}")

    # 1-4: prohibited merge
    print("\n=== Stage 1-4: Prohibited words/symbols ===")
    base_proh = load_default_prohibited(args.prohibited_json)
    extra_proh = parse_prohibited_from_config(in_path)
    merged_proh = merge_prohibited(base_proh, extra_proh)
    print(
        f" - defaults (JSON)            : words={len(base_proh['words'])}, symbols={len(base_proh['symbols'])}"
    )
    print(
        f" - extras (config)            : words={len(extra_proh['words'])}, symbols={len(extra_proh['symbols'])}"
    )
    print(
        f" - merged total               : words={len(merged_proh['words'])}, symbols={len(merged_proh['symbols'])}"
    )

    # 1-5: precedence
    print("\n=== Stage 1-5: Apply precedence (CLI > Excel > Defaults) ===")
    eff_weights, eff_tokens = apply_precedence(weights_excel, tokens_excel, args)
    total = eff_weights["W_intent"] + eff_weights["W_competition"]
    print(
        f" - effective weights          : W_intent={eff_weights['W_intent']:.4f}, W_competition={eff_weights['W_competition']:.4f} (sum={total:.4f})"
    )
    prev_eff = list(eff_tokens.items())[:10]
    prev_str = (
        ", ".join([f"{k}:{v:.2f}" for k, v in prev_eff]) if prev_eff else "(none)"
    )
    print(f" - effective tokens count     : {len(eff_tokens)}")
    print(f" - effective tokens preview   : {prev_str}")

    # 2-1: Sanitizer
    print(
        "\n=== Stage 2-1: Sanitizer (partial-match removal + normalization + logs) ==="
    )
    os.makedirs(os.path.dirname(args.sanitized_out), exist_ok=True)
    df_sanitized, log_df = sanitize_df(
        df_seeds, merged_proh["words"], merged_proh["symbols"]
    )
    changed_cnt = int(df_sanitized["sanitized_changed"].sum())
    print(f" - rows changed               : {changed_cnt} / {len(df_sanitized)}")
    changed_preview = df_sanitized[df_sanitized["sanitized_changed"]].head(10)
    if not changed_preview.empty:
        print(" - sample changes:")
        for _, r in changed_preview.iterrows():
            print(f"   • '{r['keyword']}' -> '{r['keyword_sanitized']}'")
    else:
        print(" - sample changes: (none)")

    merged_preview = df_sanitized.copy()
    if not log_df.empty:
        merged_preview = merged_preview.join(
            log_df.set_index("row_index"), how="left", lsuffix="", rsuffix="_log"
        )
    merged_preview.to_csv(args.sanitized_out, index=False, encoding="utf-8-sig")
    print(f" - saved sanitized preview    : {args.sanitized_out}")

    # 2-2: Expansion — Naver Suggest
    print("\n=== Stage 2-2: Expansion (Naver Suggest) ===")
    os.makedirs(os.path.dirname(args.expanded_out), exist_ok=True)
    expanded_df = expand_all(
        df_sanitized=df_sanitized,
        max_each=int(args.expand),
        ua=args.ua,
        timeout=float(args.timeout),
        retries=int(args.retries),
        sleep_sec=float(args.sleep),
        proh_words=merged_proh["words"],
        proh_symbols=merged_proh["symbols"],
    )
    print(f" - seeds processed            : {len(df_sanitized)}")
    print(f" - expanded rows              : {len(expanded_df)}")
    if not expanded_df.empty:
        print(" - sample expanded (top 10):")
        for _, r in expanded_df.head(10).iterrows():
            print(
                f"   • [{r['seed_sanitized']}] -> ({r['rank']:02d}) {r['related_sanitized']}"
            )

    expanded_df.to_csv(args.expanded_out, index=False, encoding="utf-8-sig")
    print(f" - saved expanded keywords    : {args.expanded_out}")

    # 3-1: Competition — Coupang/Naver result counts
    print("\n=== Stage 3-1: Competition (Coupang / Naver) ===")
    comp_df = collect_competition(
        expanded_df=expanded_df,
        site_mode=args.site_mode,
        ua=args.ua,
        timeout=float(args.timeout),
        retries=int(args.retries),
        sleep_sec=float(args.sleep),
    )
    print(f" - competition rows           : {len(comp_df)}")
    if not comp_df.empty:
        print(" - sample competition (top 10):")
        for _, r in comp_df.head(10).iterrows():
            print(
                f"   • {r['related_sanitized']} | coupang={r['comp_coupang']} naver={r['comp_naver']} | combined={r['comp_combined']:.4f}"
            )
    comp_out = args.competition_out
    os.makedirs(os.path.dirname(comp_out), exist_ok=True)
    comp_df.to_csv(comp_out, index=False, encoding="utf-8-sig")
    print(f" - saved competition counts   : {comp_out}")

    print("\nNext steps:")
    print(" - Scoring (normalize intent/competition with weights) → Reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
