"""Kroger provider — live prices via Playwright scraping of kroger.com."""
from .base import BaseProvider
from .engine import q
from .aldi import _parse_cards

STORE_NAME = "Kroger"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from kroger.com search."}


def search_url(item, zip_code):
    return "https://www.kroger.com/search?query=%s" % q(item)


def sales_url(zip_code):
    return "https://www.kroger.com/weeklyad"


async def parse_results(page, url):
    return await _parse_cards(
        page, url,
        card_sel="[data-testid='product-card'], .ProductCard, [class*='product-card']",
        name_sel="[data-testid='product-title'], [class*='product-title'], h3",
        price_sel="[data-testid='product-price'], [class*='product-price']",
    )


async def parse_sales(page):
    return []


class KrogerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
