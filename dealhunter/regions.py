"""Normalize config into a list of regions.

Multi-region is opt-in: add a `regions:` list to config. Without it, we
synthesize a single region from `location` so everything behaves exactly as
before (one page at the site root, one digest).
"""
from __future__ import annotations

import re


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def normalize_regions(cfg: dict) -> list[dict]:
    """Return [{id, label, zip, audience_id}, …]. Always at least one region."""
    default_zip = str((cfg.get("kroger") or {}).get("zipcode", "44094"))
    regions = cfg.get("regions")
    if regions:
        out = []
        for r in regions:
            label = r.get("label", "Deals")
            out.append({
                "id": r.get("id") or _slug(label),
                "label": label,
                "zip": str(r.get("zip") or r.get("zipcode") or default_zip),
                "audience_id": r.get("audience_id", ""),
            })
        return out
    # Single default region from `location` (backward compatible).
    loc = cfg.get("location") or {}
    return [{
        "id": _slug(loc.get("label", "")) or "home",
        "label": loc.get("label", "Deals Board"),
        "zip": default_zip,
        "audience_id": (cfg.get("list") or {}).get("audience_id", ""),
    }]
