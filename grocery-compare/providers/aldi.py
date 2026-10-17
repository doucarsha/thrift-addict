"""Aldi provider — live prices via Playwright scraping of aldi.us."""
from .base import BaseProvider
from .engine import q

STORE_NAME = "Aldi"
PROVIDER_STATUS = {"status": "live",
                   "note": "Live prices from aldi.us search."}

SEARCH_URL_TMPL = "https://www.aldi.us/store/aldi/s?k=%s"


def search_url(item, zip_code):
    return SEARCH_URL_TMPL % q(item)


def sales_url(zip_code):
    return "https://www.aldi.us/store/aldi/flyers/view/weekly/print"


async def parse_results(page, url):
    rows = await page.evaluate("""() => {
      const cards = [...document.querySelectorAll('main div[role="group"]')];
      const out = [];
      for (const card of cards.slice(0, 10)) {
        const h3 = card.querySelector('h3');
        const name = h3 ? h3.innerText.trim().replace(/\\s+/g, ' ') : '';
        const btn = card.querySelector('button');
        const txt = (btn ? btn.innerText : card.innerText) || '';
        const cur = txt.match(/Current price:\\s*\\$([\\d.]+)/);
        const orig = txt.match(/Original Price:\\s*\\$([\\d.]+)/);
        if (name && cur) {
          out.push({name: name.slice(0, 120),
                    price: parseFloat(cur[1]),
                    sale: /% off/i.test(txt) || !!orig});
        }
      }
      return out;
    }""")
    return [{"store": STORE_NAME, "name": r["name"], "price": r["price"],
             "unit_price": None, "sale": r["sale"], "url": url}
            for r in rows]


async def parse_sales(page):
    return []


class AldiProvider(BaseProvider):
    STORE_NAME = STORE_NAME
    PROVIDER_STATUS = PROVIDER_STATUS

    def search(self, item, zip_code):
        raise NotImplementedError("use engine.search_all")

    def weekly_sales(self, zip_code):
        raise NotImplementedError("use engine.sales_all")
