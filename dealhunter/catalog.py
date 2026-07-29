"""Durable catalog of every deal ever seen, so SEO pages accumulate instead of
404-ing when a deal drops out of today's feed.

Stored as NDJSON (one deal record per line) — text, diffable, and committed back
to the repo by the Pages workflow so it survives GitHub's stateless rebuilds.

Each build:
  1. loads the catalog,
  2. upserts today's deals (refresh price, bump last_seen, keep first_seen),
  3. prunes entries not seen for `retention_days`,
  4. saves it,
  5. renders a page for every surviving entry — active ones normally, expired
     ones in a noindex "this deal expired" state so the URL stays live (200).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Deal
from .seo import deal_slug


def record_from_deal(deal: Deal, today: str, first_seen: str | None = None) -> dict:
    return {
        "slug": deal_slug(deal),
        "title": deal.title,
        "url": deal.url,
        "source": deal.source,
        "merchant": deal.merchant,
        "category": deal.category,
        "price": deal.price,
        "orig_price": deal.orig_price,
        "discount_pct": deal.discount_pct,
        "image": deal.image,
        "is_local": deal.is_local,
        "is_essential": deal.is_essential,
        "affiliate": deal.affiliate,
        "first_seen": first_seen or today,
        "last_seen": today,
    }


def deal_from_record(rec: dict) -> Deal:
    return Deal(
        title=rec.get("title", ""),
        url=rec.get("url", ""),
        source=rec.get("source", "catalog"),
        price=rec.get("price"),
        orig_price=rec.get("orig_price"),
        discount_pct=rec.get("discount_pct"),
        category=rec.get("category", "general"),
        merchant=rec.get("merchant", ""),
        image=rec.get("image", ""),
        is_local=bool(rec.get("is_local")),
        is_essential=bool(rec.get("is_essential")),
        affiliate=bool(rec.get("affiliate")),
    )


def load(path: str) -> dict[str, dict]:
    p = Path(path)
    if not p.is_file():
        return {}
    catalog: dict[str, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("slug"):
                catalog[rec["slug"]] = rec
        except Exception:
            continue
    return catalog


def update(catalog: dict[str, dict], deals, today: str) -> tuple[dict[str, dict], set[str]]:
    """Upsert today's deals. Returns (catalog, set-of-active-slugs)."""
    active: set[str] = set()
    for d in deals:
        slug = deal_slug(d)
        active.add(slug)
        prev = catalog.get(slug)
        catalog[slug] = record_from_deal(
            d, today, first_seen=(prev or {}).get("first_seen"))
    return catalog, active


def prune(catalog: dict[str, dict], today: str, retention_days: int) -> dict[str, dict]:
    t = date.fromisoformat(today)
    kept = {}
    for slug, rec in catalog.items():
        try:
            age = (t - date.fromisoformat(rec["last_seen"])).days
        except Exception:
            age = 0
        if age <= retention_days:
            kept[slug] = rec
    return kept


def save(path: str, catalog: dict[str, dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Sorted for stable, minimal git diffs.
    lines = [json.dumps(catalog[s], ensure_ascii=False) for s in sorted(catalog)]
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
