"""Click tracking: UTM tags, Amazon ascsubtag, logged redirects, and a
popularity signal that feeds real clicks back into scoring.

Design decisions (see README for the why):
  * Non-Amazon links get UTM params and can route through a logged redirect
    page (/go/<id>/) that pings your collector, then forwards.
  * Amazon links stay DIRECT (never redirected — Amazon prohibits redirects
    that obscure the destination) and instead carry Amazon's native
    `ascsubtag`, which shows per-channel/category performance in your reports.
  * The collector is any endpoint that accepts a POST beacon (a ready-made
    Cloudflare Worker is in tracker/). If no beacon_url is set, tracking is a
    silent no-op.
"""
from __future__ import annotations

import math
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Deal

_SAFE = re.compile(r"[^a-zA-Z0-9_-]+")


def _sanitize(s: str, maxlen: int = 40) -> str:
    return _SAFE.sub("-", (s or "").strip().lower()).strip("-")[:maxlen] or "na"


def _is_amazon(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return "amazon." in host or host.endswith("amzn.to") or host == "amzn.com"


def _merge_query(url: str, extra: dict) -> str:
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.update(extra)
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q, doseq=True), parts.fragment))


def short_id(deal: Deal) -> str:
    return deal.id[:10]


class Tracker:
    """Builds tracked links for one channel (medium)."""

    def __init__(self, cfg: dict | None, medium: str, base_url: str = "",
                 region: str = ""):
        cfg = cfg or {}
        self.enabled = bool(cfg.get("enabled"))
        self.medium = medium                       # "web" | "email"
        self.region = region                       # region id, for attribution
        self.source = cfg.get("source", "dealboard")
        self.campaign = cfg.get("campaign", "daily")
        self.beacon_url = cfg.get("beacon_url", "")
        self.redirects = bool(cfg.get("redirects"))
        self.amazon_direct = cfg.get("amazon_direct", True)
        # Explicit only: web board links stay relative; email passes an absolute base.
        self.base_url = (base_url or "").rstrip("/")

    # -- destination the user ultimately lands on (with attribution params) --
    def destination(self, deal: Deal) -> str:
        url = deal.url
        if not self.enabled:
            return url
        if _is_amazon(url):
            # Amazon's own sub-tag; keeps the amazon.com URL clean of UTM.
            parts = [self.medium, self.region, deal.category]
            sub = _sanitize("-".join(p for p in parts if p), 70)
            return _merge_query(url, {"ascsubtag": sub})
        if deal.affiliate:
            # Network deep link (Awin/CJ/…) already carries tracking — don't add
            # UTM params that could interfere with attribution.
            return url
        return _merge_query(url, {
            "utm_source": self.source,
            "utm_medium": self.medium,
            "utm_campaign": f"{self.campaign}-{self.region}" if self.region else self.campaign,
            "utm_content": short_id(deal),
            "utm_term": _sanitize(deal.category),
        })

    def uses_redirect(self, deal: Deal) -> bool:
        if not (self.enabled and self.redirects):
            return False
        if _is_amazon(deal.url) and self.amazon_direct:
            return False
        return True

    # -- the href the board/email link points at --
    def link(self, deal: Deal) -> str:
        if self.uses_redirect(deal):
            path = f"go/{short_id(deal)}/"
            return f"{self.base_url}/{path}" if self.base_url else path
        return self.destination(deal)

    def redirect_map(self, deals) -> dict[str, dict]:
        """{short_id: {dest, merchant, category}} for deals that use a redirect."""
        out: dict[str, dict] = {}
        for d in deals:
            if self.uses_redirect(d):
                out[short_id(d)] = {
                    "dest": self.destination(d),
                    "merchant": d.merchant or d.source,
                    "category": d.category,
                }
        return out


# ── popularity feedback: turn logged clicks into a scoring signal ───────────
def popularity_boost(deal: Deal, stats: dict, weight: float = 10.0) -> float:
    """Boost a deal's score by how often its category/merchant get clicked.

    stats shape: {"category": {name: count}, "merchant": {name: count}}.
    Uses log scaling normalized to the busiest bucket, so a runaway category
    can't dominate. Returns 0 when there's no signal.
    """
    if not stats:
        return 0.0
    boost = 0.0
    for dim, key in (("category", deal.category), ("merchant", deal.merchant)):
        table = stats.get(dim) or {}
        count = table.get(key)
        if not count:
            continue
        top = max(table.values()) or 1
        boost += weight * (math.log1p(count) / math.log1p(top))
    return round(boost, 2)
