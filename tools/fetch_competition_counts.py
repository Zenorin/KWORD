#!/usr/bin/env python3
# tools/fetch_competition_counts.py
"""
Incremental competition fetcher with robust column detection and
header-compatible append writes.

- Reads expanded/sanitized CSVs and detects keyword/seed columns smartly.
- Appends to an existing output CSV using its header if present.
- Survives interrupts (flush after each row) and resumes by skipping
  already-processed (seed, keyword) pairs.

Usage:
  python tools/fetch_competition_counts.py \
    --expanded-in output/expanded_keywords.csv \
    --sanitized-in output/sanitized_keywords.csv \
    --out output/competition_counts.csv \
    --site-mode both --sleep 0.8 --retries 2 --timeout 12
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

try:
    import requests
    from bs4 import BeautifulSoup  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"Missing dependency: requests / beautifulsoup4 ({e})", file=sys.stderr)
    raise

# Target sites
NAVER_SHOPPING_URL = "https://search.shopping.naver.com/search/all?query={q}"
NAVER_GENERAL_URL = "https://search.naver.com/search.naver?query={q}"
COUPANG_URL = "https://www.coupang.com/np/search?component=&q={q}"

# Default headers
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
EXTRA_HEADERS = {
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Referer": "https://www.naver.com/",
}

# -------- Utilities --------


def _now_iso_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r)


def _detect_col(cols: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    """Exact/ci match among candidates."""
    cl = [c.lower() for c in cols]
    for cand in candidates:
        if cand.lower() in cl:
            return cols[cl.index(cand.lower())]
    return None


def _detect_col_fuzzy(cols: Sequence[str], substrings: Sequence[str]) -> Optional[str]:
    """Fuzzy: any column containing one of substrings (ci)."""
    for name in cols:
        low = name.lower()
        if any(sub in low for sub in substrings):
            return name
    return None


def _guess_keyword_col(rows: List[Dict[str, str]]) -> Optional[str]:
    if not rows:
        return None
    cols = list(rows[0].keys())

    # 1) Strong candidates (common in our pipeline)
    strong = [
        "keyword",
        "keyword_sanitized",
        "related_keyword",
        "expanded_keyword",
        "expansion",
        "suggest",
        "candidate",
        "term",
        "query",
        "kw",
        "text",
        "title",
    ]
    col = _detect_col(cols, strong)
    if col:
        return col

    # 2) Fuzzy by column name
    col = _detect_col_fuzzy(cols, ["keyword", "query", "term", "title"])
    if col:
        return col

    # 3) Heuristic: pick the "most string-like, longer" column
    blacklist = {"seed", "category", "cat", "idx", "id", "index", "group", "count"}
    best_col = None
    best_score = -1.0
    for name in cols:
        if name.lower() in blacklist:
            continue
        values = [str(r.get(name, "") or "") for r in rows[:50]]
        non_empty = [v for v in values if v.strip()]
        if not non_empty:
            continue
        avg_len = sum(len(v) for v in non_empty) / max(1, len(non_empty))
        fill = len(non_empty) / max(1, len(values))
        score = avg_len * (0.5 + 0.5 * fill)
        if score > best_score:
            best_score = score
            best_col = name
    return best_col


def _guess_seed_col(rows: List[Dict[str, str]]) -> Optional[str]:
    if not rows:
        return None
    cols = list(rows[0].keys())
    candidates = ["seed", "root", "parent", "group", "source_seed", "seed_name"]
    col = _detect_col(cols, candidates)
    if col:
        return col
    col = _detect_col_fuzzy(cols, ["seed", "parent", "root", "group"])
    return col


def _build_session(ua: Optional[str]) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": ua or DEFAULT_UA, **EXTRA_HEADERS})
    s.max_redirects = 5
    return s


def _try_request(session: requests.Session, url: str, timeout: float, retries: int, sleep: float) -> Optional[str]:
    for i in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(sleep * (1.5 ** i))
    return None


def _parse_int(txt: str) -> Optional[int]:
    try:
        s = re.sub(r"[^\d]", "", txt)
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _naver_comp(session: requests.Session, kw: str, timeout: float, retries: int, sleep: float) -> Optional[int]:
    import urllib.parse as ul
    # 1) Naver Shopping
    url1 = NAVER_SHOPPING_URL.format(q=ul.quote(kw))
    html = _try_request(session, url1, timeout, retries, sleep)
    if html:
        for pat in [
            r"(?:검색결과|검색 결과)\s*([\d,]+)\s*(?:개|건)",
            r"\"total\"\s*:\s*([\d]+)",  # inline JSON
        ]:
            m = re.search(pat, html)
            if m:
                n = _parse_int(m.group(1))
                if n is not None:
                    return n
        try:
            soup = BeautifulSoup(html, "html.parser")
            # card-ish fallback
            cards = soup.select("[class*='productList'] [class*='product_item'], [class*='list_basis'] [class*='item']")
            if cards:
                return len(cards)
        except Exception:
            pass

    # 2) General search (약 N건)
    url2 = NAVER_GENERAL_URL.format(q=ul.quote(kw))
    html = _try_request(session, url2, timeout, retries, sleep)
    if html:
        for pat in [
            r"약\s*([\d,]+)\s*건",
            r"([\d,]+)\s*건",  # looser fallback
        ]:
            m = re.search(pat, html)
            if m:
                n = _parse_int(m.group(1))
                if n is not None:
                    return n
    return None


def _coupang_comp(session: requests.Session, kw: str, timeout: float, retries: int, sleep: float) -> Optional[int]:
    import urllib.parse as ul
    url = COUPANG_URL.format(q=ul.quote(kw))
    html = _try_request(session, url, timeout, retries, sleep)
    if not html:
        return None

    m = re.search(r"(?:검색결과|검색 결과)\s*([\d,]+)\s*개", html)
    if m:
        n = _parse_int(m.group(1))
        if n is not None:
            return n
    try:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("[id*='productList'] li.search-product, li.search-product")
        if cards:
            return len(cards)
    except Exception:
        pass
    return None


def _read_existing_header_and_keys(outp: Path) -> Tuple[Optional[List[str]], Set[Tuple[str, str]]]:
    keys: Set[Tuple[str, str]] = set()
    header: Optional[List[str]] = None
    if outp.exists():
        with open(outp, "r", encoding="utf-8-sig", newline="") as f:
            r = csv.DictReader(f)
            header = r.fieldnames or None
            seed_col = _detect_col(header or [], ["seed"])
            kw_col = _detect_col(header or [], ["keyword", "term", "query"])
            for row in r:
                seed = (row.get(seed_col) if seed_col else "") or ""
                kw = (row.get(kw_col) if kw_col else row.get("keyword", "")) or ""
                keys.add((seed.strip(), kw.strip()))
    return header, keys


def _iter_input_rows(
    expanded: Optional[Path], sanitized: Optional[Path]
) -> Tuple[List[Tuple[str, str]], Optional[str], Optional[str]]:
    src: Optional[Path] = None
    if expanded and expanded.exists():
        src = expanded
    elif sanitized and sanitized.exists():
        src = sanitized
    if not src:
        return [], None, None

    data = _read_csv_rows(src)
    if not data:
        return [], None, None

    seed_col = _guess_seed_col(data)
    kw_col = _guess_keyword_col(data)
    if not kw_col:
        raise SystemExit("ERROR: Could not locate a keyword column in input CSV.")

    pairs: List[Tuple[str, str]] = []
    for row in data:
        seed = (row.get(seed_col) if seed_col else "") or ""
        kw = (row.get(kw_col) or "").strip()
        if kw:
            pairs.append((seed.strip(), kw))
    return pairs, seed_col, kw_col


def _choose_output_header(existing: Optional[List[str]]) -> List[str]:
    if existing:
        return list(existing)
    # default header when creating a new file
    return ["seed", "keyword", "comp_coupang", "comp_naver", "comp_combined", "scraped_at"]


def _row_dict_for_header(
    header: List[str],
    seed: str,
    kw: str,
    comp_c: Optional[int],
    comp_n: Optional[int],
) -> Dict[str, str]:
    row: Dict[str, str] = {h: "" for h in header}
    # seed/keyword
    if "seed" in row:
        row["seed"] = seed
    if "seed_name" in row and not row.get("seed_name"):
        row["seed_name"] = seed
    if "parent" in row and not row.get("parent"):
        row["parent"] = seed

    if "keyword" in row:
        row["keyword"] = kw
    elif "term" in row:
        row["term"] = kw
    elif "query" in row:
        row["query"] = kw

    # competition counts
    if "comp_coupang" in row:
        row["comp_coupang"] = "" if comp_c is None else str(comp_c)
    if "comp_naver" in row:
        row["comp_naver"] = "" if comp_n is None else str(comp_n)

    # combined (compute if both present)
    combined: Optional[float] = None
    if comp_c is not None or comp_n is not None:
        import math
        c = math.log1p(comp_c or 0)
        n = math.log1p(comp_n or 0)
        combined = c + n
    if "comp_combined" in row and combined is not None:
        row["comp_combined"] = f"{combined:.4f}"

    # timestamp
    if "scraped_at" in row:
        row["scraped_at"] = _now_iso_utc()

    return row


def fetch_and_append(
    expanded_in: Optional[Path],
    sanitized_in: Optional[Path],
    outp: Path,
    site_mode: str,
    sleep: float,
    timeout: float,
    retries: int,
    ua: Optional[str],
) -> None:
    session = _build_session(ua)
    existing_header, exist_keys = _read_existing_header_and_keys(outp)
    to_process, seed_col, kw_col = _iter_input_rows(expanded_in, sanitized_in)

    header = _choose_output_header(existing_header)
    write_header = not outp.exists()
    outp.parent.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    total = len(to_process)
    done = 0
    skipped = 0
    started_at = time.time()

    with open(outp, "a", encoding="utf-8-sig", newline="") as f, \
         open(Path("logs/errors.csv"), "a", encoding="utf-8-sig", newline="") as ef:
        dw = csv.DictWriter(f, fieldnames=header)
        ew = csv.DictWriter(ef, fieldnames=["ts", "site", "seed", "keyword", "url", "error"])
        if write_header:
            dw.writeheader()
            ew.writeheader()

        for idx, (seed, kw) in enumerate(to_process, start=1):
            key = (seed, kw)
            if key in exist_keys:
                skipped += 1
                continue

            comp_c: Optional[int] = None
            comp_n: Optional[int] = None

            try:
                if site_mode in ("both", "coupang"):
                    comp_c = _coupang_comp(session, kw, timeout, retries, sleep)
                    time.sleep(sleep + random.random() * 0.2)
                if site_mode in ("both", "naver"):
                    comp_n = _naver_comp(session, kw, timeout, retries, sleep)
                    time.sleep(sleep + random.random() * 0.2)

                dw.writerow(_row_dict_for_header(header, seed, kw, comp_c, comp_n))
                f.flush()
                done += 1

                if idx % 10 == 0:
                    elapsed = time.time() - started_at
                    print(f"[{idx}/{total}] done={done} skipped={skipped} elapsed={elapsed:.1f}s")

            except KeyboardInterrupt:
                print("\nKeyboardInterrupt received. Partial results kept. Re-run to resume.")
                break
            except Exception as e:
                ts = _now_iso_utc()
                site = "both" if site_mode == "both" else site_mode
                ew.writerow({
                    "ts": ts,
                    "site": site,
                    "seed": seed,
                    "keyword": kw,
                    "url": "-",
                    "error": str(e),
                })
                ef.flush()
                # continue to next

    print(f"All done. Output: {str(outp)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expanded-in", type=Path, help="Input CSV: expanded keywords")
    ap.add_argument("--sanitized-in", type=Path, help="Input CSV: sanitized keywords (fallback)")
    ap.add_argument("--out", type=Path, required=True, help="Output CSV (append/checkpoint)")
    ap.add_argument("--site-mode", choices=["both", "naver", "coupang"], default="both")
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--ua", type=str, default=None)

    args = ap.parse_args()
    if not args.expanded_in and not args.sanitized_in:
        print("ERROR: Provide at least one of --expanded-in or --sanitized-in", file=sys.stderr)
        return 2

    fetch_and_append(
        expanded_in=args.expanded_in,
        sanitized_in=args.sanitized_in,
        outp=args.out,
        site_mode=args.site_mode,
        sleep=args.sleep,
        timeout=args.timeout,
        retries=args.retries,
        ua=args.ua,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
