"""Aldi provider — live prices via Playwright scraping of aldi.us."""
from .base import BaseProvider
from .engine import q
from .stores import STORES

STORE_NAME = "Aldi"
PROVIDER_STATUS = {"status": "blocked",
                   "note": "Aldi blocks automated price checks. Ask Muse in chat for a live check.",
                   "address": STORES["Aldi"]["address"]}

SEARCH_URL_TMPL = "https://www.aldi.us/store/aldi/s?k=%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return "https://www.aldi.us/store/aldi/flyers/view/weekly/print"


async def parse_results(page, url):
    # Browser scraping disabled: stores block cloud-server IPs.
    # Prices refresh via scheduled checks — see README.
    return []


async def parse_sales(page):
    return []


class AldiProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
