#!/usr/bin/env bash
# scripts/d5_setup.sh
set -Eeuo pipefail
trap 'echo "[ERR] ${BASH_SOURCE[0]}:${LINENO}: ${BASH_COMMAND} (exit=$?)" >&2' ERR

# 0) 작업 루트 확인
WORKDIR="/workspaces/KWORD"
[[ -d "$WORKDIR" ]] || { echo "[FATAL] WORKDIR missing: $WORKDIR"; exit 2; }
cd "$WORKDIR"
echo "[OK] pwd=$(pwd)"

# 1) 필수 폴더
mkdir -p docs scripts .github/workflows

# 2) Pro PRD/WBS 생성(없을 때만)
if [[ ! -f docs/prd_keyword_scoring_pro_edition.md ]]; then
  cat > docs/prd_keyword_scoring_pro_edition.md <<'MD'
# PRD — KWORD: Keyword Scoring (Pro Edition)

## 1. Overview
- 목적: Free Edition 파이프라인을 기반으로 Pro 기능(멀티 소스 경쟁도, 사용자 사전, 배치/리트라이 강화, 리포트+) 제공

## 2. Scope (v0.1.0)
- [In] Free 파이프라인 호환, Pro 전용 config 확장
- [Out] 유료 API/크롤링은 미포함(추후)

## 14. Snapshot
- 초기 생성: (to be updated by snapshot tool)
MD
  echo "[OK] wrote docs/prd_keyword_scoring_pro_edition.md"
fi

if [[ ! -f docs/wbs_keyword_scoring_pro_edition.md ]]; then
  cat > docs/wbs_keyword_scoring_pro_edition.md <<'MD'
# WBS — KWORD: Keyword Scoring (Pro Edition)

## Epic P — Project Bootstrap
- [ ] P1. Pro PRD/WBS 생성
- [ ] P2. Pro 실행 스크립트 추가 (`scripts/pro_run.sh`)
- [ ] P3. Free/Pro 분기 태깅/브랜치 전략 확정

## Approval Gates
- **Gate P0 (Bootstrap)**
  - [ ] PRD(Pro) 생성
  - [ ] WBS(Pro) 생성
  - [ ] 실행 스크립트 동작
MD
  echo "[OK] wrote docs/wbs_keyword_scoring_pro_edition.md"
fi

# 3) 에디션별 실행 스크립트
cat > scripts/free_run.sh <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PYTHONUNBUFFERED=1 python -u src/keyword_scoring_free_only.py \
  --in data/seeds.xlsx \
  --expand 2 --sleep 0.6 --site-mode naver \
  --sanitized-out output/sanitized_keywords.csv \
  --expanded-out output/expanded_keywords.csv \
  --competition-out output/competition_counts.csv
python -u tools/compute_scores.py \
  --excel-in data/seeds.xlsx \
  --sanitized-in output/sanitized_keywords.csv \
  --expanded-in output/expanded_keywords.csv \
  --competition-in output/competition_counts.csv \
  --out-csv output/keyword_scores_free.csv \
  --out-xlsx output/keyword_scores_free.xlsx \
  --topn 50 --html-out output/report.html
SH
chmod +x scripts/free_run.sh

cat > scripts/pro_run.sh <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
# Pro: 초기에는 Free와 동일 파이프라인, 후속 커밋에서 Pro 전용 옵션/리포트 확장
PYTHONUNBUFFERED=1 python -u src/keyword_scoring_free_only.py \
  --in data/seeds.xlsx \
  --expand 2 --sleep 0.6 --site-mode naver \
  --sanitized-out output/sanitized_keywords.csv \
  --expanded-out output/expanded_keywords.csv \
  --competition-out output/competition_counts.csv
python -u tools/compute_scores.py \
  --excel-in data/seeds.xlsx \
  --sanitized-in output/sanitized_keywords.csv \
  --expanded-in output/expanded_keywords.csv \
  --competition-in output/competition_counts.csv \
  --out-csv output/keyword_scores_free.csv \
  --out-xlsx output/keyword_scores_free.xlsx \
  --topn 50 --html-out output/report.html
SH
chmod +x scripts/pro_run.sh

# 4) CI 워크플로우 없으면 생성
if [[ ! -f .github/workflows/ci-smoke.yml ]]; then
  cat > .github/workflows/ci-smoke.yml <<'YML'
name: CI Smoke (Free/Pro)

on:
  push:
    paths:
      - "tools/**"
      - "src/**"
      - "docs/**"
      - "data/seeds_regression.xlsx"
      - "output/golden/regression/**"
      - ".github/workflows/ci-smoke.yml"
  workflow_dispatch:

env:
  TOLERANCE: "1e-9"

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install pandas numpy openpyxl xlsxwriter
      - name: Run CI smoke with golden snapshot
        run: |
          python -u tools/ci_smoke.py \
            --golden-dir output/golden/regression \
            --excel-in data/seeds_regression.xlsx \
            --tolerance "${TOLERANCE}"
YML
  echo "[OK] wrote .github/workflows/ci-smoke.yml"
fi

# 5) .gitignore에 golden 예외 추가(중복 방지)
touch .gitignore
if ! grep -q '^output/\*\*$' .gitignore; then
  echo 'output/**' >> .gitignore
fi
if ! grep -q '^!output/golden/\*\*$' .gitignore; then
  echo '!output/golden/**' >> .gitignore
fi
if ! grep -q '^!output/golden/regression/\*\*$' .gitignore; then
  echo '!output/golden/regression/**' >> .gitignore
fi
echo "[OK] updated .gitignore exceptions for golden snapshot"

# 6) git 반영 (변경 없으면 에러 무시)
git add docs/*.md scripts/*.sh .github/workflows/ci-smoke.yml .gitignore 2>/dev/null || true
git commit -m "chore: init Pro edition skeleton + scripts + CI workflow + .gitignore golden exceptions" || true

# 7) pro 브랜치/태그 (이미 있으면 스킵)
if ! git show-ref --verify --quiet refs/heads/pro; then
  git branch pro
  echo "[OK] created branch: pro"
fi
if ! git show-ref --tags --quiet "free-v0.3.0-snapshot"; then
  git tag -a free-v0.3.0-snapshot -m "Free Edition v0.3.0 snapshot"
  echo "[OK] tagged: free-v0.3.0-snapshot"
fi

echo "[DONE] D5 skeleton ready."
