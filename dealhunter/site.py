"""Render the digest as a standalone, hostable web page (GitHub Pages).

Unlike the email HTML (table-based, inline styles), this is a real responsive
web page with a live keyword filter. Affiliate compliance is built in:
  * a visible disclosure ribbon near the top, plus the exact Amazon Associate
    line and an FTC-style disclosure in the footer;
  * every outbound deal link carries rel="sponsored nofollow noopener" — the
    correct signal for paid/affiliate links — and target="_blank";
  * a "prices retrieved <time>" note, since prices change.

build_site(result, cfg, out_dir) writes out_dir/index.html.
"""
from __future__ import annotations

import html as _html
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import Deal
from .tracking import Tracker, short_id
from . import seo
from . import catalog
from . import monetization

AMAZON_ASSOCIATE_LINE = "As an Amazon Associate I earn from qualifying purchases."
GENERAL_DISCLOSURE = (
    "This page contains affiliate links. We may earn a commission when you buy "
    "through them, at no additional cost to you.")


# ── small helpers ────────────────────────────────────────────────────────────
def _badge(d: Deal) -> tuple[str, str]:
    """Return (big, small) badge text."""
    pct = d.discount_pct
    if pct is None:
        return "DEAL", ""
    if pct >= 100:
        return "FREE", ""
    return f"{pct:.0f}%", "off"


def _price_row(d: Deal) -> str:
    if d.price is None and d.orig_price is None:
        return ""
    now = f'<span class="now">${d.price:,.2f}</span>' if d.price is not None else ""
    was = (f'<span class="was">${d.orig_price:,.2f}</span>'
           if d.orig_price is not None else "")
    return f'<div class="deal__price">{now}{was}</div>'


def _card(d: Deal, tracker: Tracker, deal_page_base: str = "") -> str:
    big, small = _badge(d)
    kind = "ess" if d.is_essential else "disc"
    merchant = d.merchant or d.source.replace("-", " ").title()
    pin = ' <span class="pin" title="Local to you">local</span>' if d.is_local else ""
    small_html = f'<span class="tag__off">{small}</span>' if small else ""
    search = _html.escape((d.title + " " + merchant).lower(), quote=True)
    title = _html.escape(d.title)
    reg = f' data-region="{_html.escape(tracker.region, quote=True)}"' if tracker.region else ""
    if deal_page_base:
        # Link to the on-site deal page (indexable; keeps users on-site). The
        # affiliate click + logging happens on the deal page's CTA.
        href = _html.escape(f"{deal_page_base}/{seo.deal_path(d)}", quote=True)
        rel = ""
        label = "See deal"
        data = reg
    else:
        href = _html.escape(tracker.link(d), quote=True)
        rel = ' rel="sponsored nofollow noopener"'
        label = "View deal"
        redir = ' data-redirect="1"' if tracker.uses_redirect(d) else ""
        data = (f' data-id="{short_id(d)}" data-cat="{_html.escape(d.category, quote=True)}"'
                f' data-merchant="{_html.escape(merchant, quote=True)}"{reg}{redir}')
    aria = _html.escape(f"{label} for {d.title} at {merchant}", quote=True)
    target = "" if deal_page_base else ' target="_blank"'
    # Keep Skimlinks off links we already monetized (only the direct-merchant CTA).
    cta_cls = "deal__cta"
    if not deal_page_base and monetization.skim_exclude(d):
        cta_cls += " noskimlinks"
    return f"""
        <article class="deal deal--{kind}" data-search="{search}">
          <div class="tag tag--{kind}"><span class="tag__num">{big}</span>{small_html}</div>
          <div class="deal__body">
            <div class="deal__merchant">{_html.escape(merchant)}{pin}</div>
            <h3 class="deal__title">{title}</h3>
            {_price_row(d)}
            <a class="{cta_cls}" href="{href}"{target}{rel} aria-label="{aria}"{data}>{label}
              <span aria-hidden="true">→</span></a>
          </div>
        </article>"""


def _section(title: str, deals: list[Deal], kind: str, empty: str,
             tracker: Tracker, deal_page_base: str = "") -> str:
    cards = "".join(_card(d, tracker, deal_page_base) for d in deals)
    body = cards or f'<p class="empty">{empty}</p>'
    count = len(deals)
    return f"""
      <section class="board board--{kind}" data-section="{kind}">
        <header class="board__head">
          <h2 class="board__title">{title}</h2>
          <span class="board__count">{count}</span>
        </header>
        <div class="grid">{body}</div>
        <p class="empty empty--filter" hidden>No matches in this section.</p>
      </section>"""


