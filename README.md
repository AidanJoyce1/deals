# 🛒 DealHunter

A daily deals + essentials aggregator. Pulls deals from feeds and APIs, scores
them by discount size and whether they're a household **essential**, filters to
what matters (big discounts **or** essentials on sale), de-dupes across runs,
and prints a ranked daily digest. Tuned out of the box for **Willoughby, OH**.

## Quick start

> **Deploying for real?** Follow **[DEPLOY.md](DEPLOY.md)** — a step-by-step
> deploy + marketing playbook with a 4-week launch plan.


```bash
pip install -r requirements.txt
python cli.py config.yaml                 # prints today's digest
python cli.py config.yaml --out today.md  # save Markdown to a file
python cli.py config.yaml --email         # email the digest (see below)
```

Runs with zero API keys using the RSS feeds in `config.yaml`. Add the Kroger API
(free) to unlock local grocery/essentials pricing.

## 📧 Email the digest to yourself (simplified)

The simple path uses **Resend** — one API key, no app passwords:

1. Sign up at <https://resend.com>, create an API key.
2. `export RESEND_API_KEY="re_xxxxxxxx"`
3. Set `email.to` in `config.yaml`. Leave `email.from` as `onboarding@resend.dev`
   to start (delivers to your signup address); verify a domain later for a
   custom From.
4. Send it: `python cli.py config.yaml --email`

That's it. The sender **auto-detects** your setup: if `RESEND_API_KEY` is set it
uses Resend; otherwise it falls back to Gmail/SMTP (`SMTP_USER` + `SMTP_PASSWORD`,
where Gmail needs an App Password). You only ever configure one.

## ⏰ Get it every morning at 8am — one setup, then forget it

Use the included cloud scheduler `.github/workflows/daily.yml` (runs on GitHub's
servers, free, no computer needed):

1. Push this project to a GitHub repo.
2. Repo **Settings ▸ Secrets ▸ Actions** → add `RESEND_API_KEY`.
3. Commit your `config.yaml` with `email.to` set.

Done — it emails you daily. Its cron is **UTC**: `0 12 * * *` ≈ 8am Eastern in
summer; switch to `0 13 * * *` in winter (GitHub doesn't shift for DST). Prefer
your own machine? `0 8 * * *` in `crontab -e` fires at exactly 8am local, but
only while the machine is awake.

## 💸 Earning commission (affiliate) — read this first

Affiliate links let a publisher earn when readers buy. Three realities shape how
this actually works:

- **You earn on *other people's* purchases, not your own.** Buying through your
  own tag is disqualified (and violates the terms). Monetization only pays once
  you **distribute** the digest to an audience — a website, an opted-in
  newsletter, or social posts.
- **Amazon links in email** are permitted only to **opted-in** recipients, so
  the email channel monetizes only a real subscriber list — not a self-digest.
- **Amazon's product API changed:** the old PA-API was retired (mid-2026) in
  favor of the **Creators API**, which needs ~10 sales in 30 days to get
  credentials. So don't start with the API — start with **tag injection**.

**What's wired up:** `affiliate.py` rewrites deal links with your tracking:

1. **Amazon Associates tag injection** — join (free), get your tag
   (e.g. `willoughby-20`), set `affiliate.amazon_tag`. Genuine Amazon links in
   your feeds get `?tag=...` appended (no cloaking — Amazon forbids redirects).
2. **Other networks** (CJ, Rakuten, Awin, Impact, Walmart/Target programs) —
   paste their deeplink templates into `affiliate.deeplink_rules`.
3. A **disclosure** line and a **"prices retrieved"** timestamp are added to
   every digest automatically (FTC + Amazon requirements).

Set `affiliate.enabled: true` once you have a tag. Tip: if wrapping many
merchants by hand is tedious, a link-monetization service like **Skimlinks/Sovrn**
can auto-affiliate any supported merchant from one account.

### Affiliate product feeds (many merchants at once)

Tag injection monetizes links you already have; **product feeds** bring in
structured deals across thousands of merchants — with the commission link
already baked in. Each network (Awin, CJ, Rakuten, Impact) gives you a
downloadable feed URL from its dashboard. Add them under `feeds:` in
`config.yaml`:

```yaml
feeds:
  - name: awin-someretailer
    network: awin          # preset column mapping; or supply your own `mapping:`
    url: "https://productdata.awin.com/datafeed/download/apikey/…/format/csv/compression/gzip/"
    min_discount: 25
```

`fetchers/feeds.py` downloads the feed (CSV/TSV/XML/JSON, gzip supported), maps
the columns, keeps only genuine markdowns above `min_discount`, and emits Deals.
Because feed links are already commission-tracked, they're surfaced as-is (never
re-wrapped) and their click-tracking keeps them clean of extra params.

