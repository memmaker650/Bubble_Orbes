"""Persistencia con sqlite3: puntuaciones, ajustes y partida guardada."""

import json
import logging
import shutil
import sqlite3
from pathlib import Path

from . import paths
from . import settings as S

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

DB_NAME = f"{S.APP_NAME}_database.db"      # BubbleQuest_database.db
LEGACY_DB_NAME = "orbes.db"                 # cuando el juego se llamaba Orbes


def _legacy_data_dir() -> Path:
    """Carpeta donde guardaba los datos la versión anterior (cuando se llamaba Orbes)."""
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir(S.LEGACY_APP_NAME, S.LEGACY_APP_NAME))
    except Exception:  # platformdirs ausente o plataforma no soportada
        return Path.home() / f".{S.LEGACY_APP_NAME.lower()}"


def default_db_path() -> Path:
    """Base de datos en la carpeta de datos del juego, junto a los logs (ver paths.py):
    en macOS ``~/Library/Application Support/com.SkullWithGasMask/BubbleQuest``."""
    base = paths.data_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.error("No se pudo crear la carpeta de datos %s", base, exc_info=True)
        raise
    path = base / DB_NAME
    _migrate_legacy_db(path)
    return path


def _migrate_legacy_db(path: Path) -> None:
    """Si aún no hay base de datos, copia la de la versión anterior (``…/Orbes/orbes.db``):
    puntuaciones, partida guardada y ajustes. La antigua se conserva."""
    if path.exists():
        return
    legacy = _legacy_data_dir() / LEGACY_DB_NAME
    if not legacy.exists():
        return
    try:
        shutil.copy2(legacy, path)
    except OSError:
        log.error("No se pudo copiar la base de datos antigua %s a %s", legacy, path,
                  exc_info=True)
    else:
        log.info("Base de datos migrada de %s a %s (la antigua se conserva)", legacy, path)


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
