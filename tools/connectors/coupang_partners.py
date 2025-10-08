# Coupang Partners API (optional). Use only if eligible.
# Example: keyword -> product search count/topN (adjust to actual available endpoints)
import hmac, hashlib, base64, time
from ..common.http import HttpClient
from ..common.env import get_env

def _auth(method, path):
    access = get_env("COUPANG_PARTNERS_ACCESS_KEY", True)
    secret = get_env("COUPANG_PARTNERS_SECRET_KEY", True)
    datetime_gmt = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    message = datetime_gmt + method + path
    signature = base64.b64encode(hmac.new(bytes(secret, 'utf-8'), message.encode('utf-8'), hashlib.sha256).digest())
    return datetime_gmt, access, signature.decode()

def keyword_search(keyword: str, page: int = 1):
    base = "https://api-gateway.coupang.com"
    path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
    method = "GET"
    datetime_gmt, access, sig = _auth(method, path)
    headers = {"Authorization": f"CEA algorithm=HmacSHA256, access-key={access}, signed-date={datetime_gmt}, signature={sig}"}
    params = {"keyword": keyword, "page": page}
    r = HttpClient().get(base+path, headers=headers, params=params)
    return r.json()
