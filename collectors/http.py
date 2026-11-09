"""Shared, polite HTTP client: browser-like headers, retries with back-off, small pauses."""
from __future__ import annotations

import random
import time

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")


class RateLimited(Exception):
    pass


def client(**headers) -> httpx.Client:
    h = {"User-Agent": UA, "Accept-Language": "en-PH,en;q=0.9"}
    h.update(headers)
    return httpx.Client(headers=h, timeout=30, follow_redirects=True)


def get(c: httpx.Client, url: str, *, params=None, tries=3, pause=(0.4, 1.0)) -> httpx.Response:
    return _req(c, "GET", url, params=params, tries=tries, pause=pause)


def post(c: httpx.Client, url: str, *, json=None, tries=3, pause=(0.4, 1.0)) -> httpx.Response:
    return _req(c, "POST", url, json=json, tries=tries, pause=pause)


def _req(c, method, url, tries, pause, **kw):
    last = None
    for attempt in range(tries):
        time.sleep(random.uniform(*pause))
        try:
            r = c.request(method, url, **kw)
        except httpx.HTTPError as e:
            last = e
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 429:
            last = RateLimited(f"429 from {url.split('?')[0]}")
            time.sleep(8 * (attempt + 1))
            continue
        if r.status_code >= 500:
            last = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    raise last
