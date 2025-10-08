# Keyword Scoring (Free Edition) — GitHub Codespaces

> Batch keyword expansion + scoring for **Coupang** and **Naver Shopping**, using **only free data** (no Google APIs).  
> Input: Excel seeds → Expand (Naver Suggest) → Sanitize (partial removal, Korean prohibited words) → Scrape competition (Coupang/Naver) → Score → CSV/XLSX/HTML.

---

## ✨ Highlights

- **Free-only**: No paid APIs, no Google services.
- **Excel-configurable**: Adjust **intent tokens** and **scoring weights** in the `config` sheet.
- **Prohibited words**: **Partial-match removal** (Korean set); do not discard keywords.
- **No seed de-duplication**: Duplicates remain as-is for per-seed tracking.
- **Batch scale**: 20–30 seeds/day × ~20 related keywords each (≈ 400–600 rows/day).
- **Polite scraping**: Throttling, retries, fallbacks, and detailed logs.

---

## 📂 Base Path

All commands assume the repository lives at:

/workspaces/KWORD

markdown
Copy code

---

## 🧠 Scoring Model (configurable)

Let:
- `comp_coupang` = search result count on Coupang
- `comp_naver`   = search result count on Naver Shopping
- `comp_combined = log1p(comp_coupang) + log1p(comp_naver)`
- `competition_norm = MinMax(comp_combined)` per run
- `intent_proxy` = weighted sum of enabled intent tokens found in the **sanitized** keyword  
  (defined in Excel `config` sheet) → MinMax → `intent_norm`

Final score (weights from Excel; re-normalized if they don’t sum to 1):

score = 100 * ( W_intent * intent_norm + W_competition * (1 - competition_norm) )

markdown
Copy code

**Default weights**: `W_intent = 0.55`, `W_competition = 0.45`.

---

## 🧹 Prohibited Words & Symbols (Korean-only)

**Policy**
- If a prohibited word/symbol is present, **remove only the matched fragment** (partial match).
- Normalize: Unicode NFKC → collapse spaces → trim → casefold.
- If the result becomes empty or length < 2, drop the row and log it.

**Default Korean terms**
- Words (subset): `즉시 할인`, `선착순`, `무료`, `무료 배송`, `1위`, `인기`, `신상품`, `신제품`, `베스트`, `추천`, `특가`, `이벤트`, `적립`, `가격`, `쿠폰`, `배송비`, `할인율`, `세일`, `한정`, `좋은`, `최고`, `초강력`, `완벽`, `최상`, `가성비`, `품질`, `긴급`, `특별 할인`, `정품`, `오리지널`, `병행수입`, `가짜`, `진품`
- Symbols: `! ? ★ ☆ ◆ ◇ ■ □ ● ○ ✔ ✅ ※ 【 】 「 」 『 』 ◀ ▶ ▲ ▼ ☞ ☜`

> File: `config/prohibited_words_ko.json` (editable).  
> You can also append more in the Excel `config` sheet (optional table).

---

## 📦 Repository Layout

/workspaces/KWORD
├─ src/
│ └─ keyword_scoring_free_only.py # main CLI
├─ data/
│ └─ seeds.xlsx # your input (seeds + config sheets)
├─ output/ # CSV/XLSX/HTML reports
├─ logs/ # run.log, errors.csv, prohibited.csv
├─ config/
│ └─ prohibited_words_ko.json # default Korean prohibited list
├─ docs/ # PRD / Runbook (optional)
├─ scripts/
│ └─ make_dirs.sh # directory bootstrap
├─ requirements.txt
└─ README.md

yaml
Copy code

---

## 🚀 Quick Start (Codespaces)

