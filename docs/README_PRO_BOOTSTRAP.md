# KWORD Pro Bootstrap (APIs-ready)

## 0) Create `.env`
Copy `.env.template` to `.env` and fill keys. Missing keys will stop the run with a clear error.

## 1) Configure
- `configs/pro.yaml` : mode, throttles, enable_connectors flags
- `configs/connectors.yaml` : base URLs and per-API settings

## 2) Run Pro pipeline (skeleton)
```bash
bash scripts/pro_run.sh
```
Wire your actual Python runners in `scripts/p1_collect.sh` etc.

## Notes
- All new files are **additive**. Free edition files remain valid.
- Deterministic review: keep `mode: snapshot` until approval.
