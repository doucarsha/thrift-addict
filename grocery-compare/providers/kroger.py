"""Kroger provider — official Kroger API (developer.kroger.com).

Setup: Shaun signs up free at developer.kroger.com, creates an app,
and provides the Client ID + Client Secret via Secure Vault. Set them
as env vars KROGER_CLIENT_ID / KROGER_CLIENT_SECRET on Render.

This is the ONLY reliable real-time price source: it's Kroger's own
API, no browser scraping, no bot blocks.
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request

from .base import BaseProvider
from .stores import STORES

STORE_NAME = "Kroger"
# Shaun's store: Kroger Hilliard-Rome. Override with KROGER_LOCATION_ID env var.
PREFERRED_LOCATION_ID = os.environ.get("KROGER_LOCATION_ID") or STORES["Kroger"]["location_id"]

TOKEN_URL = "https://api.kroger.com/v1/connect/oauth2/token"
PRODUCTS_URL = "https://api.kroger.com/v1/products"
LOCATIONS_URL = "https://api.kroger.com/v1/locations"

_token = None
_token_exp = 0


def _creds():
    cid = os.environ.get("KROGER_CLIENT_ID")
    sec = os.environ.get("KROGER_CLIENT_SECRET")
    return cid, sec


def _get_token():
    global _token, _token_exp
    if _token and time.time() < _token_exp - 60:
        return _token
    cid, sec = _creds()
    if not cid or not sec:
        return None
    basic = base64.b64encode(("%s:%s" % (cid, sec)).encode()).decode()
    data = urllib.parse.urlencode(
        {"grant_type": "client_credentials",
         "scope": "product.compact"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", "Basic " + basic)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
        _token = d["access_token"]
        _token_exp = time.time() + int(d.get("expires_in", 1800))
        return _token
    except Exception:
        return None


def _api_get(url, params):
    token = _get_token()
    if not token:
        return None
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(url + "?" + qs)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception:
        return None


def _find_location_id(zip_code):
    """Preferred Hilliard-Rome store; falls back to nearest-ZIP lookup."""
    if PREFERRED_LOCATION_ID:
        return PREFERRED_LOCATION_ID
    if not hasattr(_find_location_id, "cache"):
        _find_location_id.cache = {}
    if zip_code in _find_location_id.cache:
        return _find_location_id.cache[zip_code]
    d = _api_get(LOCATIONS_URL,
                 {"filter.zipCode.near": zip_code, "filter.limit": 1})
    try:
        lid = d["data"][0]["locationId"]
        _find_location_id.cache[zip_code] = lid
        return lid
    except Exception:
        return None


def _api_search(item, zip_code):
    loc = _find_location_id(zip_code)
    if not loc:
        return []
    d = _api_get(PRODUCTS_URL, {"filter.term": item,
                                "filter.locationId": loc,
                                "filter.limit": 10})
    out = []
    for p in (d or {}).get("data", []):
        try:
            desc = p.get("description", "")
            items = p.get("items", [])
            if not items:
                continue
            it = items[0]
            price = it.get("price", {}) or {}
            regular = price.get("regular")
            promo = price.get("promo")
            if regular is None:
                continue
            # price objects look like {"regular": 2.89, "promo": 2.49, ...}
            # or {"regular": {"amount": 2.89}, ...} — handle both
            def amt(v):
                if isinstance(v, dict):
                    return v.get("amount")
                return v
            reg_amt = amt(regular)
            pro_amt = amt(promo)
            if reg_amt is None:
                continue
            final = pro_amt if pro_amt is not None else reg_amt
            upc = p.get("upc", "")
            out.append({
                "store": STORE_NAME,
                "name": desc[:120],
                "price": float(final),
                "unit_price": None,
                "sale": pro_amt is not None and pro_amt < reg_amt,
                "url": ("https://www.kroger.com/p/%s/%s" % (
                    urllib.parse.quote(desc.lower().replace(" ", "-")[:60]),
                    upc) if upc else None),
            })
        except Exception:
            continue
    return out


PROVIDER_STATUS = {"status": "live" if _creds()[0] else "stub",
                   "note": ("Live via Kroger official API." if _creds()[0]
                            else "Needs free Kroger API key — see setup."),
                   "address": STORES["Kroger"]["address"]}


class KrogerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")


async def parse_results(page, url):
    # Not used — Kroger goes through the official API, not the browser.
    return []


async def parse_sales(page):
    return []


def search_url(item, zip_code):
    return "https://www.kroger.com/search?query=%s" % urllib.parse.quote(item)


def sales_url(zip_code):
    return "https://www.kroger.com/weeklyad"


def api_search(item, zip_code):
    """Direct API search (called by engine when credentials exist)."""
    return _api_search(item, zip_code)
