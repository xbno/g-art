"""Append-only node store for the evolution tree. SQLite, single file.

Nothing is ever deleted; returning to an old pair later is just branching
from its node id. Thumbnails live on disk next to the db, keyed by node id.
"""

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    photo TEXT NOT NULL,
    seed INTEGER NOT NULL,
    prompt TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    parent_id TEXT REFERENCES nodes(id),
    genome TEXT NOT NULL,
    seed INTEGER NOT NULL,
    generation INTEGER NOT NULL,
    slot TEXT NOT NULL,              -- 'root' | 'a' | 'b'
    chosen INTEGER NOT NULL DEFAULT 0,
    prompt_context TEXT,             -- steering prompt / mutator rationale
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pins (
    node_id TEXT PRIMARY KEY REFERENCES nodes(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nid() -> str:
    return secrets.token_hex(4)


class Store:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    def new_run(self, photo: str, seed: int, prompt: str | None = None) -> str:
        rid = _nid()
        self.db.execute("INSERT INTO runs VALUES (?,?,?,?,?)",
                        (rid, photo, seed, prompt, _now()))
        self.db.commit()
        return rid

    def add_node(self, run_id: str, parent_id: str | None, genome: dict,
                 seed: int, generation: int, slot: str,
                 prompt_context: str | None = None) -> str:
        nid = _nid()
        self.db.execute(
            "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,0,?,NULL,?)",
            (nid, run_id, parent_id, json.dumps(genome), seed,
             generation, slot, prompt_context, _now()))
        self.db.commit()
        return nid

    def mark_chosen(self, node_id: str) -> None:
        self.db.execute("UPDATE nodes SET chosen=1 WHERE id=?", (node_id,))
        self.db.commit()

    def pin(self, node_id: str, name: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO pins VALUES (?,?,?)",
                        (node_id, name, _now()))
        self.db.commit()

    def get_node(self, node_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM nodes WHERE id=?",
                              (node_id,)).fetchone()
        return self._node(row) if row else None

    def get_run(self, run_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM runs WHERE id=?",
                              (run_id,)).fetchone()
        return dict(row) if row else None

    def lineage(self, node_id: str) -> list[dict]:
        """Root -> node chain of chosen ancestry."""
        out: list[dict] = []
        cur = self.get_node(node_id)
        while cur:
            out.append(cur)
            cur = self.get_node(cur["parent_id"]) if cur["parent_id"] else None
        return list(reversed(out))

    def generation_nodes(self, run_id: str, generation: int) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM nodes WHERE run_id=? AND generation=? "
            "ORDER BY slot", (run_id, generation)).fetchall()
        return [self._node(r) for r in rows]

    def last_chosen(self, run_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM nodes WHERE run_id=? AND chosen=1 "
            "ORDER BY generation DESC LIMIT 1", (run_id,)).fetchone()
        return self._node(row) if row else None

    def pins(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT p.name, p.node_id, p.created_at FROM pins p "
            "ORDER BY p.created_at").fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _node(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["genome"] = json.loads(d["genome"])
        return d
