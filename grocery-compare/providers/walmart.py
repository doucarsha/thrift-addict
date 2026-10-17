"""Walmart provider — live prices via Playwright scraping of walmart.com."""
from .base import BaseProvider
from .engine import q

STORE_NAME = "Walmart"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from walmart.com search."}

SEARCH_URL_TMPL = "https://www.walmart.com/search?q=%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return ("https://www.walmart.com/shop/deals/food"
            "?facet=special_offers%3AClearance%7C%7Cspecial_offers%3ARollback")


async def parse_results(page, url):
    # Infinite scroll: load a couple more batches of tiles.
    for _ in range(2):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2500)
    rows = await page.evaluate("""() => {
      const links = [...document.querySelectorAll('main a[href^="/ip/"]')];
      const seen = new Set();
      const out = [];
      for (const a of links) {
        const href = a.getAttribute('href');
        if (!href || seen.has(href)) continue;
        seen.add(href);
        const h3 = a.querySelector('h3');
        const name = h3 ? h3.innerText.trim().replace(/\\s+/g, ' ') : '';
        const tile = a.closest('div');
        const txt = ((tile ? tile.innerText : '') || a.innerText) || '';
        const m = txt.match(/(?:current price|Price)\\s*\\$(\\d+\\.\\d{2})/i)
               || txt.match(/\\$(\\d+\\.\\d{2})/);
        if (name && m) {
          out.push({name: name.slice(0, 120),
                    price: parseFloat(m[1]),
                    sale: /Rollback/i.test(txt),
                    url: 'https://www.walmart.com' + href.split('?')[0]});
        }
        if (out.length >= 12) break;
      }
      return out;
    }""")
    return [{"store": STORE_NAME, "name": r["name"], "price": r["price"],
             "unit_price": None, "sale": r["sale"], "url": r["url"]}
            for r in rows]


async def parse_sales(page):
    return []


class WalmartProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
