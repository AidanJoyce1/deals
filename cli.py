#!/usr/bin/env python3
"""DealHunter entry point.

Usage:
  python cli.py [config.yaml]                 # print today's digest
  python cli.py config.yaml --out today.md    # save Markdown to a file
  python cli.py config.yaml --email           # email the digest
  python cli.py config.yaml --site _site      # build the GitHub Pages site
  python cli.py config.yaml --broadcast       # send today's digest to your list
  python cli.py config.yaml --email --site _site   # do both
"""
import sys
from pathlib import Path

from dealhunter.pipeline import run, load_config
from dealhunter.emailer import send_digest, send_broadcast, EmailNotConfigured
from dealhunter.site import build_site


def main():
    args = list(sys.argv[1:])
    do_email = "--email" in args
    if do_email:
        args.remove("--email")

    do_broadcast = "--broadcast" in args
    if do_broadcast:
        args.remove("--broadcast")

    site_dir = None
    if "--site" in args:
        i = args.index("--site")
        site_dir = args[i + 1]
        del args[i:i + 2]

    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]

    config_path = args[0] if args else "config.yaml"
    result = run(config_path)
    s = result["stats"]
    print(f"[dealhunter] fetched {s['fetched']} · kept {s['kept']} · new {s['new']}",
          file=sys.stderr)

    if out:
        Path(out).write_text(result["markdown"])
        print(f"[dealhunter] wrote {out}", file=sys.stderr)

    if site_dir:
        cfg = load_config(config_path)
        path = build_site(result, cfg, site_dir)
        print(f"[dealhunter] built site: {path}", file=sys.stderr)

    if do_email:
        cfg = load_config(config_path)
        try:
            reason = send_digest(result["subject"], result["html"],
                                 result["markdown"], cfg.get("email", {}))
            if reason:
                print(f"[dealhunter] email skipped: {reason}", file=sys.stderr)
            else:
                to = cfg.get("email", {}).get("to")
                print(f"[dealhunter] emailed digest to {to}", file=sys.stderr)
        except EmailNotConfigured as e:
            print(f"[dealhunter] email not configured: {e}", file=sys.stderr)
            sys.exit(1)

    if do_broadcast:
        cfg = load_config(config_path)
        regions = result.get("regions") or [result]
        default_aud = cfg.get("list", {}).get("audience_id", "")
        sent = 0
        for r in regions:
            aud = r.get("audience_id") or default_aud
            if not aud:
                print(f"[dealhunter] {r.get('id','?')}: no audience id — skipped",
                      file=sys.stderr)
                continue
            try:
                bid = send_broadcast(r["subject"],
                                     r.get("broadcast_html") or r["html"], cfg, aud)
                print(f"[dealhunter] broadcast '{r.get('id','')}' sent (id={bid})",
                      file=sys.stderr)
                sent += 1
            except EmailNotConfigured as e:
                print(f"[dealhunter] broadcast not configured: {e}", file=sys.stderr)
                sys.exit(1)
        if not sent:
            print("[dealhunter] no broadcasts sent (configure an audience id)",
                  file=sys.stderr)

    if not out and not do_email and not site_dir and not do_broadcast:
        print(result["markdown"])


if __name__ == "__main__":
    main()