### Auto-monetization (catch-all): Skimlinks/Sovrn + Amazon OneLink

These are **client-side scripts** (they run on the web pages, never in email) that
monetize automatically:

- **Skimlinks/Sovrn** turns *unaffiliated* merchant links into commission links
  across ~48k merchants with no per-network setup — a catch-all for deals you
  didn't monetize yourself. Set `automonetize.skimlinks.publisher_id`.
- **Amazon OneLink** geo-redirects international Amazon clicks to their local
  store with your linked tags, so you earn on non-US shoppers. Set
  `automonetize.onelink.instance_id` (the `adInstanceId` from OneLink setup).

The important part is **coordination**: links you already affiliated server-side
(Amazon tags, network deep links) are marked `class="noskimlinks"` so Skimlinks
won't override your own tags — it only earns on the long tail you didn't cover.
OneLink complements (never conflicts with) your Amazon tags. Both are off until
you add IDs.

One compliance note: these third-party scripts set cookies, so update the
`[REVIEW: cookies]` and networks sections of `site_assets/privacy.html` before
enabling them.

## 🌐 Publish a public page others can click (GitHub Pages)

This is where the affiliate links become compliant and actually earn: a public
web page you can share.

```bash
python cli.py config.yaml --site _site   # builds _site/index.html
```

`site.py` renders a responsive deals board (live keyword filter, essentials vs
biggest-discounts, price tags). Compliance is built in: a disclosure ribbon near
the top, the exact "As an Amazon Associate…" line plus an FTC-style disclosure in
the footer, a "prices retrieved" timestamp, and every outbound link carries
`rel="sponsored nofollow noopener"` — the correct signal for paid links.

**Host it free:**
1. Push this repo to GitHub (public repos get Pages for free).
2. **Settings ▸ Pages ▸ Source → "GitHub Actions."**
3. The included `.github/workflows/pages.yml` rebuilds and republishes the page
   daily and on every push. Your site lands at
   `https://<user>.github.io/<repo>/`.

Two things worth doing before you drive real traffic: add a simple **privacy
policy** page (most affiliate networks require one), and remember Amazon's rule
that **displayed prices should come from live API data** — until you have Creators
API access, keep price claims light on the page (the build already shows a
"verify on the retailer's site" note and a retrieval timestamp to stay honest).

## 📈 Click tracking — see what earns, then rank for it

The point of tracking isn't vanity metrics: it's a feedback loop. Log which
deals get clicked, then let scoring favor the categories and merchants that
actually convert. Three parts, all compliant:

**1. Tagged links (automatic).** `tracking.py` tags every outbound link:
- **Non-Amazon** links get UTM params (`utm_source/medium/campaign/content/term`)
  so any analytics tool can attribute the click.
- **Amazon** links stay **direct** and get Amazon's native **`ascsubtag`**
  (e.g. `web-groceries`), which shows per-channel/category performance right in
  your Associates reports. Amazon links are never routed through a redirect —
  Amazon prohibits redirects that obscure the destination.

