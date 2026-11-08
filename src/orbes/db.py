"""Persistencia con sqlite3: puntuaciones, ajustes, progreso y partida guardada."""

import json
import logging
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

# Una sola partida guardada (slot 1), como JSON con el estado completo del mundo.
SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS saved_game (
    slot     INTEGER PRIMARY KEY CHECK (slot = 1),
    data     TEXT    NOT NULL,
    saved_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
PRAGMA user_version = 2;
"""

# Dificultad con la que se consiguió cada puntuación ("easy" | "normal" | "hard").
# Las puntuaciones anteriores se quedan sin dato (NULL).
SCHEMA_V3 = """
ALTER TABLE scores ADD COLUMN difficulty TEXT;
PRAGMA user_version = 3;
"""

log = logging.getLogger(__name__)


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
        if version < 2:
            self.conn.executescript(SCHEMA_V2)
        if version < 3:
            self.conn.executescript(SCHEMA_V3)
        # Futuras migraciones: if version < 4: ...

    def close(self):
        self.conn.close()

    # --- puntuaciones ---
    def add_score(self, player: str, score: int, level: int, difficulty: str | None = None) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO scores (player, score, level, difficulty) VALUES (?, ?, ?, ?)",
                (player, int(score), int(level), difficulty),
            )
        return cur.lastrowid

    def top_scores(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT player, score, level, difficulty, created_at FROM scores "
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

    # --- partida guardada ---
    def save_game(self, data: dict) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO saved_game (slot, data, saved_at) VALUES (1, ?, datetime('now')) "
                "ON CONFLICT(slot) DO UPDATE SET data = excluded.data, saved_at = excluded.saved_at",
                (json.dumps(data, ensure_ascii=False),),
            )

    def load_game(self) -> dict | None:
        row = self.conn.execute("SELECT data FROM saved_game WHERE slot = 1").fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row["data"])
        except ValueError:
            log.error("Partida guardada ilegible; se descarta")
            self.clear_game()
            return None
        return data if isinstance(data, dict) else None

    def has_saved_game(self) -> bool:
        return self.load_game() is not None

    def clear_game(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM saved_game")
