"""Meijer provider — live prices via Playwright scraping of meijer.com."""
from .base import BaseProvider
from .engine import q

STORE_NAME = "Meijer"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from meijer.com search."}

SEARCH_URL_TMPL = "https://www.meijer.com/shopping/search/%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return "https://www.meijer.com/shopping/weekly-ad"


async def parse_results(page, url):
    rows = await page.evaluate("""() => {
      const cards = [...document.querySelectorAll('main article')];
      const out = [];
      for (const card of cards.slice(0, 10)) {
        const h3 = card.querySelector('h3');
        const name = h3 ? h3.innerText.trim().replace(/\\s+/g, ' ') : '';
        const pel = card.querySelector(
          '[aria-label="Product pricing information"]');
        const txt = ((pel ? pel.innerText : '') || card.innerText) || '';
        const m = txt.match(/\\$(\\d+\\.\\d{2})/);
        const a = card.querySelector('a[href^="/shopping/product/"]');
        const href = a ? a.getAttribute('href') : '';
        if (name && m) {
          out.push({name: name.slice(0, 120),
                    price: parseFloat(m[1]),
                    sale: /Original price:|Save \\$/i.test(txt),
                    url: href ? 'https://www.meijer.com' + href : null});
        }
      }
      return out;
    }""")
    return [{"store": STORE_NAME, "name": r["name"], "price": r["price"],
             "unit_price": None, "sale": r["sale"], "url": r["url"] or url}
            for r in rows]


async def parse_sales(page):
    return []


class MeijerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