**2. Logged redirects (non-Amazon).** With `tracking.redirects: true`, the build
generates `/go/<id>/` pages. Each is a **transparent** page ("Taking you to
Walmart…", destination shown), fires a beacon to your collector, then forwards.
These double as clean short links you can paste into Telegram or a local
Facebook group — your distribution channels.

**3. A tiny collector.** `tracker/` is a ready-to-deploy **Cloudflare Worker**
(free tier) that receives beacons and serves a `/stats` JSON endpoint:
```bash
cd tracker
npm i -g wrangler && wrangler login
wrangler kv namespace create CLICKS      # paste the id into wrangler.toml
wrangler deploy
```
Then in `config.yaml` set `tracking.beacon_url` to the Worker URL and
`tracking.stats_url` to `<url>/stats`. (No collector? Leave `beacon_url` blank
and tracking is a silent no-op; or point the beacon at any endpoint that accepts
a POST — a Google Apps Script web app appending to a Sheet works too.)

**The payoff — feedback into scoring.** On each run the pipeline reads
`stats_url` (or a local `stats_file`) and adds a **popularity boost**: deals in
categories/merchants that get clicked rise in tomorrow's digest. Your board
learns what your audience actually buys, and the affiliate `ascsubtag`/UTM data
tells you which of those actually earned.

## 📬 Build a list — signup form + daily broadcast

This is the piece that turns the page into a business: a real opted-in list.
It's also what makes Amazon links in email *compliant* (Amazon only allows them
to opted-in recipients). Built on **Resend Audiences + Broadcasts**, which handle
the unsubscribe flow and List-Unsubscribe headers for you.

**1. Signup form (on the page).** Set `list.enabled: true` and
`list.signup_endpoint` to your Worker's `/subscribe` URL. A capture band appears
on the page; it POSTs the email to your Worker, which adds it to your Resend list
using the API key **server-side** (never exposed in the page). A honeypot field
drops bots.

**2. Point the Worker at Resend.** The same `tracker/` Worker handles signups.
In `tracker/wrangler.toml` set `RESEND_AUDIENCE_ID`, then store the key as a
secret and redeploy:
```bash
cd tracker
wrangler secret put RESEND_API_KEY
wrangler deploy
```
Create the audience first at resend.com ▸ Audiences (free up to 1,000 contacts)
and copy its id.

**3. Send the list.** `python cli.py config.yaml --broadcast` renders today's
digest (with an unsubscribe footer + your physical address) and sends it as a
Resend Broadcast to everyone on the list. The included
`.github/workflows/broadcast.yml` does this every morning once you enable it.

**Before you send to real people, three non-negotiables:**
- A **verified sending domain** in `email.from` (the `resend.dev` sandbox can't
  broadcast to a list). Verify one in resend.com ▸ Domains.
- A **physical mailing address** in `list.sender_address` — CAN-SPAM requires it,
  and it's added to the footer automatically.
- A **privacy policy** page at `list.privacy_url` — a reviewable starter ships in
  `site_assets/privacy.html` and deploys automatically; fill its `[REVIEW: …]`
  blanks and delete the notice banner before publishing. Consider **double
  opt-in** (a confirmation click) for cleaner deliverability; this build uses
  single opt-in with clear consent.

Anything you drop in `site_assets/` (favicon, an `about.html`, etc.) is copied to
the site root on each build, with `{{BUSINESS_NAME}}`/`{{CONTACT_EMAIL}}`/
`{{MAILING_ADDRESS}}`/`{{LOCATION}}` filled from config.

## 🔎 SEO per-deal pages (free organic traffic)

