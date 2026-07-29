/**
 * DealHunter click collector — a tiny Cloudflare Worker (free tier).
 *
 * Endpoints:
 *   POST /            receive a click beacon (text/plain JSON body). Returns 204.
 *   GET  /stats       return {category:{...}, merchant:{...}, total} as JSON.
 *
 * The page/redirects send beacons here; the daily build reads /stats and feeds
 * it back into scoring (popularity signal). Counts live in Workers KV.
 *
 * Deploy:
 *   1. npm i -g wrangler  &&  wrangler login
 *   2. wrangler kv namespace create CLICKS        # copy the id into wrangler.toml
 *   3. wrangler deploy
 *   4. Put the deployed URL in config.yaml -> tracking.beacon_url (POST) and
 *      tracking.stats_url ("<url>/stats").
 *
 * Low-volume, last-write-wins increments are fine here. For heavy traffic,
 * swap KV for Durable Objects or D1.
 */
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const json = (obj, status) =>
  new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "Content-Type": "application/json", ...CORS },
  });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    if (request.method === "GET" && url.pathname === "/stats") {
      const out = { category: {}, merchant: {}, region: {}, total: 0 };
      const dims = { cat: "category", merch: "merchant", reg: "region" };
      for (const prefix of Object.keys(dims)) {
        const list = await env.CLICKS.list({ prefix: prefix + ":" });
        for (const k of list.keys) {
          const name = k.name.slice(prefix.length + 1);
          out[dims[prefix]][name] = parseInt((await env.CLICKS.get(k.name)) || "0", 10);
        }
      }
      out.total = parseInt((await env.CLICKS.get("total")) || "0", 10);
      return new Response(JSON.stringify(out), {
        headers: { "Content-Type": "application/json", ...CORS },
      });
    }

    if (request.method === "POST" && url.pathname === "/subscribe") {
      // Adds an email to your Resend Audience. Keeps RESEND_API_KEY server-side.
      // Set: wrangler secret put RESEND_API_KEY  and  vars RESEND_AUDIENCE_ID.
      let body = {};
      try {
        body = JSON.parse(await request.text());
      } catch (e) {}
      const email = (body.email || "").trim();
      if (body.website) return json({ ok: true }, 200); // honeypot: pretend success
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        return json({ ok: false, error: "invalid email" }, 400);
      }
      if (!env.RESEND_API_KEY || !env.RESEND_AUDIENCE_ID) {
        return json({ ok: false, error: "collector not configured" }, 500);
      }
      const r = await fetch(
        "https://api.resend.com/audiences/" + env.RESEND_AUDIENCE_ID + "/contacts",
        {
          method: "POST",
          headers: {
            Authorization: "Bearer " + env.RESEND_API_KEY,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, unsubscribed: false }),
        }
      );
      // Treat "already exists" as success so re-subscribes look clean.
      if (r.ok || r.status === 409) return json({ ok: true }, 200);
      return json({ ok: false, error: "subscribe failed" }, 502);
    }

    if (request.method === "POST") {
      let ev = {};
      try {
        ev = JSON.parse(await request.text());
      } catch (e) {
        return new Response(null, { status: 204, headers: CORS });
      }
      const bump = async (k) => {
        const cur = parseInt((await env.CLICKS.get(k)) || "0", 10);
        await env.CLICKS.put(k, String(cur + 1));
      };
      const jobs = [bump("total")];
      if (ev.cat) jobs.push(bump("cat:" + String(ev.cat).slice(0, 40)));
      if (ev.merchant) jobs.push(bump("merch:" + String(ev.merchant).slice(0, 60)));
      if (ev.region) jobs.push(bump("reg:" + String(ev.region).slice(0, 40)));
      await Promise.all(jobs);
      return new Response(null, { status: 204, headers: CORS });
    }

    return new Response("DealHunter collector", { headers: CORS });
  },
};
