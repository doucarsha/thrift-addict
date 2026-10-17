"""Walmart provider — live prices via Playwright scraping of walmart.com."""
from .base import BaseProvider
from .engine import q
from .aldi import _parse_cards

STORE_NAME = "Walmart"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from walmart.com search."}


def search_url(item, zip_code):
    return "https://www.walmart.com/search?q=%s" % q(item)


def sales_url(zip_code):
    return ("https://www.walmart.com/shop/deals/food"
            "?facet=special_offers%3AClearance%7C%7Cspecial_offers%3ARollback")


async def parse_results(page, url):
    return await _parse_cards(
        page, url,
        card_sel="[data-testid='list-view'] > div, div[data-item-id], [class*='search-result-gridview-item']",
        name_sel="[data-automation-id='product-title'], span[class*='normal']",
        price_sel="[data-automation-id='product-price'], div[class*='price']",
    )


async def parse_sales(page):
    return []


class WalmartProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