Set `seo.enabled: true` and a `site.base_url`, and the build generates an
indexable **`/deal/<slug>/` page per deal** — the durable, rankable surface
(region board pages change daily and aren't good SEO targets). Each page carries:

- **schema.org `Product` + `Offer`** JSON-LD (price, currency, availability,
  `priceValidUntil`) for rich results — an `Offer` is only emitted when a real
  price is known, as Google requires;
- a unique `<title>`/description, **canonical URL**, Open Graph + Twitter tags;
- a short blurb + **related-deal links** (to avoid thin, scaled-content pages);
- the affiliate CTA (`rel="sponsored nofollow noopener"`) with click logging.

It also writes **`sitemap.xml`** (only live pages: active deals + region + landing)
and **`robots.txt`** (which disallows the `/go/` redirect layer). With
`link_cards_to_pages: true`, board cards link to these on-site pages — internal
links that help crawlers discover them and keep visitors on your site.

**Pages accumulate — they don't 404.** A durable catalog (`data/catalog.ndjson`,
text and git-diffable) records every deal ever seen. Each build upserts today's
deals, prunes anything not seen for `retention_days` (default 45), and renders a
page for **every** surviving entry:
- **Active** deals (in today's feed) render normally and go in the sitemap.
- **Expired** deals (seen before, gone today) render in a **noindex "this deal
  expired"** state (schema `Discontinued`) so the URL stays live at **200 instead
  of 404** — old backlinks and any rankings keep landing somewhere useful, and
  their related-links funnel visitors to current deals. They're kept out of the
  sitemap.

The catalog survives GitHub's stateless rebuilds because `pages.yml` **commits it
back to the repo** after each run (with `[skip ci]` + a `data/**` push-ignore so
it doesn't loop). After `retention_days`, an expired page is dropped and will
then 404 — acceptable once a deal is long gone.

**Honest caveats — read before expecting traffic:**
- **SEO is a long game.** New pages take weeks to index and rank, and you're
  competing with Slickdeals/RetailMeNot nationally. Your winnable keywords are
  **local** ("cheap diapers Willoughby", store + item), which is why the local
  angle matters.
- **Thin content is penalized.** One-line affiliate pages don't rank; the blurb
  + related links help, but adding real context (specs, why it's a good price)
  is what wins.
- **Retention is a trade-off.** Longer retention keeps more URLs alive (fewer
  404s) but grows the catalog and page count; `max_pages` caps rendering
  (active first).

## 🗺️ Multiple regions (wider geographic base)

Multi-region is opt-in and shares work: **national deals (RSS + affiliate feeds)
are fetched once**, and only the local layer (Kroger by zip) and the output page
vary per region. Add a `regions:` list to `config.yaml`:

```yaml
regions:
  - id: willoughby
    label: "Willoughby, OH"
    zip: "44094"
  - id: mentor
    label: "Mentor, OH"
    zip: "44060"
```

- **One region** → a single page at the site root, exactly like before.
- **Several regions** → the build writes `/<id>/` pages (each with a region
  switcher and its own local deals) plus a root **landing page** to pick an area.
  Per-region `/go/` redirect pages are generated inside each region folder.

Clicks are attributed by region (beacon, UTM `utm_campaign`, and Amazon
`ascsubtag`), and the collector's `/stats` buckets by region too — so you can see
which areas convert. Give a region its own `audience_id` and
`python cli.py config.yaml --broadcast` sends that region's digest to that list;
regions without one are skipped.

Grow in rings — Willoughby → Lake County → Northeast Ohio — keeping the local
edge national aggregators can't match. Local sources worth adding for NE Ohio:
**Giant Eagle**, Meijer, and CVS/Walgreens weekly ads.

## The most important design decision: sources, not scraping

You asked to "scrape everything." For a deals aggregator that's usually the
*wrong* first move — the best deal data is already published in structured form,
and scraping HTML is brittle (layouts change), often against sites' Terms of
Service, and gives you no monetization. Prefer sources in this order:

1. **RSS feeds** — Slickdeals, DealNews, Woot, and most deal blogs publish them.
   Free, instant, structured. Already wired up here.
2. **Affiliate product feeds / APIs** — the professional path. Join a network
   (Rakuten Advertising, CJ/Commission Junction, Impact, Awin, ShareASale, or
   Amazon's Product Advertising API) and you get *clean deal feeds* for
   thousands of merchants **and** you earn commission on every click that
   converts. This is how real deal sites (Slickdeals, RetailMeNot) make money.
3. **Retailer / local APIs** — Kroger (wired up here; great for Ohio essentials),
   eBay Browse API, Best Buy, Target. For local restaurants: Yelp Fusion or
   Google Places to find spots, then their own promo pages/feeds.
4. **Scraping — last resort only.** For a specific site with no feed/API, scrape
   *that one page* politely: read its `robots.txt`, respect it, cache
   aggressively, rate-limit (1 request / few seconds), set a real User-Agent,
   and never scrape behind a login or paywall. Add these as new files under
   `dealhunter/fetchers/` that return `Deal` objects, exactly like the others.

## How it fits together

```
config.yaml ─┐
             ├─► fetchers/ ─► [Deal, Deal, ...] ─► scoring.enrich_and_score
rss + kroger ┘                                          │
                                                        ▼
             digest ◄── store (SQLite, dedup) ◄── scoring.passes_filter
```

- `models.py` — the `Deal` object + stable de-dupe id.
- `scoring.py` — **the brain.** Essential keyword lists, discount parsing from
  messy titles, the scoring formula, and the keep/drop filter. Start tuning here.
- `fetchers/rss_source.py` — generic feed reader (any RSS/Atom URL).
- `fetchers/kroger.py` — local essentials with real regular-vs-promo prices.
- `fetchers/feeds.py` — affiliate product feeds (Awin/CJ/Rakuten/…) → Deals.
- `store.py` — SQLite persistence; skips deals seen before.
- `affiliate.py` — rewrites links with your affiliate tags/deeplinks.
- `monetization.py` — client-side auto-monetization (Skimlinks/Sovrn, Amazon OneLink).
- `monetization.py` — client-side auto-monetization (Skimlinks/Sovrn, Amazon OneLink).
- `tracking.py` — UTM/ascsubtag tagging, logged redirects, popularity feedback.
- `digest.py` — renders the ranked Markdown **and** HTML-email digest + disclosure.
- `site.py` — renders the standalone public web page + `/go/` redirect pages.
- `emailer.py` — Resend (simple) or SMTP; keys from env vars only; list broadcasts.
- `regions.py` — normalizes config into regions (national shared, local per-zip).
- `seo.py` — per-deal indexable pages (schema.org), sitemap, robots.
- `catalog.py` — durable NDJSON catalog so deal pages accumulate across builds.
- `catalog.py` — durable NDJSON catalog so deal pages accumulate across builds.
- `pipeline.py` / `cli.py` — glue + entry point.
- `tracker/` — Cloudflare Worker: click collector + email signup endpoint.
- `site_assets/` — static files copied to the site root (incl. `privacy.html`).
- `.github/workflows/daily.yml` — cloud scheduler that emails you at ~8am.
- `.github/workflows/pages.yml` — builds & publishes the public page daily.
- `.github/workflows/broadcast.yml` — sends the daily digest to your list.

## Tuning what counts as "necessary and beneficial"

Edit `ESSENTIAL_CATEGORIES` in `scoring.py` and the `filters` block in
`config.yaml`:
- `min_discount` — bar for non-essential "wants" (default 50%, raise toward 80%).
- `essential_min_discount` — low bar for essentials (default 15%).
- Essentials and local deals always outrank equivalent non-essentials via the
  score bonuses in `score_deal()`.

## Sensible next steps

- **Finish the privacy page** — fill the `[REVIEW: …]` blanks in `site_assets/privacy.html`.
- **Add double opt-in** to the signup flow for cleaner deliverability.
- **Wire real analytics** (Plausible/GoatCounter) alongside the collector for dashboards.
- **Add Yelp/Google Places** for Willoughby restaurant deals (a `fetchers/local.py`).
- **Price history** — store lowest-ever price per product to flag true lows
  (like CamelCamelCamel) instead of trusting "was" prices.
- **A tiny web dashboard** instead of Markdown, once the pipeline feels right.

Legal note: respect each source's Terms of Service and robots.txt, and follow
the disclosure rules of any affiliate program you join. This is a starting
scaffold, not legal advice.
