"""SEO surface: a durable, crawlable page per deal + sitemap + robots.

Region board pages are transient (they change daily); these per-deal pages are
the thing search engines index and rank. Each carries schema.org Product/Offer
JSON-LD (rich results), Open Graph tags, a canonical URL, the affiliate
disclosure, and internal links to related deals and the board.

IMPORTANT REALITIES (see README):
  * SEO is a long game; thin one-line affiliate pages risk Google's
    scaled-content / thin-affiliate policies. Pages here add price context,
    a blurb, and related-deal links to carry real value — lean into your local
    angle for winnable keywords.
  * Deals expire and Pages deploys are stateless, so to ACCUMULATE indexed
    pages the output must persist (commit the site dir or cache it). Expired
    deals render with an "expired" state and schema availability.
  * A `site.base_url` is required for absolute canonical/sitemap URLs.
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import date, datetime, timezone

from .models import Deal
from .tracking import short_id


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def deal_slug(deal: Deal) -> str:
    return f"{_slug(deal.title)[:60].strip('-')}-{short_id(deal)}"


def deal_path(deal: Deal) -> str:
    return f"deal/{deal_slug(deal)}/"


def _jsonld(deal: Deal, canonical: str, active: bool) -> str:
    """Product + Offer structured data. Only emits an Offer when a real price is
    known (Google requires a price); otherwise a lighter Product object.
    """
    node: dict = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": deal.title,
    }
    if deal.merchant:
        node["brand"] = {"@type": "Brand", "name": deal.merchant}
    if deal.image:
        node["image"] = [deal.image]
    if deal.price and deal.price > 0:
        node["offers"] = {
            "@type": "Offer",
            "url": canonical,
            "priceCurrency": "USD",
            "price": f"{deal.price:.2f}",
            "availability": ("https://schema.org/InStock" if active
                             else "https://schema.org/Discontinued"),
            "priceValidUntil": f"{date.today().year}-12-31",
        }
    return json.dumps(node, ensure_ascii=False)


def _blurb(deal: Deal) -> str:
    parts = []
    if deal.discount_pct:
        parts.append(f"currently {deal.discount_pct:.0f}% off")
    if deal.price and deal.price > 0 and deal.orig_price:
        parts.append(f"down to ${deal.price:,.2f} from ${deal.orig_price:,.2f}")
    where = f" at {deal.merchant}" if deal.merchant else ""
    lead = f"{deal.title}{where}"
    tail = (", ".join(parts)) if parts else "on sale now"
    local = " This is a local in-store deal." if deal.is_local else ""
    return f"{lead} is {tail}.{local} Prices change fast — check the retailer before buying."


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
{{CANONICAL}}{{ROBOTS}}
<meta property="og:type" content="product">
<meta property="og:title" content="{{OG_TITLE}}">
<meta property="og:description" content="{{DESCRIPTION}}">
{{OG_URL}}{{OG_IMAGE}}
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,800&family=Inter:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script type="application/ld+json">{{JSONLD}}</script>
<style>
  :root{--bg:#FAFAF6;--surface:#FFFFFF;--ink:#172420;--ink-soft:#5A6660;--line:#E8E7DE;
    --teal:#0E7C6B;--teal-ink:#0A5C4F;--marigold:#EFA015;--marigold-ink:#8A5B04;--marigold-tint:#FBEFD6;
    --display:'Bricolage Grotesque',system-ui,sans-serif;--body:'Inter',system-ui,sans-serif;--mono:'Space Mono',monospace}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.6}
  .wrap{max-width:680px;margin:0 auto;padding:0 22px}
  a{color:var(--teal-ink)}
  .ribbon{background:var(--ink);color:#EAF3EF;font-size:13px;text-align:center}
  .ribbon .wrap{padding:9px 22px}
  .crumb{font-family:var(--mono);font-size:12px;color:var(--ink-soft);padding:22px 0 0}
  .expired{background:var(--marigold-tint);color:var(--marigold-ink);border-radius:12px;
    padding:12px 16px;margin:16px 0 0;font-size:14px}
  h1{font-family:var(--display);font-weight:800;font-size:clamp(26px,5vw,40px);
    line-height:1.05;margin:14px 0 6px}
  .meta{font-family:var(--mono);font-size:12.5px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em}
  .pricebox{display:flex;gap:14px;align-items:baseline;margin:18px 0 4px;font-family:var(--mono)}
  .pricebox .now{font-size:30px;font-weight:700}
  .pricebox .was{font-size:16px;color:var(--ink-soft);text-decoration:line-through}
  .pricebox .save{font-size:14px;color:#fff;background:var(--marigold);color:var(--marigold-ink);
    padding:3px 9px;border-radius:999px;font-weight:700}
  .cta{display:inline-block;margin:18px 0 6px;background:var(--teal);color:#fff;font-weight:600;
    text-decoration:none;padding:14px 24px;border-radius:12px;font-size:16px}
  .cta:hover{background:var(--teal-ink)}
  p.blurb{font-size:16px;margin:14px 0}
  h2{font-family:var(--display);font-weight:800;font-size:19px;margin:34px 0 8px}
  .related{list-style:none;padding:0;margin:0}
  .related li{padding:9px 0;border-bottom:1px solid var(--line)}
  .related a{text-decoration:none;color:var(--ink);font-weight:500}
  footer{border-top:1px solid var(--line);margin-top:34px;padding:20px 0 44px;color:var(--ink-soft);font-size:12.5px}
</style>
</head>
<body>
  <div class="ribbon"><div class="wrap">Some links are affiliate links — we may earn a commission if you buy.</div></div>
  <div class="wrap">
    <div class="crumb"><a href="../../">&larr; All deals</a></div>
    {{EXPIRED}}
    <div class="meta">{{CATEGORY}}{{LOCAL}}</div>
    <h1>{{H1}}</h1>
    {{PRICEBOX}}
    <a class="{{CTA_CLASS}}" href="{{CTA_URL}}" target="_blank" rel="sponsored nofollow noopener"
       id="cta"{{CTA_DATA}}>{{CTA_LABEL}}</a>
    <p class="blurb">{{BLURB}}</p>
    {{RELATED}}
  </div>
  <footer><div class="wrap">
    As an Amazon Associate we earn from qualifying purchases. Prices retrieved {{RETRIEVED}} and may have changed.
    <a href="../../privacy.html">Privacy</a>.
  </div></footer>
  {{BEACON}}
  {{AUTO}}
</body>
</html>"""


