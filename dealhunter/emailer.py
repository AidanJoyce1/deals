"""Send the digest by email — the simple way (Resend) or classic SMTP.

SIMPLEST PATH (recommended): Resend. One API key, one HTTP call, no app
passwords, free tier ~3,000 emails/month.
    1. Sign up at https://resend.com and create an API key.
    2. export RESEND_API_KEY="re_..."
    3. Set email.to in config.yaml. To start, leave email.from as
       "onboarding@resend.dev" (Resend's sandbox sender, which delivers to your
       own signup address). Later, verify your domain for a custom From.

CLASSIC PATH (fallback): SMTP with SMTP_USER / SMTP_PASSWORD env vars
(Gmail needs an App Password).

send_digest() auto-selects: if RESEND_API_KEY is set it uses Resend, otherwise
it falls back to SMTP. You only configure one.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import requests

RESEND_ENDPOINT = "https://api.resend.com/emails"
RESEND_BROADCASTS = "https://api.resend.com/broadcasts"


class EmailNotConfigured(RuntimeError):
    pass


def build_message(subject: str, html_body: str, text_body: str,
                  from_addr: str, to_addrs: list[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(text_body)                       # plain-text fallback
    msg.add_alternative(html_body, subtype="html")   # rich version
    return msg


def send(msg: EmailMessage, host: str, port: int,
         user: str, password: str, security: str = "ssl", timeout: int = 30):
    if security == "ssl":                            # port 465
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout) as s:
            s.login(user, password)
            s.send_message(msg)
    else:                                            # starttls, port 587
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, password)
            s.send_message(msg)


def send_via_resend(subject: str, html_body: str, text_body: str,
                    from_addr: str, to_addrs: list[str], api_key: str) -> str:
    """Send through Resend's REST API. Returns the message id."""
    resp = requests.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"from": from_addr, "to": to_addrs, "subject": subject,
              "html": html_body, "text": text_body},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def send_broadcast(subject: str, html_body: str, cfg: dict,
                   audience_id: str = "") -> str:
    """Send the digest to your opted-in list via a Resend Broadcast.

    Pass `audience_id` to target a specific region's list; otherwise falls back
    to list.audience_id / RESEND_AUDIENCE_ID. Broadcasts handle the unsubscribe
    flow and List-Unsubscribe headers, so the html should contain a
    {{{RESEND_UNSUBSCRIBE_URL}}} placeholder (the pipeline adds one).
    Requires a *verified domain* sender — the sandbox address won't work.
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise EmailNotConfigured("Set RESEND_API_KEY to send a broadcast.")

    audience_id = (audience_id or cfg.get("list", {}).get("audience_id")
                   or os.getenv("RESEND_AUDIENCE_ID"))
    if not audience_id:
        raise EmailNotConfigured(
            "Set an audience id (list.audience_id or a region's audience_id).")

    from_addr = cfg.get("email", {}).get("from") or ""
    if not from_addr or from_addr.endswith("resend.dev"):
        raise EmailNotConfigured(
            "Broadcasts need a verified-domain sender in email.from "
            "(the resend.dev sandbox address can't send to a list).")

    resp = requests.post(
        RESEND_BROADCASTS,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        # audience_id is the long-standing REST field; newer "Segments"
        # accounts accept the same id here.
        json={"audience_id": audience_id, "from": from_addr,
              "subject": subject, "html": html_body, "send": True},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("id", "")


def send_digest(subject: str, html_body: str, text_body: str,
                email_cfg: dict) -> Optional[str]:
    """Deliver the digest. Auto-selects Resend (if RESEND_API_KEY set) else SMTP.

    Returns None on success, or a human-readable reason if skipped.
    """
    if not email_cfg or not email_cfg.get("enabled"):
        return "email disabled in config"

    to_addrs = email_cfg.get("to")
    if isinstance(to_addrs, str):
        to_addrs = [to_addrs]
    if not to_addrs:
        raise EmailNotConfigured("No 'to' address configured in config.yaml.")

    # --- Preferred: Resend (one key, no app password) ---
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        from_addr = email_cfg.get("from") or "onboarding@resend.dev"
        send_via_resend(subject, html_body, text_body, from_addr, to_addrs,
                        resend_key)
        return None

    # --- Fallback: SMTP ---
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not user or not password:
        raise EmailNotConfigured(
            "Set RESEND_API_KEY (simplest), or SMTP_USER and SMTP_PASSWORD.")

    from_addr = email_cfg.get("from") or user
    msg = build_message(subject, html_body, text_body, from_addr, to_addrs)
    send(
        msg,
        host=email_cfg.get("smtp_host", "smtp.gmail.com"),
        port=int(email_cfg.get("smtp_port", 465)),
        user=user,
        password=password,
        security=email_cfg.get("security", "ssl"),
    )
    return None
