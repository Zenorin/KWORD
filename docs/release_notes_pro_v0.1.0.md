# Release Notes — KWORD Pro v0.1.0 (snapshot)

## Highlights
- Pro 에디션 스켈레톤 도입 (PRD/WBS/런 스크립트)
- Free 파이프라인과 호환 유지, 후속 커밋에서 Pro 전용 옵션 확장 예정

## What’s Included
- `docs/prd_keyword_scoring_pro_edition.md` — Pro PRD
- `docs/wbs_keyword_scoring_pro_edition.md` — Pro WBS
- `scripts/pro_run.sh` — Pro 실행 스크립트 (현재 Free와 동일 플로우)
- `tools/ci_smoke.py` — Golden 기반 CI 스모크 유지
- `output/golden/regression/*` — 결정적 스냅샷 (Free 기준)

## Compatibility
- Python 3.12
- pandas 2.2.x / numpy 1.26.x / openpyxl 3.1.x / XlsxWriter 3.2.x

## Next (Pro Roadmap)
- 멀티 소스 경쟁도(Bing/Naver/Coupang selectable)
- 사용자 사전(동의어/치환/불용어) 병합 규칙
- 레포트+ (카테고리별 TopN, 비교뷰, 섹션 점수)

## Changelog (since snapshot)
- init: Pro 문서/스크립트/CI 공용 워크플로우
- docs: 프로 스냅샷 섹션 자동화 준비
