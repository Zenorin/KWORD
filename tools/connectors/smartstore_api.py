# Placeholder SmartStore Commerce API client (seller)
# Read-only catalog pull to align categories/titles
import json
from ..common.http import HttpClient
from ..common.env import get_env

def get_my_products(page=1, size=20):
    token = get_env("SMARTSTORE_ACCESS_TOKEN", True)
    base = "https://api.commerce.naver.com"
    # Endpoint paths depend on granted scopes; replace with actual path you enabled.
    url = f"{base}/external/v2/products?page={page}&size={size}"
    h = {"Authorization": f"Bearer {token}"}
    r = HttpClient().get(url, headers=h)
    return r.json()
