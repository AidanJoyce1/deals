# 🚀 Deploy & Launch Playbook

Everything you need to take DealHunter from code to a live, monetized, growing
deals site. Work top to bottom — **each step leaves you with something that
works**, so you can stop anywhere and still have a running system.

There are three parts:
- **Part A — Deploy** (get it live, in rings)
- **Part B — Market** (get traffic — the real bottleneck)
- **Part C — A 4-week launch plan** that runs both at once
- **Part D — Cheat sheets** (where each secret lives, costs, troubleshooting)

> The single most common mistake: piling on monetization before you have
> traffic. Affiliate revenue ≈ visitors × conversion × commission. With no
> visitors it's zero, no matter how many networks you add. Deploy the essentials,
> then spend your energy on Part B.

---

## Part A — Deploy

### What it costs (near zero)
| Thing | Cost | Needed for |
|---|---|---|
| GitHub (public repo) | Free | Hosting + automation |
| Resend | Free (3,000 emails/mo) | Email + list |
| Cloudflare Workers | Free tier | Click tracking + signups |
| Amazon Associates | Free | Affiliate commission |
| Kroger API | Free | Local grocery deals |
| **A domain name** | ~$12/yr | **Verified email sender + nicer URL** |

A domain is the only near-necessary spend — Resend needs a verified domain to
send to a real list, and it makes your URL trustworthy. Get one before Step 6 if
you can (Namecheap, Cloudflare Registrar, Porkbun).