1) **Create & activate virtualenv**
```bash
cd /workspaces/KWORD
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
Install dependencies

bash
Copy code
pip install -r requirements.txt
Prepare data/seeds.xlsx

Sheet seeds (duplicates allowed):

A: keyword (required)

B: category (optional; pass-through)

Sheet config:

Weights (key, value):

W_intent (e.g., 0.55)

W_competition (e.g., 0.45)

Intent tokens (token, weight, enabled):

e.g., 빅사이즈, 1.0, TRUE, 임산부, 0.9, TRUE, …, 기모, 0.3, TRUE

(Optional) Prohibited words (word, enabled) to append to defaults.

Minimal example

sql
Copy code
| seeds sheet |
keyword       | category
--------------|---------
기모 원피스   | apparel
겨울 니트     | apparel

| config sheet |
key           | value
--------------|------
W_intent      | 0.55
W_competition | 0.45

token   | weight | enabled
--------|--------|--------
빅사이즈| 1.0    | TRUE
임산부  | 0.9    | TRUE
...
Run

bash
Copy code
python src/keyword_scoring_free_only.py \
  --in data/seeds.xlsx \
  --out output/keyword_scores_free.csv \
  --expand 20 \
  --sleep 0.7 \
  --site-mode both \
  --topN-report 50
Open results

output/keyword_scores_free.csv (UTF-8-SIG)

output/keyword_scores_free.xlsx (formatted)

output/report.html (optional Top-N summary)

Logs: logs/run.log, logs/errors.csv, logs/prohibited.csv

🖥️ CLI
bash
Copy code
python src/keyword_scoring_free_only.py --help
Flags

--in PATH : Excel path (with seeds & config sheets)

--out PATH : Output CSV path

--expand INT : Related keywords per seed (default: 20)

--sleep FLOAT : Delay between requests (default: 0.7)

--retries INT : Retries per request (default: 2)

--timeout FLOAT : Request timeout seconds (default: 6.0)

--site-mode [both|coupang|naver] : Competition sources (default: both)

--ua STRING : Custom User-Agent

--topN-report INT : Generate HTML/XLSX for top N (0=skip)

--no-html : Skip HTML report

Precedence

CLI flags → 2) Excel config → 3) Built-in defaults.

🔍 How It Works
Expand: Naver Suggest (unofficial), up to --expand per seed; include seed itself.

Sanitize: Remove prohibited fragments (Korean set, partial match), then normalize.

Scrape:

Coupang: parse 검색 결과 nnn개 (regex), fallback to product card count.

Naver Shopping: parse 검색결과 nnn개 (regex).

Score: Normalize intent & competition; combine with Excel-provided weights.

🧪 Smoke Test
bash
Copy code
# Create a tiny seeds.xlsx + config
python - << 'PY'
import pandas as pd, os
base = '/workspaces/KWORD'
os.makedirs(f'{base}/data', exist_ok=True)
df = pd.DataFrame({'keyword':['[특가] 기모 원피스!','무료 배송 겨울 니트']})
df.to_excel(f'{base}/data/seeds.xlsx', sheet_name='seeds', index=False)
with pd.ExcelWriter(f'{base}/data/seeds.xlsx', mode='a', engine='openpyxl') as w:
    pd.DataFrame({'key':['W_intent','W_competition'],'value':[0.55,0.45]}).to_excel(w, sheet_name='config', index=False)
    pd.DataFrame({'token':['빅사이즈','임산부','하객','홈웨어','니트','롱','후드','맨투맨','폴라','기모'],
                  'weight':[1.0,0.9,0.7,0.6,0.5,0.5,0.4,0.4,0.4,0.3],
                  'enabled':[True]*10}).to_excel(w, sheet_name='config', index=False, startrow=4)
print('Wrote data/seeds.xlsx')
PY

# Run
python src/keyword_scoring_free_only.py --in data/seeds.xlsx --out output/test.csv --expand 5 --sleep 1.0
⚙️ Requirements
Python 3.9+

requirements.txt

ini
Copy code
pandas==2.2.2
numpy==1.26.4
requests==2.32.3
beautifulsoup4==4.12.3
openpyxl==3.1.5
XlsxWriter==3.2.0
🧰 Tips
Adjust weights/tokens in Excel config sheet; the tool auto re-normalizes weights.

Extend prohibited list via config/prohibited_words_ko.json or a table in config sheet.

Keep --sleep ≥ 0.5 to reduce throttling; use --retries 2 for resilience.

Duplicate seeds are intentional; the output preserves per-seed rows.

📄 Legal
Respect each site’s Terms of Service and robots directives.

Anonymous, read-only scraping; no personal data.

DOM can change anytime; update regex/selectors as needed.

📬 Support
Open an issue and include:

your data/seeds.xlsx (redacted),

the exact CLI you ran,

logs/run.log, logs/errors.csv, logs/prohibited.csv,

a few problem rows.