def render_deal_page(deal: Deal, *, cfg: dict, base_url: str, cta_url: str,
                     related: list[tuple[str, str]] | None = None,
                     active: bool = True, beacon_url: str = "",
                     auto_scripts: str = "") -> str:
    base = (base_url or "").rstrip("/")
    canonical = f"{base}/{deal_path(deal)}" if base else ""
    title = f"{deal.title}"
    if deal.discount_pct:
        title += f" — {deal.discount_pct:.0f}% off"
    if deal.merchant:
        title += f" at {deal.merchant}"
    desc = _blurb(deal)[:300]

    # price box
    pricebox = ""
    if deal.price and deal.price > 0:
        was = (f'<span class="was">${deal.orig_price:,.2f}</span>'
               if deal.orig_price is not None else "")
        save = (f'<span class="save">{deal.discount_pct:.0f}% off</span>'
                if deal.discount_pct else "")
        pricebox = (f'<div class="pricebox"><span class="now">${deal.price:,.2f}</span>'
                    f'{was}{save}</div>')
    elif deal.discount_pct:
        pricebox = (f'<div class="pricebox"><span class="save">'
                    f'{deal.discount_pct:.0f}% off</span></div>')

    related_html = ""
    if related:
        items = "".join(f'<li><a href="{_html.escape(href, quote=True)}">'
                        f'{_html.escape(t)}</a></li>' for t, href in related)
        related_html = f'<h2>More deals like this</h2><ul class="related">{items}</ul>'

    expired_html = ("" if active else
                    '<div class="expired"><strong>This deal has expired.</strong> '
                    'It may no longer be available — see the current deals above.</div>')

    beacon = ""
    cta_data = ""
    if beacon_url and active:
        cta_data = (f' data-id="{short_id(deal)}" data-cat="{_html.escape(deal.category, quote=True)}"'
                    f' data-merchant="{_html.escape(deal.merchant, quote=True)}"')
        beacon = f"""<script>
    document.getElementById('cta').addEventListener('click',function(){{
      try{{var a=this;var p=JSON.stringify({{id:a.dataset.id,cat:a.dataset.cat,
        merchant:a.dataset.merchant,m:'dealpage',t:Date.now()}});
        navigator.sendBeacon({beacon_url!r},new Blob([p],{{type:'text/plain'}}));}}catch(e){{}}
    }});</script>"""

    subs = {
        "{{TITLE}}": _html.escape(title),
        "{{OG_TITLE}}": _html.escape(title),
        "{{DESCRIPTION}}": _html.escape(desc),
        "{{CANONICAL}}": f'<link rel="canonical" href="{_html.escape(canonical, quote=True)}">\n' if canonical else "",
        "{{ROBOTS}}": "" if active else '<meta name="robots" content="noindex">\n',
        "{{OG_URL}}": f'<meta property="og:url" content="{_html.escape(canonical, quote=True)}">\n' if canonical else "",
        "{{OG_IMAGE}}": (f'<meta property="og:image" content="{_html.escape(deal.image, quote=True)}">\n'
                         if deal.image else ""),
        "{{JSONLD}}": _jsonld(deal, canonical or f"/{deal_path(deal)}", active),
        "{{EXPIRED}}": expired_html,
        "{{CATEGORY}}": _html.escape(deal.category),
        "{{LOCAL}}": " · local in-store" if deal.is_local else "",
        "{{H1}}": _html.escape(deal.title),
        "{{PRICEBOX}}": pricebox,
        "{{CTA_URL}}": _html.escape(cta_url, quote=True),
        "{{CTA_CLASS}}": "cta noskimlinks" if deal.affiliate else "cta",
        "{{CTA_DATA}}": cta_data,
        "{{CTA_LABEL}}": "Get this deal &rarr;" if active else "Check current price &rarr;",
        "{{BLURB}}": _html.escape(_blurb(deal)),
        "{{RELATED}}": related_html,
        "{{RETRIEVED}}": f"{datetime.now(timezone.utc):%b %d, %Y}",
        "{{BEACON}}": beacon,
        "{{AUTO}}": auto_scripts,
    }
    page = _TEMPLATE
    for k, v in subs.items():
        page = page.replace(k, v)
    return page


def render_sitemap(entries: list[tuple[str, str]]) -> str:
    """entries: list of (absolute_loc, lastmod_date). Returns sitemap XML."""
    rows = "".join(
        f"  <url><loc>{_html.escape(loc)}</loc><lastmod>{lm}</lastmod></url>\n"
        for loc, lm in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{rows}</urlset>\n")


def render_robots(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    sm = f"Sitemap: {base}/sitemap.xml\n" if base else ""
    return ("User-agent: *\n"
            "Allow: /\n"
            "Disallow: /go/\n"          # don't crawl the redirect layer
            f"{sm}")
