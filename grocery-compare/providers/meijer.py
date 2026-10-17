"""Meijer provider — live prices via Playwright scraping of meijer.com."""
from .base import BaseProvider
from .engine import q
from .aldi import _parse_cards

STORE_NAME = "Meijer"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from meijer.com search."}


def search_url(item, zip_code):
    return "https://www.meijer.com/shopping/search/%s" % q(item)


def sales_url(zip_code):
    return "https://www.meijer.com/shopping/weekly-ad"


async def parse_results(page, url):
    return await _parse_cards(
        page, url,
        card_sel="[data-testid='product-card'], [class*='product-tile'], [class*='product-card']",
        name_sel="[class*='product-title'], [class*='product-name'], h3",
        price_sel="[class*='price'], [data-testid='price']",
    )


async def parse_sales(page):
    return []


class MeijerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
