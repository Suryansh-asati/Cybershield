import sqlite3
from typing import Dict, List
import os


SCHEMA = """
CREATE TABLE IF NOT EXISTS flagged_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT,
    username TEXT,
    link TEXT,
    category TEXT,
    confidence REAL,
    timestamp TEXT
);
"""


class Database:
    def __init__(self, db_path='cybershield.db'):
        self.db_path = db_path
        self._ensure()

    def _ensure(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(SCHEMA)

    def insert_flagged(self, record: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO flagged_posts(platform, username, link, category, confidence, timestamp) VALUES (?,?,?,?,?,?)",
                (
                    record.get('platform'),
                    record.get('username'),
                    record.get('link'),
                    record.get('category'),
                    record.get('confidence'),
                    record.get('timestamp'),
                )
            )

    def fetch_all(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT id, platform, username, link, category, confidence, timestamp FROM flagged_posts ORDER BY id DESC")
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
        return [dict(zip(cols, r)) for r in rows]