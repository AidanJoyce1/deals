"""Client-side auto-monetization snippets: Skimlinks/Sovrn + Amazon OneLink.

These run in the browser on the public web pages (never in email — clients
don't execute JS):

  * Skimlinks/Sovrn: a catch-all that turns *unaffiliated* merchant links into
    commission links across ~48k merchants, with no per-network setup. We tag
    links we've ALREADY monetized server-side with class="noskimlinks" so
    Skimlinks won't override our own Amazon tag / network deep links — it only
    earns on the long tail we didn't cover.
  * Amazon OneLink (oneTag): geo-redirects international Amazon clicks to their
    local marketplace with your linked tags, so you earn on non-US shoppers.
    Complements (doesn't conflict with) the Amazon tags we already inject.

Config (all optional; a snippet is emitted only when enabled AND its id is set):

  automonetize:
    skimlinks: {enabled: true, publisher_id: "12345X1234567"}
    onelink:   {enabled: true, instance_id: "xxxxxxxx-....", marketplace: "US"}
"""
from __future__ import annotations

from .models import Deal


def skimlinks_snippet(publisher_id: str) -> str:
    if not publisher_id:
        return ""
    return ('<script type="text/javascript" async '
            f'src="https://s.skimresources.com/js/{publisher_id}.skimlinks.js"></script>')


def onelink_snippet(instance_id: str, marketplace: str = "US") -> str:
    if not instance_id:
        return ""
    # &amp; keeps the attribute valid HTML.
    return (f'<div id="amzn-assoc-ad-{instance_id}"></div>'
            '<script async src="https://z-na.amazon-adsystem.com/widgets/onejs'
            f'?MarketPlace={marketplace}&amp;adInstanceId={instance_id}"></script>')


def auto_scripts(cfg: dict) -> str:
    """Concatenated snippet HTML to inject before </body> on public pages."""
    a = cfg.get("automonetize", {}) or {}
    out = []
    sk = a.get("skimlinks", {}) or {}
    if sk.get("enabled") and sk.get("publisher_id"):
        out.append(skimlinks_snippet(sk["publisher_id"]))
    ol = a.get("onelink", {}) or {}
    if ol.get("enabled") and ol.get("instance_id"):
        out.append(onelink_snippet(ol["instance_id"], ol.get("marketplace", "US")))
    return "\n".join(out)


def skim_exclude(deal: Deal) -> str:
    """Class to keep Skimlinks off links we've already monetized ourselves."""
    return "noskimlinks" if getattr(deal, "affiliate", False) else ""
