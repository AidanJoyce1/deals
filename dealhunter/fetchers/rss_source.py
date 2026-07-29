"""Generic RSS/Atom deal fetcher.

Works with any deal feed (Slickdeals, DealNews, Woot, blog feeds, or feeds you
generate yourself with a tool like rss.app). Configure feeds in config.yaml.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ..models import Deal


def _parsed_time(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_rss(name: str, url: str, limit: int = 60) -> list[Deal]:
    """Fetch one feed into Deal objects. Never raises: returns [] on failure."""
    deals: list[Deal] = []
    try:
        feed = feedparser.parse(url)
    except Exception:
        return deals

    for entry in feed.entries[:limit]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        deals.append(
            Deal(
                title=title,
                url=link,
                source=name,
                posted_at=_parsed_time(entry),
            )
        )
    return deals


def fetch_all_rss(feeds: Iterable[dict], per_feed_limit: int = 60) -> list[Deal]:
    out: list[Deal] = []
    for f in feeds:
        out.extend(fetch_rss(f["name"], f["url"], per_feed_limit))
    return out
