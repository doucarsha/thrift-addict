"""Kroger provider — live prices via Playwright scraping of kroger.com."""
from .base import BaseProvider
from .engine import q

STORE_NAME = "Kroger"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from kroger.com search."}

SEARCH_URL_TMPL = "https://www.kroger.com/search?query=%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return "https://www.kroger.com/weeklyad"


async def parse_results(page, url):
    rows = await page.evaluate("""() => {
      const cards = [...document.querySelectorAll(
        'main div:has(> a[href^="/p/"])')];
      const out = [];
      for (const card of cards.slice(0, 10)) {
        const a = card.querySelector('a[href^="/p/"]');
        const name = a ? a.innerText.trim().replace(/\\s+/g, ' ') : '';
        const href = a ? a.getAttribute('href') : '';
        const txt = card.innerText || '';
        const m = txt.match(/\\$(\\d+\\.\\d{2})/);
        const u = txt.match(/\\$[\\d.]+\\/([a-zA-Z ]+)/);
        if (name && m) {
          out.push({name: name.slice(0, 120),
                    price: parseFloat(m[1]),
                    unit_price: u ? ('$' + m[1] + '/' + u[1].trim()) : null,
                    sale: /Sale:/i.test(txt),
                    url: href ? 'https://www.kroger.com' + href.split('?')[0]
                              : null});
        }
      }
      return out;
    }""")
    return [{"store": STORE_NAME, "name": r["name"], "price": r["price"],
             "unit_price": r["unit_price"], "sale": r["sale"],
             "url": r["url"] or url}
            for r in rows]


async def parse_sales(page):
    return []


class KrogerProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
