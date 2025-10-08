import os

REQUIRED = [
    ("NAVER_CLIENT_ID", False),
    ("NAVER_CLIENT_SECRET", False),
    ("SMARTSTORE_ACCESS_TOKEN", True),          # may be disabled by config
    ("COUPANG_ACCESS_KEY", True),
    ("COUPANG_SECRET_KEY", True),
    ("COUPANG_VENDOR_ID", True),
]

def get_env(name: str, required: bool = False) -> str:
    val = os.getenv(name, "")
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

def assert_required_for(enabled: dict):
    # Only enforce variables for enabled connectors
    for key, req in REQUIRED:
        if "NAVER" in key and (enabled.get("naver_search") or enabled.get("naver_datalab")):
            if not os.getenv(key):
                raise RuntimeError(f"Missing NAVER env: {key}")
        if "SMARTSTORE" in key and enabled.get("smartstore"):
            if not os.getenv(key):
                raise RuntimeError(f"Missing SmartStore env: {key}")
        if "COUPANG_" in key and (enabled.get("coupang_open") or enabled.get("coupang_partners")):
            if not os.getenv(key):
                raise RuntimeError(f"Missing Coupang env: {key}")
