"""Aldi provider — live prices via Playwright scraping of aldi.us."""
from .base import BaseProvider
from .engine import q

STORE_NAME = "Aldi"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from aldi.us search."}


def search_url(item, zip_code):
    return "https://www.aldi.us/store/aldi/s?k=%s" % q(item)


def sales_url(zip_code):
    return "https://www.aldi.us/store/aldi/flyers/view/weekly/print"


async def parse_results(page, url):
    """Extract product results. Selectors refined from live DOM research."""
    return await _parse_cards(
        page, url,
        card_sel="[data-testid='product-card'], [class*='product-card'], li[class*='product']",
        name_sel="[class*='product-name'], [class*='ProductName'], h3, h4",
        price_sel="[class*='product-price'], [class*='ProductPrice'], [data-testid='price']",
    )


async def parse_sales(page):
    return []


async def _parse_cards(page, url, card_sel, name_sel, price_sel):
    import re
    results = []
    cards = await page.query_selector_all(card_sel)
    for card in cards[:8]:
        try:
            name_el = await card.query_selector(name_sel)
            name = (await name_el.inner_text()).strip() if name_el else ""
            price_el = await card.query_selector(price_sel)
            price_txt = (await price_el.inner_text()).strip() if price_el else ""
            m = re.search(r"\$(\d+(?:\.\d{1,2})?)", price_txt.replace(",", ""))
            price = float(m.group(1)) if m else None
            link_el = await card.query_selector("a[href]")
            href = await link_el.get_attribute("href") if link_el else ""
            if href and href.startswith("/"):
                href = "https://www.aldi.us" + href
            if name and price:
                results.append({"store": STORE_NAME, "name": name[:120],
                                "price": price, "unit_price": None,
                                "sale": False, "url": href or url})
        except Exception:
            continue
    return results


class AldiProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
