"""Meijer provider — live prices via Playwright scraping of meijer.com."""
from .base import BaseProvider
from .engine import q
from .stores import STORES

STORE_NAME = "Meijer"
PROVIDER_STATUS = {"status": "blocked",
                   "note": "Meijer blocks automated price checks. Ask Muse in chat for a live check.",
                   "address": STORES["Meijer"]["address"]}

SEARCH_URL_TMPL = "https://www.meijer.com/shopping/search/%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return "https://www.meijer.com/shopping/weekly-ad"


async def parse_results(page, url):
    # Browser scraping disabled: stores block cloud-server IPs.
    # Prices refresh via scheduled checks — see README.
    return []


async def parse_sales(page):
    return []


class MeijerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
