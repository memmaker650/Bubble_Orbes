"""Persistencia con sqlite3: puntuaciones, ajustes y progreso."""

import sqlite3
from pathlib import Path

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS scores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player     TEXT    NOT NULL,
    score      INTEGER NOT NULL,
    level      INTEGER NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scores_score ON scores(score DESC);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


def default_db_path() -> Path:
    """Carpeta de datos de usuario (sandbox en iOS, Application Support en macOS)."""
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("Orbes", "Orbes"))
    except Exception:  # platformdirs ausente o plataforma no soportada
        base = Path.home() / ".orbes"
    base.mkdir(parents=True, exist_ok=True)
    return base / "orbes.db"


class Database:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.conn.executescript(SCHEMA_V1)
        # Futuras migraciones: if version < 2: ...

    def close(self):
        self.conn.close()

    # --- puntuaciones ---
    def add_score(self, player: str, score: int, level: int) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO scores (player, score, level) VALUES (?, ?, ?)",
                (player, int(score), int(level)),
            )
        return cur.lastrowid

    def top_scores(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT player, score, level, created_at FROM scores "
            "ORDER BY score DESC, id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- ajustes ---
    def get_setting(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    # --- progreso (nivel desbloqueado, base 1) ---
    def unlocked_level(self) -> int:
        return int(self.get_setting("unlocked_level", 1))

    def unlock_level(self, level: int, max_level: int) -> None:
        level = min(level, max_level)
        if level > self.unlocked_level():
            self.set_setting("unlocked_level", level)
