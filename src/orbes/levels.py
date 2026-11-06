"""Niveles: se cargan desde ficheros JSON en ``resources/levels`` (ver level_generator.py).

Cada mapa son 16 filas de 9 caracteres:

  #  muro sólido        =  plataforma (se puede atravesar saltando desde abajo)
  P  inicio del jugador E  enemigo rojo (lengua)
  B  enemigo azul (láser por los ojos)
  S  estrella de fin de nivel
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pygame import Rect

from . import settings as S

log = logging.getLogger(__name__)

LEVELS_DIR = Path(__file__).parent / "resources" / "levels"


@dataclass
class LevelDef:
    """Definición de un nivel tal y como se guarda en JSON."""

    number: int                  # número que ve el jugador (0 = tutorial)
    name: str
    rows: list
    tutorial: bool = False       # muestra la guía de pasos
    enemies_attack: bool = True  # False: los enemigos no hacen daño

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "tutorial": self.tutorial,
            "enemies_attack": self.enemies_attack,
            "map": list(self.rows),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LevelDef":
        try:
            level = cls(
                number=int(data["number"]),
                name=str(data.get("name", f"Nivel {data['number']}")),
                rows=list(data["map"]),
                tutorial=bool(data.get("tutorial", False)),
                enemies_attack=bool(data.get("enemies_attack", True)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Nivel mal definido: {exc}") from exc
        parse_level(level.rows)  # valida el mapa
        return level


def load_levels(directory=LEVELS_DIR) -> list[LevelDef]:
    """Lee todos los ``level_*.json`` de la carpeta, ordenados por número de nivel."""
    levels = []
    for path in sorted(Path(directory).glob("level_*.json")):
        try:
            levels.append(LevelDef.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    if not levels:
        raise ValueError(f"No hay niveles en {directory}")
    levels.sort(key=lambda lv: lv.number)
    numbers = [lv.number for lv in levels]
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"Números de nivel repetidos en {directory}: {numbers}")
    log.info("Niveles cargados: %s", numbers)
    return levels


@dataclass
class LevelData:
    solids: list
    oneway: list
    player_spawn: tuple
    enemy_spawns: list
    star_pos: tuple | None = None


def parse_level(rows) -> LevelData:
    if len(rows) != S.ROWS:
        raise ValueError(f"El nivel debe tener {S.ROWS} filas, tiene {len(rows)}")
    solids, oneway, enemies, spawn, star = [], [], [], None, None
    for r, row in enumerate(rows):
        if len(row) != S.COLS:
            raise ValueError(f"Fila {r}: debe tener {S.COLS} columnas")
        for c, ch in enumerate(row):
            x, y = c * S.TILE, r * S.TILE
            if ch == "#":
                solids.append(Rect(x, y, S.TILE, S.TILE))
            elif ch == "=":
                oneway.append(Rect(x, y, S.TILE, 12))
            elif ch == "P":
                spawn = (x, y)
            elif ch in "EB":
                enemies.append((x, y, ch))
            elif ch == "S":
                star = (x, y)
            elif ch != " ":
                raise ValueError(f"Fila {r}, columna {c}: carácter desconocido {ch!r}")
    if spawn is None:
        raise ValueError("El nivel no tiene inicio de jugador 'P'")
    return LevelData(solids, oneway, spawn, enemies, star)


_cache: list | None = None


def index_of(number: int) -> int:
    """Posición en LEVELS del nivel con ese número (el más cercano por debajo si no existe)."""
    levels = __getattr__("LEVELS")
    candidates = [i for i, lv in enumerate(levels) if lv.number <= number]
    return candidates[-1] if candidates else 0


def __getattr__(name):
    """``LEVELS`` se carga la primera vez que se usa (así el generador puede crear los JSON)."""
    global _cache
    if name == "LEVELS":
        if _cache is None:
            _cache = load_levels()
        return _cache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