### Step 0 — Create the accounts
- [ ] [GitHub](https://github.com) account
- [ ] [Resend](https://resend.com) account
- [ ] [Cloudflare](https://cloudflare.com) account
- [ ] [Amazon Associates](https://affiliate-program.amazon.com) (approval can take a few days)
- [ ] (Optional) a domain name

### Step 1 — Put the code on GitHub
```bash
cd dealhunter
git init
git add .
git commit -m "Initial DealHunter"
```
Create a **public** repo on GitHub (public = free Pages), then:
```bash
git remote add origin https://github.com/<you>/<repo>.git
git branch -M main
git push -u origin main
```

### Step 2 — Prove it runs locally
```bash
pip install -r requirements.txt
python cli.py config.yaml
```
You should see today's digest print in your terminal. If yes, the engine works.

### Step 3 — Basic config (no keys yet)
Open `config.yaml` and set just these:
```yaml
regions:
  - id: willoughby
    label: "Willoughby, OH"
    zip: "44094"
site:
  business_name: "Willoughby Deals Board"
  contact_email: "you@youremail.com"
```
Commit and push. Leave every `enabled:` flag `false` for now.

### Step 4 — Turn on the website (5 minutes to live)
1. Repo → **Settings → Pages → Build and deployment → Source = "GitHub Actions."**
2. Repo → **Actions** tab → **publish-site** → **Run workflow**.
3. When it's green, your site is live at
   `https://<you>.github.io/<repo>/`.

✅ **You now have a live deals site.**

### Step 5 — Set your real URL
Now that you know the URL, set it (needed later for SEO + email links):
```yaml
site:
  base_url: "https://<you>.github.io/<repo>"   # NO trailing slash; include /<repo>
```
Using a custom domain instead? Point it at Pages (Settings → Pages → Custom
domain) and use `https://yourdomain.com` here.

### Step 6 — Email the digest to yourself
1. In Resend, create an **API key**.
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `RESEND_API_KEY` = your key
3. In `config.yaml`:
   ```yaml
   email:
     enabled: true
     to: "you@youremail.com"
     from: "onboarding@resend.dev"   # sandbox to start; change after Step 10
   ```
4. Repo → **Actions → daily-deals → Run workflow** to test. Check your inbox.

✅ **You now get a daily deals email.**

### Step 7 — Click tracking + signup collector (Cloudflare Worker)
This powers click stats *and* the email signup form.
```bash
npm install -g wrangler
wrangler login
cd tracker
wrangler kv namespace create CLICKS
```
Copy the printed `id` into `tracker/wrangler.toml` (replace
`PASTE_YOUR_KV_NAMESPACE_ID_HERE`). Then:
```bash
wrangler deploy
```
Note the deployed URL (e.g. `https://dealhunter-clicks.<you>.workers.dev`) and
put it in `config.yaml`:
```yaml
tracking:
  enabled: true
  beacon_url: "https://dealhunter-clicks.<you>.workers.dev"
  stats_url: "https://dealhunter-clicks.<you>.workers.dev/stats"
```
Push. Now every click is logged, and tomorrow's ranking learns from it.

### Step 8 — Affiliate (start earning on clicks)
1. Once Amazon Associates is approved, grab your tag (e.g. `willoughby-20`).
2. In `config.yaml`:
   ```yaml
   affiliate:
     enabled: true
     amazon_tag: "willoughby-20"
   ```
3. **Product feeds (optional, more merchants):** join a network (Awin is the
   easiest), generate a product-feed URL, and add it under `feeds:` (see the
   commented examples in `config.yaml` and the README).

### Step 9 — Auto-monetization catch-all (optional)
- **Skimlinks/Sovrn:** sign up (approval required), get your publisher id, set
  `automonetize.skimlinks`. It earns on merchants you didn't cover; your own
  affiliate links are automatically protected.
- **Amazon OneLink:** set it up in Associates Central, get the `adInstanceId`,
  set `automonetize.onelink`. Earns on international Amazon shoppers.
- ⚠️ Both set cookies — update the cookies/networks sections of
  `site_assets/privacy.html` before enabling.

### Step 10 — Build the email list (the compounding asset)
1. In Resend, **verify a domain** (Domains → Add) — required to email a list.
   Update `email.from` to something like `deals@yourdomain.com`.
2. In Resend, create an **Audience**; copy its id.
3. Wire the Worker to Resend so the signup form works:
   ```bash
   cd tracker
   # put RESEND_AUDIENCE_ID in wrangler.toml [vars], then:
   wrangler secret put RESEND_API_KEY
   wrangler deploy
   ```
4. In `config.yaml`:
   ```yaml
   list:
     enabled: true
     audience_id: "<your Resend audience id>"
     signup_endpoint: "https://dealhunter-clicks.<you>.workers.dev/subscribe"
     sender_address: "Your Name · 123 Main St · Willoughby, OH 44094"  # CAN-SPAM
   ```
5. **Fill the `[REVIEW: …]` blanks in `site_assets/privacy.html`** and delete its
   banner. (Required before collecting emails.)
6. Enable the daily list send: it's already wired in
   `.github/workflows/broadcast.yml` — just make sure `RESEND_API_KEY` is set
   (Step 6) and test with **Actions → broadcast-list → Run workflow**.

✅ **Signups now flow into your list, and it emails them daily.**

### Step 11 — Local grocery deals (optional)
1. Create an app at [developer.kroger.com](https://developer.kroger.com).
2. Add `KROGER_CLIENT_ID` and `KROGER_CLIENT_SECRET` as **Actions secrets**.
3. `config.yaml`: `kroger: { enabled: true }`.

### Step 12 — Turn on SEO pages
```yaml
seo:
  enabled: true          # needs site.base_url from Step 5
```
Push. The build now generates a `/deal/<slug>/` page per deal, a `sitemap.xml`,
and `robots.txt`, and **commits the catalog back** so pages accumulate instead of
404-ing. (The `publish-site` workflow already has permission to commit it.)

### Step 13 — Add regions later (optional)
Add more entries under `regions:` (each with its own `zip`). One region = a page
at the root; several = `/willoughby/`, `/mentor/`, … plus a landing page. Grow in
rings: Willoughby → Lake County → NE Ohio.

### Step 14 — Verify the schedules
Each workflow has a **Run workflow** button (test it) and a daily schedule.
Note: **GitHub cron is UTC and ignores daylight saving** — `0 12 * * *` ≈ 8am ET
in summer, 7am in winter. Adjust the cron lines if you care about the exact time.

---

## Part B — Market it (get traffic)

Traffic is the whole game now. Your edge is **local** — you will never out-rank
Slickdeals nationally, but nobody owns "the deals that matter in Lake County, OH."
Lead with that everywhere.

### 1. Tell search engines you exist
- [ ] [Google Search Console](https://search.google.com/search-console): add your
      site, verify (drop the verification `.html` file into `site_assets/` so it
      deploys), then **submit `https://<your-site>/sitemap.xml`**.
- [ ] [Bing Webmaster Tools](https://www.bing.com/webmasters): same thing.
- [ ] Add lightweight analytics ([GoatCounter](https://www.goatcounter.com) or
      [Plausible](https://plausible.io)) so you can see what's landing.

### 2. Seed the local channels (value first, never spam)
Reuse your `/go/` short links — they're clean and trackable.
- [ ] **Local Facebook groups.** Search "Willoughby OH", "Lake County OH",
      "Mentor OH" community / buy-sell-trade groups. Join 5–10. **Read each
      group's rules.** Participate for a few days, then share *one genuinely
      great local deal* (not a link dump). Mention the free daily email once.
- [ ] **Nextdoor.** Post the best local deal to your neighborhood.
- [ ] **Reddit** (r/Cleveland, r/NortheastOhio). Redditors punish self-promotion —
      build a little karma, answer questions, and share deals where welcome. Follow
      the ~10:1 rule (ten helpful posts per self-promo).
- [ ] **A public channel** (Facebook Page, Telegram, or WhatsApp Channel). Post
      the day's top 3 deals daily — this is the easiest repeatable habit.

### 3. Turn visitors into subscribers (the compounding move)
The signup form is already on every page. Your job is to drive people to it and
give them a reason: "**one email each morning, the best local + national deals.**"
Add a "forward this to a friend" line to the email (referrals are free growth).

### 4. Content that ranks (slow but compounding)
On top of the auto-generated deal pages, write a few evergreen pages (drop them in
`site_assets/` or as new deal-style content):
- [ ] **Coupon-code pages** — high intent ("Kroger promo code Willoughby").
- [ ] **"Best [X] under $[Y]" roundups** — evergreen, higher commission.
- [ ] **Local guides** — "cheapest groceries in Lake County this week."

### 5. Local partnerships (traffic *and* revenue)
Email 3–5 local shops/restaurants: offer a **featured local slot** in the daily
email/site. A local sponsor can out-earn months of affiliate pennies and gives
locals a reason to visit.

### 6. Measure and prune
- Worker `/stats` shows clicks by **category, merchant, and region** — do more of
  what converts, drop what doesn't.
- UTM tags + your analytics show which channels send traffic.
- Search Console shows which keywords you're starting to rank for — lean into them.

### Marketing guardrails (don't torch your reputation)
- Follow **each platform's self-promotion rules** — most FB groups and subreddits
  ban link-spam and will ban you. Provide value; promote sparingly.
- Keep the **FTC/affiliate disclosure** visible (it already is on-site and in email).
- **Don't buy traffic or bots** — it converts to nothing and risks your affiliate
  accounts. **Never click your own affiliate links to "test earnings"** — that's
  a disqualified purchase and against the terms.

---

## Part C — Your first 4 weeks (deploy + market together)

**Weekend 0 — Ship it.** Steps 1–12. Buy a domain, verify it in Resend, submit
your sitemap to Search Console. Subscribe yourself. Send the site to 10
friends/family for your first subscribers and honest feedback.

**Week 1 — Show up.** Join 5–10 local FB groups and Nextdoor; just *participate*,
no promo yet. Start the daily "top 3 deals" post on one public channel. Watch
`/stats` to see if anything gets clicked.

**Week 2 — Start sharing.** Post one standout local deal in 2–3 groups (per their
rules), each time inviting people to the free daily email. Email 3 local
businesses about a featured slot. Add a "forward to a friend" line to the email.

**Week 3 — Double down.** Check `/stats` and Search Console. Do more of what
converts, cut what doesn't. Write 2 evergreen pages (a coupon page + a roundup)
targeting local keywords.

**Week 4 — Systematize.** Lock in a sustainable posting cadence, review your
subscriber growth and top categories, and send your first featured-local pitch to
a business that fits. Decide which one channel is worth going deeper on.

**Honest expectations:** first affiliate earnings are small and lumpy; SEO takes
1–3 months to show anything; the **email list is the asset that compounds**, and
**local is the moat**. Consistency beats intensity here.

---

## Part D — Cheat sheets

### Where each secret lives (the #1 gotcha)
Two separate stores — don't mix them up:

| Secret | Lives in | Used for |
|---|---|---|
| `RESEND_API_KEY` | **GitHub** Actions secrets | daily email + list broadcast |
| `KROGER_CLIENT_ID` / `_SECRET` | **GitHub** Actions secrets | local grocery deals |
| `RESEND_API_KEY` (again) | **Cloudflare** Worker (`wrangler secret put`) | signup form → Resend |
| `RESEND_AUDIENCE_ID` | **Cloudflare** `wrangler.toml` `[vars]` | which list signups join |
| KV namespace `id` | **Cloudflare** `wrangler.toml` | click storage |

For **local testing**, put keys in your shell:
`export RESEND_API_KEY=...  KROGER_CLIENT_ID=...  KROGER_CLIENT_SECRET=...`

### The commands you'll actually use
```bash
python cli.py config.yaml                 # print today's digest
python cli.py config.yaml --site _site     # build the website
python cli.py config.yaml --email          # email yourself
python cli.py config.yaml --broadcast      # send to your list
```

### Troubleshooting
- **Pages 404** → Settings → Pages Source must be **GitHub Actions**; check the
  `publish-site` run is green.
- **No email** → is `RESEND_API_KEY` set in *GitHub* secrets? For a real list you
  need a **verified domain** in `email.from` (the sandbox can't broadcast).
- **Signup form does nothing** → the Worker needs `RESEND_API_KEY` (secret) and
  `RESEND_AUDIENCE_ID` (var), then `wrangler deploy` again.
- **SEO pages / sitemap missing** → set `seo.enabled: true` **and** `site.base_url`.
- **Deal pages 404 after a day** → the catalog commit needs `contents: write` (the
  `publish-site` workflow already has it); confirm `data/catalog.ndjson` is being
  committed.
- **Wrong send time** → GitHub cron is UTC and ignores DST; edit the cron lines.

You built the whole stack. This is the part where it goes live and starts
growing. Ship Weekend 0, then live in Part B.
