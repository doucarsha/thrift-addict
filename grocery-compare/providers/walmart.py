"""Walmart provider — live prices via Playwright scraping of walmart.com."""
from .base import BaseProvider
from .engine import q
from .stores import STORES

STORE_NAME = "Walmart"
PROVIDER_STATUS = {"status": "blocked",
                   "note": "Walmart blocks automated price checks. Ask Muse in chat for a live check.",
                   "address": STORES["Walmart"]["address"]}

SEARCH_URL_TMPL = "https://www.walmart.com/search?q=%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return ("https://www.walmart.com/shop/deals/food"
            "?facet=special_offers%3AClearance%7C%7Cspecial_offers%3ARollback")


async def parse_results(page, url):
    # Browser scraping disabled: stores block cloud-server IPs.
    # Prices refresh via scheduled checks — see README.
    return []


async def parse_sales(page):
    return []


class WalmartProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
