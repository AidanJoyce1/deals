"""Monetize deal links: inject affiliate tags / deeplinks.

Two mechanisms, applied in order:

1. Amazon Associates tag injection. Join at https://affiliate-program.amazon.com
   (free), get your Store/Tracking ID like "yourname-20", set it as
   affiliate.amazon_tag in config. We add ?tag=... to genuine amazon.com URLs.
   No URL cloaking/redirects (Amazon prohibits them).

2. Generic deeplink rules for other networks (CJ, Rakuten, Awin, Impact, etc.).
   Each rule matches a substring of the destination host/url and wraps it with
   a template you paste from your network's link generator, e.g.:
       - match: "walmart.com"
         template: "https://goto.walmart.com/c/XXXX/9383/1234?u={url}"
   {url} = URL-encoded destination, {raw} = destination as-is.

IMPORTANT COMPLIANCE NOTES (enforced/aided elsewhere in the app):
  * You earn on OTHER people's purchases, not your own — self-referral is
    disqualified. Monetization only pays once you distribute to an audience.
  * Amazon links in email are only permitted to opted-in recipients.
  * A disclosure ("As an Amazon Associate…") is added to every digest, and a
    "prices retrieved <time>" note is included, per Amazon/FTC rules.
"""
from __future__ import annotations

from urllib.parse import (parse_qsl, quote, urlencode, urlsplit, urlunsplit)

from .models import Deal

DISCLOSURE = ("Some links are affiliate links: as an Amazon Associate and via "
              "partner programs, the publisher may earn from qualifying "
              "purchases at no extra cost to you.")


def _is_amazon(host: str) -> bool:
    host = host.lower()
    return "amazon." in host or host.endswith("amzn.to") or host == "amzn.com"


def apply_amazon_tag(url: str, tag: str) -> str | None:
    """Return url with ?tag=<tag> if it's a real Amazon URL, else None.

    amzn.to short links can't be safely tagged without expanding them, so we
    leave those untouched (return None) rather than produce a broken link.
    """
    parts = urlsplit(url)
    if not _is_amazon(parts.netloc):
        return None
    if parts.netloc.lower().endswith("amzn.to"):
        return None  # short link — skip
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q["tag"] = tag
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(q, doseq=True), parts.fragment))


def apply_deeplink(url: str, rules: list[dict]) -> str | None:
    """Apply the first matching network deeplink rule, else None."""
    for rule in rules or []:
        match = rule.get("match", "")
        if match and match in url:
            tmpl = rule["template"]
            return tmpl.replace("{url}", quote(url, safe="")).replace("{raw}", url)
    return None


def monetize(deal: Deal, cfg: dict) -> Deal:
    """Rewrite deal.url with affiliate tracking based on config. Idempotent."""
    if not cfg or not cfg.get("enabled"):
        return deal
    if deal.affiliate:
        return deal  # already commission-tracked (e.g. from an affiliate feed)

    tag = cfg.get("amazon_tag")
    if tag:
        new = apply_amazon_tag(deal.url, tag)
        if new:
            deal.url, deal.affiliate = new, True
            return deal

    new = apply_deeplink(deal.url, cfg.get("deeplink_rules"))
    if new:
        deal.url, deal.affiliate = new, True
    return deal
