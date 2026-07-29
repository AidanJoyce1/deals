"""Orchestrate: fetch -> enrich/score -> filter -> store -> digest.

National sources (RSS, affiliate feeds) are fetched once and shared across all
regions; only the local layer (Kroger by zip) and the rendered output vary per
region. With no `regions:` in config, this runs as a single region at the root.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from .affiliate import monetize, DISCLOSURE
from .digest import render_markdown, render_html, build_subject
from .fetchers import fetch_all_rss, fetch_kroger, fetch_all_feeds
from .regions import normalize_regions
from .tracking import Tracker, popularity_boost
from .models import Deal
from .scoring import enrich_and_score, passes_filter
from .store import Store


def load_config(path: str = "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


def _load_click_stats(tcfg: dict) -> dict:
    """Best-effort load of {category:{...}, merchant:{...}} click counts.

    Supports a local file (tracking.stats_file) or a URL (tracking.stats_url,
    e.g. your collector's /stats endpoint). Never raises.
    """
    import json
    src = (tcfg or {}).get("stats_url") or (tcfg or {}).get("stats_file")
    if not src:
        return {}
    try:
        if str(src).startswith("http"):
            import requests
            return requests.get(src, timeout=15).json()
        return json.loads(Path(src).read_text())
    except Exception:
        return {}


def _render_region(region: dict, national: list[Deal], cfg: dict, *,
                   min_discount: float, essential_min: float, per_section: int,
                   aff_cfg: dict, stats: dict, tcfg: dict, list_cfg: dict,
                   store: Store) -> dict:
    """Score/filter/monetize/render one region over shared national deals."""
    # Local layer for this region (fresh objects); national copied per region so
    # per-region scoring never mutates the shared list.
    kcfg = cfg.get("kroger", {})
    local: list[Deal] = []
    if kcfg.get("enabled"):
        local = fetch_kroger(zipcode=region["zip"], terms=kcfg.get("terms"),
                             min_discount=float(kcfg.get("min_discount", essential_min)))
    deals = [replace(d) for d in national] + local

    scored = [enrich_and_score(d) for d in deals]
    kept = [d for d in scored if passes_filter(d, min_discount, essential_min)]

    if aff_cfg.get("enabled"):
        kept = [monetize(d, aff_cfg) for d in kept]
    affiliate_note = DISCLOSURE if aff_cfg.get("enabled") else ""

    if stats:
        for d in kept:
            d.score += popularity_boost(d, stats)

    added = store.upsert(kept)
    kept.sort(key=lambda d: d.score, reverse=True)

    email_tracker = Tracker(tcfg, medium="email",
                            base_url=tcfg.get("site_base_url", ""),
                            region=region["id"])
    header = f"<!-- {region['id']} | kept {len(kept)} | new {added} -->\n"
    broadcast_html = ""
    if list_cfg.get("enabled"):
        broadcast_html = render_html(kept, min_discount, per_section,
                                     affiliate_note, email_tracker,
                                     unsubscribe=True,
                                     sender_address=list_cfg.get("sender_address", ""))
    return {
        "id": region["id"],
        "label": region["label"],
        "audience_id": region.get("audience_id", ""),
        "markdown": header + render_markdown(kept, min_discount, per_section,
                                             affiliate_note, email_tracker),
        "html": render_html(kept, min_discount, per_section, affiliate_note,
                            email_tracker),
        "broadcast_html": broadcast_html,
        "subject": build_subject(kept) + (f" — {region['label']}"
                                          if region["label"] else ""),
        "deals": kept,
        "stats": {"fetched": len(deals), "kept": len(kept), "new": added},
    }


def run(config_path: str = "config.yaml") -> dict:
    """Run the pipeline. Returns the primary region's result (backward-compatible
    keys: markdown, html, broadcast_html, subject, deals, stats) plus a
    `regions` list with one such result per region.
    """
    cfg = load_config(config_path)
    filt = cfg.get("filters", {})
    min_discount = float(filt.get("min_discount", 50))
    essential_min = float(filt.get("essential_min_discount", 15))
    per_section = cfg.get("per_section", 15)

    # National sources — fetched once, shared across every region.
    national: list[Deal] = []
    if cfg.get("rss_feeds"):
        national += fetch_all_rss(cfg["rss_feeds"],
                                  per_feed_limit=cfg.get("per_feed_limit", 60))
    if cfg.get("feeds"):
        national += fetch_all_feeds(cfg["feeds"])

    tcfg = cfg.get("tracking", {})
    stats = _load_click_stats(tcfg) if tcfg.get("enabled") else {}
    aff_cfg = cfg.get("affiliate", {})
    list_cfg = cfg.get("list", {})

    store = Store(cfg.get("db_path", "deals.db"))
    regions = normalize_regions(cfg)
    region_results = [
        _render_region(r, national, cfg, min_discount=min_discount,
                       essential_min=essential_min, per_section=per_section,
                       aff_cfg=aff_cfg, stats=stats, tcfg=tcfg,
                       list_cfg=list_cfg, store=store)
        for r in regions
    ]
    store.close()

    primary = region_results[0]
    return {
        "markdown": primary["markdown"],
        "html": primary["html"],
        "broadcast_html": primary["broadcast_html"],
        "subject": primary["subject"],
        "deals": primary["deals"],
        "stats": primary["stats"],
        "regions": region_results,
    }
