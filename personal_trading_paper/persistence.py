from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import SessionState, state_from_dict, state_to_dict


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self, starting_capital):
        if not self.path.exists():
            from decimal import Decimal
            return SessionState(Decimal(starting_capital), Decimal(starting_capital))
        try:
            with closing(sqlite3.connect(self.path)) as db:
                row = db.execute("SELECT value FROM session WHERE key='state'").fetchone()
            if row is None:
                raise ValueError("corrupt session state: missing record")
            return state_from_dict(json.loads(row[0]))
        except (sqlite3.Error, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("corrupt session state; refusing to trade") from exc

    def save(self, state: SessionState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS session (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, entry_time INTEGER NOT NULL, exit_time INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("INSERT INTO session(key,value) VALUES('state',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(state_to_dict(state)),))
            db.execute("DELETE FROM trades")
            db.executemany("INSERT INTO trades(entry_time,exit_time,payload) VALUES(?,?,?)", [(t.entry_time, t.exit_time, json.dumps({k: str(v) if hasattr(v, 'as_tuple') else v for k, v in t.__dict__.items()})) for t in state.trades])
            db.commit()

