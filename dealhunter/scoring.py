"""The 'brain': detect essentials, parse discounts, and rank deals.

This is where you tune what 'most necessary and beneficial' means for you.
Everything here is pure/testable so you can iterate confidently.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from .models import Deal

# ---------------------------------------------------------------------------
# 1. Essential categories. Add/remove keywords to reshape what counts as an
#    "essential". Order matters only for which category label gets assigned.
# ---------------------------------------------------------------------------
ESSENTIAL_CATEGORIES: dict[str, list[str]] = {
    "groceries": [
        "rice", "beans", "pasta", "flour", "sugar", "cooking oil", "olive oil",
        "coffee", "cereal", "oatmeal", "canned", "peanut butter", "milk",
        "eggs", "bread", "chicken", "ground beef", "frozen vegetables", "broth",
    ],
    "household": [
        "toilet paper", "paper towel", "laundry detergent", "dish soap",
        "trash bag", "cleaning", "disinfectant", "batteries", "light bulb",
        "aluminum foil", "storage bag", "air filter",
    ],
    "hygiene": [
        "toothpaste", "toothbrush", "shampoo", "conditioner", "body wash",
        "soap", "deodorant", "razor", "floss", "feminine", "hand sanitizer",
    ],
    "health": [
        "vitamin", "ibuprofen", "acetaminophen", "tylenol", "advil", "allergy",
        "first aid", "bandage", "cough", "cold medicine", "thermometer",
    ],
    "baby": ["diaper", "baby wipes", "formula", "baby food"],
    "pet": ["dog food", "cat food", "cat litter", "pet food"],
}

# Categories that are nice-to-have but should never be flagged "essential".
NON_ESSENTIAL_HINTS = ["gaming", "console", "lego", "collectible", "jewelry", "toy"]


def categorize(title: str) -> tuple[str, bool]:
    """Return (category, is_essential) for a deal title."""
    t = (title or "").lower()
    for category, keywords in ESSENTIAL_CATEGORIES.items():
        if any(kw in t for kw in keywords):
            return category, True
    return "general", False


# ---------------------------------------------------------------------------
# 2. Discount extraction from free-text titles (RSS deals rarely give clean
#    numeric fields, so we mine the title). Kroger/API sources set these
#    numerically and skip this path.
# ---------------------------------------------------------------------------
_PCT_RE = re.compile(r"(\d{1,3})\s?%\s?off", re.I)
_WAS_RE = re.compile(r"\$?([\d,]+(?:\.\d{1,2})?)\s*(?:->|→|from|\(?\s*(?:was|reg\.?|orig\.?|list)\s*)\$?([\d,]+(?:\.\d{1,2})?)", re.I)
_FREE_RE = re.compile(r"\bfree\b", re.I)
_PRICE_RE = re.compile(r"\$([\d,]+(?:\.\d{1,2})?)")


def _f(x: str) -> float:
    return float(x.replace(",", ""))


def extract_discount(title: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Best-effort (price, orig_price, discount_pct) from a title string."""
    t = title or ""

    m = _PCT_RE.search(t)
    if m:
        pct = min(float(m.group(1)), 100.0)
        return None, None, pct

    m = _WAS_RE.search(t)
    if m:
        low, high = sorted((_f(m.group(1)), _f(m.group(2))))
        if high > 0 and low < high:
            return low, high, round((1 - low / high) * 100, 1)

    if _FREE_RE.search(t):
        return 0.0, None, 100.0

    return None, None, None


# ---------------------------------------------------------------------------
# 3. Scoring. Higher = more worth surfacing today.
# ---------------------------------------------------------------------------
def score_deal(deal: Deal, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(timezone.utc)
    score = 0.0

    # Discount magnitude (0-60 pts). Missing discount => modest neutral value.
    if deal.discount_pct is not None:
        score += min(deal.discount_pct, 100) * 0.6
    else:
        score += 12

    # Essentials matter more than wants.
    if deal.is_essential:
        score += 40

    # Local store/restaurant deals get a bump (your stated priority).
    if deal.is_local:
        score += 15

    # Freshness: decay ~1 pt/hour, floor at -24.
    posted = deal.posted_at
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    hours_old = (now - posted).total_seconds() / 3600
    score += max(-24, -hours_old)

    return round(score, 2)


def enrich_and_score(deal: Deal, now: Optional[datetime] = None) -> Deal:
    """Fill missing category/discount fields, then score. Idempotent."""
    cat, ess = categorize(deal.title)
    if deal.category == "general":
        deal.category = cat              # only fill a still-generic label
    deal.is_essential = deal.is_essential or ess  # never downgrade essential
    if deal.discount_pct is None:
        p, op, pct = extract_discount(deal.title)
        deal.price = deal.price if deal.price is not None else p
        deal.orig_price = deal.orig_price if deal.orig_price is not None else op
        deal.discount_pct = pct
    deal.score = score_deal(deal, now)
    return deal


def passes_filter(deal: Deal, min_discount: float, essential_min_discount: float) -> bool:
    """Keep a deal if it's a big discount OR an essential with a modest one.

    Mirrors the ask: 'deals up to 80% off OR discounts on essentials.'
    """
    pct = deal.discount_pct or 0
    if deal.is_essential:
        return pct >= essential_min_discount or deal.is_local
    return pct >= min_discount
