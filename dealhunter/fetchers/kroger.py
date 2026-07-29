"""Kroger public API fetcher — local essentials with real promo pricing.

Kroger is headquartered in Ohio and covers the Willoughby area, so this is your
best 'essentials near me' source with structured regular-vs-promo prices.

Setup (free):
  1. Create an app at https://developer.kroger.com  -> get client_id/secret.
  2. Export creds:  export KROGER_CLIENT_ID=...  KROGER_CLIENT_SECRET=...
  3. Public tier: OAuth2 client-credentials, scope 'product.compact'.
     Rate limit ~1,600 calls/day per endpoint.

If creds are absent, fetch_kroger() simply returns [] so the pipeline still runs.
"""
from __future__ import annotations

import base64
import os
from typing import Optional

import requests

from ..models import Deal

TOKEN_URL = "https://api.kroger.com/v1/connect/oauth2/token"
LOCATIONS_URL = "https://api.kroger.com/v1/locations"
PRODUCTS_URL = "https://api.kroger.com/v1/products"


def _token() -> Optional[str]:
    cid = os.getenv("KROGER_CLIENT_ID")
    secret = os.getenv("KROGER_CLIENT_SECRET")
    if not cid or not secret:
        return None
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "product.compact"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("access_token")


def _nearest_location(token: str, zipcode: str, radius: int = 15) -> Optional[dict]:
    r = requests.get(
        LOCATIONS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"filter.zipCode.near": zipcode, "filter.radiusInMiles": radius,
                "filter.limit": 1},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json().get("data", [])
    return data[0] if data else None


def _search_products(token: str, location_id: str, term: str, limit: int = 20) -> list[dict]:
    r = requests.get(
        PRODUCTS_URL,
        headers={"Authorization": f"Bearer {token}"},
        params={"filter.term": term, "filter.locationId": location_id,
                "filter.limit": limit},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_kroger(zipcode: str = "44094", terms: Optional[list[str]] = None,
                 min_discount: float = 10.0) -> list[Deal]:
    """Return Kroger products currently on promo near `zipcode`."""
    token = _token()
    if not token:
        return []

    terms = terms or ["milk", "eggs", "bread", "chicken", "coffee",
                      "diapers", "detergent", "toothpaste"]
    loc = _nearest_location(token, zipcode)
    if not loc:
        return []
    location_id = loc["locationId"]
    store_name = loc.get("name", "Kroger")

    deals: list[Deal] = []
    for term in terms:
        for p in _search_products(token, location_id, term):
            items = p.get("items") or [{}]
            price = items[0].get("price") or {}
            regular = price.get("regular")
            promo = price.get("promo")
            if not regular or not promo or promo <= 0 or promo >= regular:
                continue
            pct = round((1 - promo / regular) * 100, 1)
            if pct < min_discount:
                continue
            desc = p.get("description", term)
            deals.append(
                Deal(
                    title=f"{desc} — ${promo:.2f} (was ${regular:.2f})",
                    url="https://www.kroger.com/",
                    source="kroger",
                    price=promo,
                    orig_price=regular,
                    discount_pct=pct,
                    is_essential=True,
                    is_local=True,
                    merchant=store_name,
                )
            )
    return deals
