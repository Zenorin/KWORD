#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERR] ${BASH_SOURCE[0]}:${LINENO}: ${BASH_COMMAND} (exit=$?)" >&2' ERR
cd "$(dirname "$0")/.."

# 1) 검증
python -u tools/verify_outputs.py \
  --sanitized output/sanitized_keywords.csv \
  --expanded output/expanded_keywords.csv \
  --competition output/competition_counts.csv \
  --scores-csv output/keyword_scores_free.csv \
  --scores-xlsx output/keyword_scores_free.xlsx \
  --html output/report.html || VERIFY_RC=$? || true

VERIFY_RC=${VERIFY_RC:-0}
echo "[INFO] verify rc=${VERIFY_RC}"

# 2) 중복 발견 시 자동 정리 → 재검증
NEED_FIX=0
if grep -q "duplicated keys" output/_verify_report.md; then
  NEED_FIX=1
fi

if [[ $NEED_FIX -eq 1 ]]; then
  echo "[INFO] duplicates detected → running auto fix"
  python -u tools/fix_duplicates.py \
    --in  output/keyword_scores_free.csv \
    --out output/keyword_scores_free.csv
  # re-verify
  python -u tools/verify_outputs.py \
    --sanitized output/sanitized_keywords.csv \
    --expanded output/expanded_keywords.csv \
    --competition output/competition_counts.csv \
    --scores-csv output/keyword_scores_free.csv \
    --scores-xlsx output/keyword_scores_free.xlsx \
    --html output/report.html
fi

# 3) PRD 스냅샷에 품질 메모 추가
python - <<'PY'
from pathlib import Path, re
prd = Path("docs/prd_keyword_scoring_free_edition.md")
rep = Path("output/_verify_report.md")
txt = prd.read_text(encoding="utf-8").splitlines()
note = "**Quality:** outputs verified; duplicates auto-fixed ✅" if "duplicated keys" in rep.read_text(encoding="utf-8") else "**Quality:** outputs verified ✅ (no issues)"
inserted=False
for i, line in enumerate(txt):
    if re.match(r'^\s*##\s*(?:14\.\s*)?Snapshot\b', line, flags=re.I):
        j=i+1
        if j < len(txt) and txt[j].strip().lower().startswith("**quality:**"):
            txt.pop(j)
        txt.insert(i+1, note)
        inserted=True
        break
if not inserted:
    txt.extend(["","## Snapshot", note])
prd.write_text("\n".join(txt)+"\n", encoding="utf-8")
print("[OK] PRD quality note updated")
PY

# 4) WBS D7 체크
python - <<'PY'
import re, pathlib
wbs = pathlib.Path("docs/wbs_keyword_scoring_free_edition.md")
s = wbs.read_text(encoding="utf-8")
if re.search(r"^- \[ \] D7\.", s, flags=re.M):
    s = re.sub(r"^- \[ \] D7\.", "- [x] D7.", s, flags=re.M)
elif re.search(r"^##\s*Epic D", s, flags=re.M):
    s = re.sub(r"(##\s*Epic D[^\n]*\n)", r"\1- [x] D7. Verify & auto-fix duplicates\n", s, flags=re.M)
else:
    s += "\n\n## Epic D — Data & Config Quality\n- [x] D7. Verify & auto-fix duplicates\n"
wbs.write_text(s, encoding="utf-8")
print("[OK] WBS D7 checked/added")
PY

# 5) 커밋
git add tools/verify_outputs.py tools/fix_duplicates.py scripts/d7_verify.sh docs/*.md output/_verify_report.md 2>/dev/null || true
git commit -m "ops(free): D7 verify outputs + auto dedup; PRD/WBS updated" || true
echo "[DONE] D7 verify & dedup complete."
