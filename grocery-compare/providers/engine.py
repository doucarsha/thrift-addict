#!/usr/bin/env python3
"""Shared Playwright engine for grocery providers.

One persistent headless Chromium, concurrent store scrapes (semaphore-limited
for memory safety), SQLite result cache (24h TTL). Providers implement
site-specific search_url() / parse() / sales_url() / parse_sales().

Proxy is read from HTTPS_PROXY when set (dev VM); absent on Render.
"""
import asyncio
import json
import os
import sqlite3
import threading
import time
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
STORE_TIMEOUT_S = 40
MAX_CONCURRENT = 1  # sequential: 512MB free tier can't hold 2 heavy pages
CACHE_TTL_S = 24 * 3600

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DB = os.path.join(os.path.dirname(BASE), "price_cache.db")

_pw = None
_browser = None
_sem = None


def _proxy_cfg():
    # Explicit opt-in only. Never auto-read HTTPS_PROXY: PaaS platforms
    # sometimes set proxy vars that break Playwright's CONNECT tunneling.
    raw = os.environ.get("GROCERY_PROXY")
    return {"server": raw} if raw else None


async def _ensure():
    global _pw, _browser, _sem
    if _browser is None:
        _pw = await async_playwright().start()
        kwargs = {"headless": True,
                  "args": ["--disable-dev-shm-usage", "--no-sandbox",
                           "--disable-gpu", "--no-zygote",
                           "--disable-extensions",
                           "--disable-background-networking"]}
        proxy = _proxy_cfg()
        if proxy:
            kwargs["proxy"] = proxy
        _browser = await _pw.chromium.launch(**kwargs)
        _sem = asyncio.Semaphore(MAX_CONCURRENT)
    return _browser, _sem


async def _new_page(browser):
    ctx = await browser.new_context(
        user_agent=UA,
        viewport={"width": 1280, "height": 900},
        locale="en-US")

    async def route(r):
        if r.request.resource_type in ("image", "font", "media"):
            await r.abort()
        else:
            await r.continue_()
    await ctx.route("**/*", route)
    return await ctx.new_page(), ctx


# ---------------------------------------------------------------- cache ---

def _db():
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS cache "
                 "(k TEXT PRIMARY KEY, v TEXT, ts REAL)")
    return conn


def cache_get(key):
    try:
        conn = _db()
        row = conn.execute("SELECT v, ts FROM cache WHERE k=?",
                           (key,)).fetchone()
        conn.close()
        if row and time.time() - row[1] < CACHE_TTL_S:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def cache_set(key, value):
    try:
        conn = _db()
        conn.execute("REPLACE INTO cache (k, v, ts) VALUES (?, ?, ?)",
                     (key, json.dumps(value), time.time()))
        conn.commit()
        conn.close()
    except Exception:
        pass


# --------------------------------------------------------------- scrape ---

async def _scrape_one(provider_mod, item, zip_code, sales_mode=False):
    """Run one provider's scrape. Returns (results, error_note)."""
    # Providers with a real API (e.g. Kroger) skip the browser entirely.
    api_fn = getattr(provider_mod, "api_search", None)
    if api_fn and not sales_mode:
        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None, api_fn, item, zip_code)
            return results or [], None
        except Exception as e:
            return [], "api failed: %s" % str(e)[:120]

    cache_key = "sales:%s:%s" % (provider_mod.STORE_NAME, zip_code) \
        if sales_mode else "search:%s:%s:%s" % (
            provider_mod.STORE_NAME, item.lower().strip(), zip_code)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached, None

    browser, sem = await _ensure()
    async with sem:
        page, ctx = await _new_page(browser)
        try:
            url = provider_mod.sales_url(zip_code) if sales_mode \
                else provider_mod.search_url(item, zip_code)
            await page.goto(url, wait_until="domcontentloaded",
                            timeout=STORE_TIMEOUT_S * 1000)
            # let the SPA render results
            await page.wait_for_timeout(8000)
            if sales_mode:
                results = await provider_mod.parse_sales(page)
            else:
                results = await provider_mod.parse_results(page, url)
            results = results or []
            cache_set(cache_key, results)
            return results, None
        except Exception as e:
            return [], "scrape failed: %s" % str(e)[:120]
        finally:
            try:
                await ctx.close()
            except Exception:
                pass


async def search_all(item, zip_code, providers):
    """Concurrent search across providers. Returns {store: (results, err)}."""
    async def one(mod):
        try:
            res, err = await asyncio.wait_for(
                _scrape_one(mod, item, zip_code), timeout=STORE_TIMEOUT_S + 20)
        except asyncio.TimeoutError:
            res, err = [], "timed out"
        return mod.STORE_NAME, (res, err)

    out = {}
    for name, (res, err) in await asyncio.gather(
            *(one(m) for m in providers)):
        out[name] = (res, err)
    return out


async def sales_all(zip_code, providers):
    async def one(mod):
        try:
            res, err = await asyncio.wait_for(
                _scrape_one(mod, None, zip_code, sales_mode=True),
                timeout=STORE_TIMEOUT_S + 20)
        except asyncio.TimeoutError:
            res, err = [], "timed out"
        return mod.STORE_NAME, (res, err)

    out = {}
    for name, (res, err) in await asyncio.gather(
            *(one(m) for m in providers)):
        out[name] = (res, err)
    return out


def run(coro):
    """Sync entry point. All Playwright work runs on one dedicated
    thread/event-loop so the browser singleton stays loop-bound."""
    loop = _ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=600)


_loop = None


def _ensure_loop():
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()

        def runner():
            asyncio.set_event_loop(_loop)
            _loop.run_forever()

        t = threading.Thread(target=runner, daemon=True)
        t.start()
    return _loop


def q(s):
    return quote_plus(s or "")
