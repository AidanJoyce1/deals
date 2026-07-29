"""Core data model for a single deal."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


@dataclass
class Deal:
    title: str
    url: str
    source: str                       # e.g. "slickdeals", "kroger", "dealnews"
    price: Optional[float] = None     # current price if known
    orig_price: Optional[float] = None
    discount_pct: Optional[float] = None
    category: str = "general"
    is_essential: bool = False
    is_local: bool = False            # True for store/restaurant deals near you
    merchant: str = ""                # store / restaurant name
    image: str = ""                   # product image URL (for OG / schema.org)
    affiliate: bool = False           # True once an affiliate tag/deeplink applied
    posted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = 0.0

    # Stable id used for de-duplication across runs.
    @property
    def id(self) -> str:
        basis = self.url or f"{self.source}:{_slug(self.title)}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def to_row(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        d["posted_at"] = self.posted_at.isoformat()
        return d
