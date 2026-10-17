"""Grocery price-comparison providers package.

Each provider module exposes:
  - PROVIDER_STATUS: dict(status=..., note=...) — "live", "stub", or "blocked"
  - search(item, zip_code) -> list of result dicts
  - weekly_sales(zip_code) -> list of sale dicts

Result dicts: {store, name, price, unit_price, sale, url}
Sale dicts:   {store, name, price, sale_price, url}
Prices are floats in USD or None when unavailable. Never invent prices.
"""
