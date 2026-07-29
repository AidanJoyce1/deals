"""Affiliate product-feed fetcher.

One parser for the networks that publish downloadable product feeds — Awin, CJ,
Rakuten, Impact — because they all boil down to the same thing: rows of products
with a price, a sale price, and an already-affiliate-tracked link. You configure
a feed URL + a column mapping (or use a preset), and this turns the catalog into
Deal objects, keeping only items actually on sale.

Because the link in a feed is already commission-tracked by the network, these
Deals are marked affiliate=True and are NOT re-wrapped by affiliate.monetize().

Presets encode the common column names, but feeds are configurable per advertiser
— verify against your actual feed and override with `mapping:` if needed.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Iterable

import requests

from ..models import Deal

# Preset column mappings. Values may be a single column name or a list of
# fallbacks (first present wins). Lookup is case-insensitive.
PRESETS: dict[str, dict] = {
    "awin": {  # verified against Awin publisher feed columns
        "format": "csv",
        "mapping": {
            "title": "product_name",
            "url": "aw_deep_link",
            "price": ["rrp_price", "store_price", "base_price"],
            "sale_price": "search_price",
            "image": ["aw_image_url", "merchant_image_url"],
            "merchant": "merchant_name",
            "category": ["merchant_category", "category_name"],
            "currency": "currency",
        },
    },
    "cj": {  # verify against your CJ feed / GraphQL export
        "format": "csv",
        "mapping": {
            "title": ["title", "name", "TITLE"],
            "url": ["link", "buyurl", "BUYURL", "clickUrl"],
            "price": ["price", "retailPrice", "PRICE"],
            "sale_price": ["salePrice", "saleprice", "SALEPRICE"],
            "image": ["imageLink", "imageurl", "IMAGEURL", "image"],
            "merchant": ["advertiserName", "advertiser-name", "ADVERTISERNAME", "programName"],
            "category": ["googleProductCategory", "advertiserCategory", "ADVERTISERCATEGORY"],
            "currency": ["currency", "CURRENCY"],
        },
    },
    "rakuten": {  # verify against your Rakuten feed
        "format": "xml",
        "mapping": {
            "title": ["productname", "name"],
            "url": ["linkurl", "link"],
            "price": ["price", "retailprice"],
            "sale_price": ["saleprice"],
            "image": ["imageurl", "image"],
            "merchant": ["merchantname"],
            "category": ["category", "primarycategory"],
            "currency": ["currency"],
        },
    },
    "generic": {"mapping": {}},
}


# ── loading ──────────────────────────────────────────────────────────────────
def _load_bytes(src: str) -> bytes:
    if str(src).startswith("http"):
        r = requests.get(src, timeout=45)
        r.raise_for_status()
        data = r.content
    else:
        with open(src, "rb") as fh:
            data = fh.read()
    if data[:2] == b"\x1f\x8b" or str(src).endswith(".gz"):
        data = gzip.decompress(data)
    return data


def _detect_format(src: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    s = str(src).lower().rstrip(".gz")
    if s.endswith((".xml", ".xml-tree")):
        return "xml"
    if s.endswith(".json"):
        return "json"
    if s.endswith((".tsv", ".txt")):
        return "tsv"
    return "csv"


# ── row iteration per format ─────────────────────────────────────────────────
def _rows_csv(data: bytes, delimiter: str | None) -> Iterable[dict]:
    text = data.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    if not delimiter:
        counts = {d: sample.count(d) for d in (",", "\t", "|", ";")}
        delimiter = max(counts, key=counts.get) if any(counts.values()) else ","
    yield from csv.DictReader(io.StringIO(text), delimiter=delimiter)


def _localname(tag: str) -> str:
    return tag.split("}")[-1].lower()


def _rows_xml(data: bytes) -> Iterable[dict]:
    root = ET.fromstring(data)
    # The product row is the element tag that repeats most and has children.
    tags = Counter(el.tag for el in root.iter() if len(list(el)))
    if not tags:
        return
    row_tag = tags.most_common(1)[0][0]
    for el in root.iter(row_tag):
        yield {_localname(c.tag): (c.text or "").strip() for c in el}


def _rows_json(data: bytes) -> Iterable[dict]:
    obj = json.loads(data.decode("utf-8", errors="replace"))
    if isinstance(obj, list):
        rows = obj
    elif isinstance(obj, dict):
        rows = next((v for v in obj.values() if isinstance(v, list)
                     and v and isinstance(v[0], dict)), [])
    else:
        rows = []
    for r in rows:
        if isinstance(r, dict):
            yield r


# ── mapping + parsing helpers ────────────────────────────────────────────────
def _lower_keys(row: dict) -> dict:
    return {str(k).lower(): v for k, v in row.items()}


def _get(row_l: dict, spec) -> str:
    names = spec if isinstance(spec, list) else [spec]
    for n in names:
        v = row_l.get(str(n).lower())
        if v not in (None, ""):
            return str(v).strip()
    return ""


_NUM = re.compile(r"[0-9][0-9.,\u00a0 ]*[0-9]|[0-9]")


def _price(s: str) -> float | None:
    """Parse a price string in US (1,299.00) or EU (1.299,00) formats."""
    if not s:
        return None
    m = _NUM.search(s)
    if not m:
        return None
    num = m.group(0).replace("\u00a0", "").replace(" ", "")
    if "," in num and "." in num:
        # The right-most separator is the decimal; the other is thousands.
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        dec = num.rsplit(",", 1)[-1]
        num = (num.replace(",", ".") if (num.count(",") == 1 and len(dec) == 2)
               else num.replace(",", ""))
    elif num.count(".") > 1:
        num = num.replace(".", "")               # dots as thousands separators
    else:
        head, _, dec = num.partition(".")
        if len(dec) == 3 and len(head) <= 3:      # ambiguous 1.299 -> 1299
            num = num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


# ── public API ───────────────────────────────────────────────────────────────
def fetch_feed(name: str, url: str, mapping: dict, *, fmt: str | None = None,
               delimiter: str | None = None, min_discount: float = 15.0,
               limit: int = 300, max_rows: int = 20000,
               category_hint: str = "") -> list[Deal]:
    """Parse one product feed into on-sale Deals. Never raises."""
    deals: list[Deal] = []
    try:
        data = _load_bytes(url)
    except Exception:
        return deals

    fmt = _detect_format(url, fmt)
    try:
        if fmt == "xml":
            rows = _rows_xml(data)
        elif fmt == "json":
            rows = _rows_json(data)
        else:
            rows = _rows_csv(data, "\t" if fmt == "tsv" else delimiter)
    except Exception:
        return deals

    for i, row in enumerate(rows):
        if i >= max_rows or len(deals) >= limit:
            break
        rl = _lower_keys(row)
        title = _get(rl, mapping.get("title", "title"))
        link = _get(rl, mapping.get("url", "url"))
        if not title or not link:
            continue
        orig = _price(_get(rl, mapping.get("price", "price")))
        sale = _price(_get(rl, mapping.get("sale_price", "sale_price")))
        # A feed is a full catalog; keep only genuine markdowns.
        if not orig or not sale or sale <= 0 or sale >= orig:
            continue
        pct = round((1 - sale / orig) * 100, 1)
        if pct < min_discount:
            continue
        deals.append(Deal(
            title=title,
            url=link,
            source=name,
            price=sale,
            orig_price=orig,
            discount_pct=pct,
            merchant=_get(rl, mapping.get("merchant", "merchant")),
            image=_get(rl, mapping.get("image", "image")),
            category=(_get(rl, mapping.get("category", "category")).lower()
                      or category_hint or "general"),
            affiliate=True,          # feed links are already commission-tracked
        ))
    return deals


def _resolve_mapping(feed: dict) -> tuple[dict, str | None]:
    preset = PRESETS.get(feed.get("network", "generic"), PRESETS["generic"])
    mapping = dict(preset.get("mapping", {}))
    mapping.update(feed.get("mapping", {}) or {})   # explicit override wins
    return mapping, feed.get("format") or preset.get("format")


def fetch_all_feeds(feeds: Iterable[dict]) -> list[Deal]:
    out: list[Deal] = []
    for feed in feeds:
        if not feed.get("url"):
            continue
        mapping, fmt = _resolve_mapping(feed)
        out.extend(fetch_feed(
            feed.get("name", feed.get("network", "feed")),
            feed["url"], mapping, fmt=fmt,
            delimiter=feed.get("delimiter"),
            min_discount=float(feed.get("min_discount", 15)),
            limit=int(feed.get("limit", 300)),
            category_hint=feed.get("category", ""),
        ))
    return out