# ── page template (tokens replaced, so CSS braces stay literal) ──────────────
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily Deals Board — {{LOCATION}}</title>
<meta name="description" content="The best essentials on sale and biggest discounts near {{LOCATION}} and nationwide, refreshed every morning.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Inter:wght@400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#FAFAF6; --surface:#FFFFFF; --ink:#172420; --ink-soft:#5A6660;
    --line:#E8E7DE; --teal:#0E7C6B; --teal-tint:#E7F2EF; --teal-ink:#0A5C4F;
    --marigold:#EFA015; --marigold-tint:#FBEFD6; --marigold-ink:#8A5B04;
    --display:'Bricolage Grotesque',system-ui,sans-serif;
    --body:'Inter',system-ui,sans-serif; --mono:'Space Mono',ui-monospace,monospace;
    --shadow:0 1px 0 var(--line),0 8px 24px -18px rgba(23,36,32,.5);
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);
       line-height:1.5;-webkit-font-smoothing:antialiased}
  a{color:inherit}
  .wrap{max-width:1080px;margin:0 auto;padding:0 20px}

  /* disclosure ribbon */
  .ribbon{background:var(--ink);color:#EAF3EF;font-size:13px;letter-spacing:.02em}
  .ribbon .wrap{padding:9px 20px;display:flex;gap:8px;align-items:center;justify-content:center;text-align:center}
  .ribbon strong{color:#fff}

  /* hero */
  .hero{padding:44px 0 30px;border-bottom:1px solid var(--line)}
  .regionnav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px;align-items:center}
  .regionnav__label{font-family:var(--mono);font-size:11px;letter-spacing:.12em;
    text-transform:uppercase;color:var(--ink-soft);margin-right:4px}
  .regionnav a{font-family:var(--mono);font-size:12.5px;text-decoration:none;
    padding:6px 11px;border-radius:999px;border:1.5px solid var(--line);
    background:var(--surface);color:var(--ink)}
  .regionnav a[aria-current=page]{background:var(--teal);border-color:var(--teal);color:#fff}
  .regionnav a:hover{border-color:var(--teal)}
  .eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.18em;
           text-transform:uppercase;color:var(--teal-ink)}
  .hero h1{font-family:var(--display);font-weight:800;font-size:clamp(40px,8vw,74px);
           line-height:.95;letter-spacing:-.02em;margin:.18em 0 .1em}
  .hero .date{font-family:var(--mono);font-size:15px;color:var(--ink-soft)}
  .hero .lede{max-width:52ch;margin:14px 0 0;color:var(--ink-soft);font-size:16px}

  .controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:24px}
  .search{flex:1 1 260px;position:relative}
  .search input{width:100%;font-family:var(--body);font-size:16px;color:var(--ink);
    padding:13px 16px 13px 42px;border:1.5px solid var(--line);border-radius:12px;
    background:var(--surface);transition:border-color .15s,box-shadow .15s}
  .search input:focus{outline:none;border-color:var(--teal);
    box-shadow:0 0 0 4px var(--teal-tint)}
  .search svg{position:absolute;left:14px;top:50%;transform:translateY(-50%);
    width:18px;height:18px;color:var(--ink-soft)}
  .chips{display:flex;gap:8px;flex-wrap:wrap}
  .chip{font-family:var(--mono);font-size:12.5px;padding:8px 12px;border-radius:999px;
        border:1.5px solid var(--line);background:var(--surface);white-space:nowrap}
  .chip b{color:var(--teal-ink)}
  .chip.disc b{color:var(--marigold-ink)}

  /* board sections */
  main{padding:14px 0 40px}
  .board{padding:34px 0 8px}
  .board__head{display:flex;align-items:baseline;gap:12px;margin-bottom:18px}
  .board__title{font-family:var(--display);font-weight:800;font-size:24px;margin:0;
    letter-spacing:-.01em}
  .board__count{font-family:var(--mono);font-size:13px;color:#fff;padding:3px 10px;
    border-radius:999px}
  .board--ess .board__count{background:var(--teal)}
  .board--disc .board__count{background:var(--marigold);color:var(--marigold-ink)}

  /* receipt-perforation divider */
  .perf{height:14px;background:
    radial-gradient(circle at 7px 50%, transparent 0 5px, var(--bg) 5px) repeat-x;
    background-size:14px 14px;border-top:2px dashed var(--line);margin:8px 0 0}

  .grid{display:grid;gap:16px;
    grid-template-columns:repeat(auto-fill,minmax(min(100%,278px),1fr))}

  .deal{position:relative;background:var(--surface);border:1.5px solid var(--line);
    border-radius:16px;padding:18px;display:flex;gap:14px;box-shadow:var(--shadow);
    transition:transform .18s ease,box-shadow .18s ease}
  .deal:hover{transform:translateY(-3px);
    box-shadow:0 1px 0 var(--line),0 22px 34px -22px rgba(23,36,32,.55)}
  .deal.is-hidden{display:none}

  /* the signature: a punched price-tag badge */
  .tag{flex:0 0 auto;width:62px;height:62px;border-radius:12px;display:flex;
    flex-direction:column;align-items:center;justify-content:center;
    transform:rotate(-4deg);font-family:var(--mono);line-height:1}
  .tag::before{content:"";position:absolute;width:7px;height:7px;border-radius:50%;
    background:var(--bg);border:1.5px solid currentColor;margin-top:-40px;opacity:.55}
  .tag--ess{background:var(--teal-tint);color:var(--teal-ink)}
  .tag--disc{background:var(--marigold-tint);color:var(--marigold-ink)}
  .tag__num{font-weight:700;font-size:19px}
  .tag__off{font-size:10px;text-transform:uppercase;letter-spacing:.1em;opacity:.8}

  .deal__body{min-width:0;display:flex;flex-direction:column;gap:6px;flex:1}
  .deal__merchant{font-family:var(--mono);font-size:11.5px;letter-spacing:.04em;
    text-transform:uppercase;color:var(--ink-soft)}
  .pin{color:var(--teal-ink);background:var(--teal-tint);padding:1px 6px;
    border-radius:5px;font-size:10px}
  .deal__title{font-size:15.5px;font-weight:600;margin:0;line-height:1.32;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .deal__price{font-family:var(--mono);display:flex;gap:8px;align-items:baseline}
  .deal__price .now{font-weight:700;font-size:16px}
  .deal__price .was{color:var(--ink-soft);text-decoration:line-through;font-size:13px}
  .deal__cta{margin-top:auto;align-self:flex-start;font-weight:600;font-size:14px;
    text-decoration:none;color:var(--teal-ink);padding-top:4px}
  .deal--disc .deal__cta{color:var(--marigold-ink)}
  .deal__cta:hover span{margin-left:3px}
  .deal__cta span{transition:margin-left .15s}
  .deal__cta:focus-visible,.search input:focus-visible{outline:2px solid var(--teal);
    outline-offset:2px}

  .empty{color:var(--ink-soft);font-size:15px;padding:6px 0 10px}

  /* signup band */
  .signup{background:var(--teal);color:#fff}
  .signup .wrap{padding:26px 20px;display:flex;flex-wrap:wrap;gap:16px 28px;
    align-items:center;justify-content:space-between}
  .signup__copy{max-width:44ch}
  .signup__copy h2{font-family:var(--display);font-weight:800;font-size:22px;margin:0 0 4px}
  .signup__copy p{margin:0;font-size:14px;color:#DCEFEA}
  .signup form{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .signup input[type=email]{font-family:var(--body);font-size:15px;padding:12px 14px;
    border:0;border-radius:10px;min-width:220px}
  .signup input[type=email]:focus-visible{outline:3px solid #073F36;outline-offset:2px}
  .signup button{font-family:var(--body);font-weight:600;font-size:15px;color:var(--teal-ink);
    background:#fff;border:0;border-radius:10px;padding:12px 18px;cursor:pointer;
    transition:transform .12s}
  .signup button:hover{transform:translateY(-1px)}
  .signup button:disabled{opacity:.6;cursor:default;transform:none}
  .signup__msg{font-size:13px;color:#EAF7F3;min-height:1em;width:100%}
  .signup__fine{font-size:11px;color:#BFE0D8;margin-top:6px}
  .signup__fine a{color:#fff}
  .hp{position:absolute;left:-9999px}

  /* footer */
  footer{border-top:1px solid var(--line);background:var(--surface);margin-top:20px}
  footer .wrap{padding:28px 20px 40px}
  .disc{font-size:13px;color:var(--ink-soft);max-width:70ch;line-height:1.6}
  .disc b{color:var(--ink)}
  .made{font-family:var(--mono);font-size:12px;color:var(--ink-soft);margin-top:14px}

  /* entrance animation */
  @media (prefers-reduced-motion:no-preference){
    .deal{animation:rise .5s cubic-bezier(.2,.7,.2,1) both}
    @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
  }
</style>
</head>
<body>
  <div class="ribbon"><div class="wrap">
    <span><strong>Heads up:</strong> some links are affiliate links — we may earn a commission if you buy.</span>
  </div></div>

  <header class="hero"><div class="wrap">
    {{REGION_NAV}}
    <div class="eyebrow">{{LOCATION_UPPER}} · &amp; nationwide</div>
    <h1>Today&rsquo;s Deals Board</h1>
    <div class="date">{{DATE}} · updated {{RETRIEVED}}</div>
    <p class="lede">The best essentials on sale and the biggest discounts we could
      find, gathered fresh every morning. Tap a deal to go straight to the store.</p>
    <div class="controls">
      <div class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
        <label for="q" class="sr-only" style="position:absolute;left:-9999px">Search deals</label>
        <input id="q" type="search" placeholder="Search deals (e.g. coffee, diapers)&hellip;"
               autocomplete="off">
      </div>
      <div class="chips">
        <span class="chip ess"><b>{{N_ESSENTIALS}}</b> essentials</span>
        <span class="chip disc"><b>{{N_DISCOUNTS}}</b> big discounts</span>
      </div>
    </div>
  </div></header>

  {{SIGNUP_BAND}}

  <main><div class="wrap">
    {{ESSENTIALS_SECTION}}
    <div class="perf" aria-hidden="true"></div>
    {{DISCOUNTS_SECTION}}
    <p class="empty" id="no-results" hidden>Nothing matches that search. Try another word.</p>
  </div></main>

  <footer><div class="wrap">
    <p class="disc"><b>Disclosure.</b> {{GENERAL_DISCLOSURE}} {{AMAZON_LINE}}
      Prices were retrieved {{RETRIEVED}} and may have changed — always confirm the
      current price on the retailer&rsquo;s site before buying.</p>
    <p class="made">Deals Board · {{LOCATION}} &amp; national · generated by DealHunter · {{YEAR}}</p>
  </div></footer>

  <script>
    (function(){
      var q=document.getElementById('q');
      var cards=[].slice.call(document.querySelectorAll('.deal'));
      var sections=[].slice.call(document.querySelectorAll('.board'));
      var noResults=document.getElementById('no-results');
      if(!q)return;
      q.addEventListener('input',function(){
        var term=q.value.trim().toLowerCase();
        var anyVisible=false;
        cards.forEach(function(c){
          var hit=!term||c.getAttribute('data-search').indexOf(term)>-1;
          c.classList.toggle('is-hidden',!hit);
          if(hit)anyVisible=true;
        });
        sections.forEach(function(s){
          var visible=s.querySelectorAll('.deal:not(.is-hidden)').length;
          var note=s.querySelector('.empty--filter');
          if(note)note.hidden=!(term&&visible===0);
        });
        noResults.hidden=anyVisible;
      });
    })();
  </script>
  {{BEACON_SCRIPT}}
  {{AUTO_SCRIPTS}}
</body>
</html>"""


def _beacon_script(beacon_url: str, only_if_no_redirect: bool) -> str:
    """Board-level click logger. Fires a text/plain beacon (no CORS preflight)
    then lets the link navigate normally. Only attaches to direct links so we
    never double-count clicks that already go through a logged redirect page.
    """
    if not beacon_url:
        return ""
    guard = "if(a.dataset.redirect==='1')return;" if only_if_no_redirect else ""
    return f"""<script>
    (function(){{
      var B={beacon_url!r};
      document.querySelectorAll('.deal__cta[data-id]').forEach(function(a){{
        a.addEventListener('click',function(){{
          {guard}
          try{{
            var p=JSON.stringify({{id:a.dataset.id,cat:a.dataset.cat,
              merchant:a.dataset.merchant,region:a.dataset.region||'',
              m:'web',t:Date.now()}});
            navigator.sendBeacon(B,new Blob([p],{{type:'text/plain'}}));
          }}catch(e){{}}
        }});
      }});
    }})();
  </script>"""


def _region_nav(nav: list[dict] | None) -> str:
    """Horizontal region switcher. nav items: {label, href, active}."""
    if not nav or len(nav) < 2:
        return ""
    links = []
    for n in nav:
        cur = ' aria-current="page"' if n.get("active") else ""
        links.append(f'<a href="{_html.escape(n["href"], quote=True)}"{cur}>'
                     f'{_html.escape(n["label"])}</a>')
    return ('<nav class="regionnav" aria-label="Choose your area">'
            '<span class="regionnav__label">Your area</span>'
            + "".join(links) + "</nav>")


def _signup_band(endpoint: str, privacy_url: str, region: str = "") -> str:
    """A single-opt-in email capture band. Posts the address to your Worker,
    which adds it to your Resend list (keeping the API key server-side).
    """
    if not endpoint:
        return ""
    ep = _html.escape(endpoint, quote=True)
    priv = _html.escape(privacy_url or "privacy.html", quote=True)
    return f"""
  <section class="signup" aria-labelledby="signup-h">
    <div class="wrap">
      <div class="signup__copy">
        <h2 id="signup-h">Get the deals in your inbox</h2>
        <p>One short email each morning — the day&rsquo;s best essentials and
           biggest discounts. No spam, unsubscribe anytime.</p>
      </div>
      <form id="signup-form" novalidate>
        <label for="email" class="hp-label" style="position:absolute;left:-9999px">Email</label>
        <input id="email" name="email" type="email" required
               placeholder="you@email.com" autocomplete="email">
        <input class="hp" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
        <button type="submit" id="signup-btn">Subscribe</button>
        <div class="signup__msg" id="signup-msg" role="status" aria-live="polite"></div>
        <div class="signup__fine">By subscribing you agree to receive our daily
          email. See our <a href="{priv}">privacy policy</a>.</div>
      </form>
    </div>
    <script>
      (function(){{
        var f=document.getElementById('signup-form');
        var msg=document.getElementById('signup-msg');
        var btn=document.getElementById('signup-btn');
        if(!f)return;
        f.addEventListener('submit',function(e){{
          e.preventDefault();
          var email=f.email.value.trim();
          if(f.website.value){{return;}}            /* honeypot: silently drop bots */
          if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email)){{
            msg.textContent='Please enter a valid email.';return;}}
          btn.disabled=true;msg.textContent='Subscribing…';
          fetch({endpoint!r},{{method:'POST',headers:{{'Content-Type':'text/plain'}},
            body:JSON.stringify({{email:email,region:{region!r}}})}})
          .then(function(r){{if(!r.ok)throw 0;
            msg.textContent='You\\u2019re in! Check your inbox tomorrow morning.';
            f.email.value='';}})
          .catch(function(){{msg.textContent='Something went wrong — try again in a moment.';}})
          .finally(function(){{btn.disabled=false;}});
        }});
      }})();
    </script>
  </section>"""


def render_page(deals: Sequence[Deal], location_label: str = "Willoughby, OH",
                affiliate_enabled: bool = True, tracker: Tracker | None = None,
                signup_endpoint: str = "", privacy_url: str = "",
                regions_nav: list[dict] | None = None,
                deal_page_base: str = "", auto_scripts: str = "") -> str:
    tracker = tracker or Tracker(None, "web")
    essentials = sorted((d for d in deals if d.is_essential),
                        key=lambda d: d.score, reverse=True)
    big = sorted((d for d in deals if not d.is_essential),
                 key=lambda d: d.score, reverse=True)

    ess_html = _section("🧺 Essentials on sale", essentials, "ess",
                        "No essential deals today — check back tomorrow morning.",
                        tracker, deal_page_base)
    disc_html = _section("🔥 Biggest discounts", big, "disc",
                         "No big discounts cleared today — check back tomorrow.",
                         tracker, deal_page_base)

    # Board beacon logs direct affiliate clicks. When cards link to on-site deal
    # pages instead, those pages carry the CTA beacon, so skip it here.
    beacon = ("" if deal_page_base else
              (_beacon_script(tracker.beacon_url, only_if_no_redirect=True)
               if tracker.beacon_url else ""))

    amazon_line = AMAZON_ASSOCIATE_LINE if affiliate_enabled else ""
    general = GENERAL_DISCLOSURE if affiliate_enabled else (
        "Links go directly to each retailer.")

    subs = {
        "{{LOCATION}}": _html.escape(location_label),
        "{{LOCATION_UPPER}}": _html.escape(location_label.upper()),
        "{{DATE}}": f"{date.today():%A, %B %d, %Y}",
        "{{RETRIEVED}}": f"{datetime.now(timezone.utc):%H:%M UTC}",
        "{{N_ESSENTIALS}}": str(len(essentials)),
        "{{N_DISCOUNTS}}": str(len(big)),
        "{{ESSENTIALS_SECTION}}": ess_html,
        "{{DISCOUNTS_SECTION}}": disc_html,
        "{{GENERAL_DISCLOSURE}}": _html.escape(general),
        "{{AMAZON_LINE}}": _html.escape(amazon_line),
        "{{YEAR}}": str(date.today().year),
        "{{BEACON_SCRIPT}}": beacon,
        "{{SIGNUP_BAND}}": _signup_band(signup_endpoint, privacy_url, tracker.region),
        "{{REGION_NAV}}": _region_nav(regions_nav),
        "{{AUTO_SCRIPTS}}": auto_scripts,
    }
    page = _TEMPLATE
    for k, v in subs.items():
        page = page.replace(k, v)
    return page


def _redirect_page(dest: str, merchant: str, beacon_url: str,
                   meta: dict) -> str:
    """A transparent, logged redirect page (non-Amazon links).

    Fires a beacon (if configured), then forwards to the real destination.
    Shows the destination so it never 'obscures' where the visitor is going.
    """
    dest_e = _html.escape(dest, quote=True)
    merch_e = _html.escape(merchant)
    beacon_js = ""
    if beacon_url:
        payload = ('{"id":"%s","cat":"%s","merchant":"%s","region":"%s","m":"redirect","t":"+Date.now()+"}'
                   % (meta.get("id", ""), _html.escape(meta.get("category", ""), quote=True),
                      merch_e, _html.escape(meta.get("region", ""), quote=True)))
        beacon_js = f"""try{{navigator.sendBeacon({beacon_url!r},
      new Blob(['{payload}'],{{type:'text/plain'}}));}}catch(e){{}}"""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Continue to {merch_e}…</title>
<meta http-equiv="refresh" content="1;url={dest_e}">
<style>body{{font-family:system-ui,sans-serif;background:#FAFAF6;color:#172420;
display:grid;place-content:center;min-height:80vh;text-align:center;gap:10px;padding:24px}}
a{{color:#0A5C4F}}</style></head>
<body>
  <p>Taking you to <strong>{merch_e}</strong>…</p>
  <p><a href="{dest_e}" rel="sponsored nofollow noopener">Continue &rarr;</a></p>
  <script>{beacon_js}location.replace({dest_e!r});</script>
</body></html>"""


def _copy_assets(cfg: dict, out: Path) -> list[str]:
    """Copy site_assets/* into the output, filling simple {{TOKENS}} in text
    files from config (business name, contact, address, location). Legal blanks
    marked [REVIEW: …] are left for you to complete.
    """
    site_cfg = cfg.get("site", {})
    assets = Path(site_cfg.get("assets_dir", "site_assets"))
    if not assets.is_dir():
        return []
    tokens = {
        "{{BUSINESS_NAME}}": site_cfg.get("business_name", "Deals Board"),
        "{{CONTACT_EMAIL}}": site_cfg.get("contact_email",
                                          "[REVIEW: your contact email]"),
        "{{MAILING_ADDRESS}}": (cfg.get("list", {}).get("sender_address")
                                or "[REVIEW: your mailing address]"),
        "{{LOCATION}}": (cfg.get("location") or {}).get("label", "Willoughby, OH"),
    }
    copied = []
    for f in assets.rglob("*"):
        if not f.is_file():
            continue
        dest = out / f.relative_to(assets)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix.lower() in (".html", ".htm", ".txt", ".xml", ".css", ".webmanifest"):
            text = f.read_text(encoding="utf-8")
            for k, v in tokens.items():
                text = text.replace(k, _html.escape(v))
            dest.write_text(text, encoding="utf-8")
        else:
            dest.write_bytes(f.read_bytes())
        copied.append(str(dest.relative_to(out)))
    return copied


def _render_landing(regions: list[dict], cfg: dict, auto_scripts: str = "") -> str:
    """Root page that lets visitors pick their area (multi-region only)."""
    business = cfg.get("site", {}).get("business_name", "Deals Board")
    cards = []
    for r in regions:
        href = _html.escape(f"{r['path']}/", quote=True)
        label = _html.escape(r["label"])
        n = len(r.get("deals", []))
        cards.append(
            f'<a class="rcard" href="{href}"><span class="rcard__name">{label}</span>'
            f'<span class="rcard__meta">{n} deals today &rarr;</span></a>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(business)} — choose your area</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,800&family=Inter:wght@400;500;600&family=Space+Mono&display=swap" rel="stylesheet">
<style>
  :root{{--bg:#FAFAF6;--surface:#FFFFFF;--ink:#172420;--ink-soft:#5A6660;
    --line:#E8E7DE;--teal:#0E7C6B;--teal-ink:#0A5C4F}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font-family:'Inter',system-ui,sans-serif;line-height:1.5}}
  .wrap{{max-width:760px;margin:0 auto;padding:60px 22px 70px}}
  .eyebrow{{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.18em;
    text-transform:uppercase;color:var(--teal-ink)}}
  h1{{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;
    font-size:clamp(34px,7vw,58px);line-height:1;margin:.2em 0 .3em}}
  .lede{{color:var(--ink-soft);max-width:52ch;margin:0 0 28px}}
  .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr))}}
  .rcard{{display:flex;flex-direction:column;gap:6px;padding:20px;border-radius:16px;
    background:var(--surface);border:1.5px solid var(--line);text-decoration:none;
    color:var(--ink);transition:transform .16s,border-color .16s}}
  .rcard:hover{{transform:translateY(-3px);border-color:var(--teal)}}
  .rcard__name{{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:20px}}
  .rcard__meta{{font-family:'Space Mono',monospace;font-size:12.5px;color:var(--teal-ink)}}
  footer{{margin-top:40px;color:var(--ink-soft);font-size:13px}}
</style></head>
<body><div class="wrap">
  <div class="eyebrow">{_html.escape(business)}</div>
  <h1>Choose your area</h1>
  <p class="lede">Local essentials on sale and the biggest national discounts,
    refreshed every morning. Pick where you shop.</p>
  <div class="grid">{"".join(cards)}</div>
  <footer><a href="privacy.html" style="color:var(--teal-ink)">Privacy policy</a></footer>
</div>{auto_scripts}</body></html>"""


def build_site(result: dict, cfg: dict, out_dir: str = "site") -> str:
    """Write region page(s), logged-redirect pages, a landing page (when there's
    more than one region), and static assets to out_dir.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / ".nojekyll").write_text("")  # serve files as-is on GitHub Pages

    # Regions: use the pipeline's per-region results, or synthesize one.
    regions = result.get("regions") or [{
        "id": "home", "label": (cfg.get("location") or {}).get("label", "Deals Board"),
        "deals": result["deals"],
    }]
    multi = len(regions) > 1
    for r in regions:
        r["path"] = r["id"] if multi else ""   # single region lives at root

    affiliate_enabled = bool(cfg.get("affiliate", {}).get("enabled"))
    tcfg = cfg.get("tracking")
    list_cfg = cfg.get("list", {})
    base_signup = list_cfg.get("signup_endpoint", "") if list_cfg.get("enabled") else ""
    base_privacy = list_cfg.get("privacy_url", "privacy.html")

    # When SEO pages are on (and a base_url is known), board cards link to the
    # on-site deal pages instead of straight to the merchant.
    seo_cfg = cfg.get("seo", {})
    seo_base = (cfg.get("site", {}).get("base_url")
                or (tcfg or {}).get("site_base_url", "")).rstrip("/")
    deal_page_base = seo_base if (seo_cfg.get("enabled") and seo_base
                                  and seo_cfg.get("link_cards_to_pages", True)) else ""
    auto = monetization.auto_scripts(cfg)

    for r in regions:
        path = r["path"]
        rout = out / path if path else out
        rout.mkdir(parents=True, exist_ok=True)
        # From a region subfolder, privacy + nav links go up one level.
        up = "../" if path else ""
        privacy_url = (up + base_privacy) if base_privacy else base_privacy
        nav = [{"label": o["label"], "href": (f"{up}{o['path']}/" if o["path"] else up or "./"),
                "active": o["id"] == r["id"]} for o in regions] if multi else None

        tracker = Tracker(tcfg, medium="web", region=r["id"])
        html = render_page(r["deals"], r["label"], affiliate_enabled, tracker,
                           base_signup, privacy_url, regions_nav=nav,
                           deal_page_base=deal_page_base, auto_scripts=auto)
        (rout / "index.html").write_text(html, encoding="utf-8")

        # Redirect pages are only needed for direct affiliate board links.
        if not deal_page_base:
            for rid, info in tracker.redirect_map(r["deals"]).items():
                d = rout / "go" / rid
                d.mkdir(parents=True, exist_ok=True)
                (d / "index.html").write_text(
                    _redirect_page(info["dest"], info["merchant"], tracker.beacon_url,
                                   {"id": rid, "category": info["category"], "region": r["id"]}),
                    encoding="utf-8")

    if multi:
        (out / "index.html").write_text(_render_landing(regions, cfg, auto),
                                         encoding="utf-8")

    _copy_assets(cfg, out)

    _build_seo(result, cfg, out, regions, multi, auto)

    root_page = regions[0]["path"]
    return str(out / (root_page + "/index.html" if root_page and not multi else "index.html"))


def _build_seo(result: dict, cfg: dict, out: Path, regions: list[dict],
               multi: bool, auto_scripts: str = ""):
    """Generate per-deal SEO pages + sitemap.xml + robots.txt (opt-in).

    Pages accumulate: today's deals render active; previously-seen deals still in
    the catalog render in a noindex 'expired' state so their URLs stay live (200)
    instead of 404-ing. Only active pages go in the sitemap.
    """
    seo_cfg = cfg.get("seo", {})
    if not seo_cfg.get("enabled"):
        return
    base_url = (cfg.get("site", {}).get("base_url")
                or cfg.get("tracking", {}).get("site_base_url", "")).rstrip("/")
    tcfg = cfg.get("tracking")
    tracker = Tracker(tcfg, medium="web", region="seo")
    max_pages = int(seo_cfg.get("max_pages", 2000))

    # Today's deals, de-duped across regions (national deals appear in several).
    active_by_slug: dict[str, Deal] = {}
    for r in regions:
        for d in r["deals"]:
            active_by_slug.setdefault(seo.deal_slug(d), d)

    # Durable catalog: load, upsert today's, prune, save.
    today = f"{date.today():%Y-%m-%d}"
    cat_path = seo_cfg.get("catalog_file", "data/catalog.ndjson")
    retention = int(seo_cfg.get("retention_days", 45))
    cat = catalog.load(cat_path)
    cat, active_slugs = catalog.update(cat, active_by_slug.values(), today)
    cat = catalog.prune(cat, today, retention)
    catalog.save(cat_path, cat)

    # Order: active first, then most-recently-seen expired; cap at max_pages.
    records = sorted(cat.values(),
                     key=lambda r: (r["slug"] in active_slugs, r.get("last_seen", "")),
                     reverse=True)[:max_pages]

    # Related links only ever point at ACTIVE deals (never dead ends).
    active_records = [r for r in records if r["slug"] in active_slugs]

    entries: list[tuple[str, str]] = []
    if base_url:
        entries.append((base_url + "/", today))
        for r in regions:
            entries.append((f"{base_url}/{r['path']}/" if r["path"] else base_url + "/", today))

    for rec in records:
        slug = rec["slug"]
        is_active = slug in active_slugs
        deal = active_by_slug[slug] if is_active else catalog.deal_from_record(rec)

        picks = [x for x in active_records if x["slug"] != slug]
        same = [x for x in picks if x.get("category") == rec.get("category")]
        picks = (same + [x for x in picks if x not in same])[:4]
        related = [(x["title"], f"../{x['slug']}/") for x in picks]

        cta = tracker.destination(deal) if is_active else deal.url
        page = seo.render_deal_page(
            deal, cfg=cfg, base_url=base_url, cta_url=cta,
            related=related, active=is_active, beacon_url=tracker.beacon_url,
            auto_scripts=auto_scripts)
        dpath = out / "deal" / slug
        dpath.mkdir(parents=True, exist_ok=True)
        (dpath / "index.html").write_text(page, encoding="utf-8")

        if base_url and is_active:            # only live deals in the sitemap
            entries.append((f"{base_url}/deal/{slug}/", today))

    if base_url:
        # De-dupe (the root region and landing can share base_url + "/").
        seen = set()
        entries = [(loc, lm) for loc, lm in entries
                   if not (loc in seen or seen.add(loc))]
        (out / "sitemap.xml").write_text(seo.render_sitemap(entries), encoding="utf-8")
        (out / "robots.txt").write_text(seo.render_robots(base_url), encoding="utf-8")
