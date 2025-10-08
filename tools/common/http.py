import time, random, requests

class HttpClient:
    def __init__(self, throttle_ms=300, retry_attempts=3):
        self.throttle_ms = throttle_ms
        self.retry_attempts = retry_attempts
        self._last = 0.0

    def _throttle(self):
        now = time.time()
        wait_s = max(0.0, self._last + self.throttle_ms/1000.0 - now)
        if wait_s > 0:
            time.sleep(wait_s)
        self._last = time.time()

    def get(self, url, **kwargs):
        return self._with_retry(lambda: requests.get(url, timeout=15, **kwargs))

    def post(self, url, **kwargs):
        return self._with_retry(lambda: requests.post(url, timeout=15, **kwargs))

    def _with_retry(self, fn):
        err = None
        for i in range(self.retry_attempts):
            try:
                self._throttle()
                r = fn()
                if r.status_code >= 500:
                    raise RuntimeError(f"5xx from server: {r.status_code}")
                return r
            except Exception as e:
                err = e
                time.sleep(min(2**i, 8) + random.random()*0.3)
        raise err
