# Coupang Open API client (seller). Category prediction as feature.
import hmac, hashlib, base64, time
from urllib.parse import urlparse
from ..common.http import HttpClient
from ..common.env import get_env

def _authorization(method, path, secret, access_key):
    datetime_gmt = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    message = datetime_gmt + method + path
    signature = base64.b64encode(hmac.new(bytes(secret, 'utf-8'), message.encode('utf-8'), hashlib.sha256).digest())
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={datetime_gmt}, signature={signature.decode()}"

def category_predict(title: str):
    base = "https://api-gateway.coupang.com"
    path = "/v2/providers/affiliate_open_api/apis/api/v1/category/predict"  # adjust when using official cat prediction path
    method = "POST"
    access = get_env("COUPANG_ACCESS_KEY", True)
    secret = get_env("COUPANG_SECRET_KEY", True)
    headers = {
        "Authorization": _authorization(method, path, secret, access),
        "Content-Type": "application/json;charset=UTF-8"
    }
    body = {"title": title}
    client = HttpClient()
    r = client.post(base+path, headers=headers, json=body)
    return r.json()
