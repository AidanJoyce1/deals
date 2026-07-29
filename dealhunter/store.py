"""SQLite persistence + de-duplication across daily runs."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from .models import Deal

SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY,
    title TEXT, url TEXT, source TEXT, merchant TEXT,
    price REAL, orig_price REAL, discount_pct REAL,
    category TEXT, is_essential INTEGER, is_local INTEGER,
    score REAL, posted_at TEXT, first_seen TEXT
);
"""


class Store:
    def __init__(self, path: str = "deals.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def upsert(self, deals: Iterable[Deal]) -> int:
        """Insert new deals; skip ones already seen. Returns # newly added."""
        now = datetime.now(timezone.utc).isoformat()
        added = 0
        for d in deals:
            cur = self.conn.execute("SELECT 1 FROM deals WHERE id = ?", (d.id,))
            if cur.fetchone():
                continue
            self.conn.execute(
                """INSERT INTO deals
                   (id,title,url,source,merchant,price,orig_price,discount_pct,
                    category,is_essential,is_local,score,posted_at,first_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d.id, d.title, d.url, d.source, d.merchant, d.price, d.orig_price,
                 d.discount_pct, d.category, int(d.is_essential), int(d.is_local),
                 d.score, d.posted_at.isoformat(), now),
            )
            added += 1
        self.conn.commit()
        return added

    def top_today(self, limit: int = 40) -> list[sqlite3.Row]:
        """Deals first seen in the last 24h, best score first."""
        cutoff = datetime.now(timezone.utc).timestamp() - 86400
        rows = self.conn.execute("SELECT * FROM deals ORDER BY score DESC").fetchall()
        out = []
        for r in rows:
            try:
                seen = datetime.fromisoformat(r["first_seen"]).timestamp()
            except Exception:
                seen = 0
            if seen >= cutoff:
                out.append(r)
            if len(out) >= limit:
                break
        return out

    def close(self):
        self.conn.close()
