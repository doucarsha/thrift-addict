"""Provider interface for grocery price comparison.

A provider module must define:
  PROVIDER_STATUS = {"status": "live"|"stub"|"blocked", "note": str}
  STORE_NAME      = "Aldi" (etc.)
  def search(item, zip_code) -> list[dict]
  def weekly_sales(zip_code) -> list[dict]

Search result dict:
  {"store": str, "name": str, "price": float|None, "unit_price": str|None,
   "sale": bool, "url": str|None}

Weekly-sale dict:
  {"store": str, "name": str, "price": float|None, "sale_price": float|None,
   "url": str|None}

Rules:
  - Never invent prices. If the provider cannot fetch real data, return [].
  - Keep PROVIDER_STATUS honest: "live" (returning real data), "stub"
    (not implemented yet), "blocked" (site blocks automated access).
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    STORE_NAME = "Unknown"
    # Overridden by each provider module; kept here for tooling.
    PROVIDER_STATUS = {"status": "stub", "note": "Not implemented yet."}

    @abstractmethod
    def search(self, item, zip_code):
        """Return list of result dicts for `item` near `zip_code`."""
        raise NotImplementedError

    @abstractmethod
    def weekly_sales(self, zip_code):
        """Return list of this week's notable sale dicts near `zip_code`."""
        raise NotImplementedError

    def status(self):
        return {"store": self.STORE_NAME, **self.PROVIDER_STATUS}
