"""Niveles: se cargan desde ficheros JSON en ``resources/levels`` (ver level_generator.py).

Cada mapa describe solo el interior del nivel: 9 caracteres por fila y 16 filas o más. Si
tiene más de 16, el nivel es más alto que la pantalla y se hace scroll vertical. Los bordes
(finos) se añaden solos alrededor; ``#`` sirve para poner bloques u obstáculos dentro.

  #  bloque sólido      =  plataforma (se puede atravesar saltando desde abajo)
  L  ladrillo/cemento: sólido que además sirve de parapeto (bloquea ataques y visión)
  H  botiquín: recupera un corazón
  C  moneda de oro: +100 puntos
  B  bomba: se enciende con una burbuja o con la acción encima; explota a los 3 s
  P  inicio del jugador E  enemigo rojo (lengua)
  A  enemigo azul (láser por los ojos)
  N  enemigo naranja (cuchillo, cuerpo a cuerpo; se agacha para esquivar burbujas)
  S  estrella de fin de nivel
"""

import json
import logging
from dataclasses import dataclass, field
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
    bricks: list = field(default_factory=list)   # ladrillos (también están en solids)
    height: int = 0                              # alto del mundo en px (con bordes)
    rows: int = 0
    medkits: list = field(default_factory=list)  # posiciones (casillas) de los botiquines
    coins: list = field(default_factory=list)    # posiciones (casillas) de las monedas
    bombs: list = field(default_factory=list)    # posiciones (casillas) de las bombas


def border_walls(height=S.FIELD_H) -> list:
    """Bordes del nivel. Se ven de BORDER px, pero por fuera son gruesos (una casilla más)
    para que nada los atraviese aunque caiga muy rápido."""
    t, w, h, b = S.TILE, S.FIELD_W, height, S.BORDER
    return [
        Rect(-t, -t, w + 2 * t, t + b),          # techo
        Rect(-t, h - b, w + 2 * t, t + b),       # suelo
        Rect(-t, -t, t + b, h + 2 * t),          # izquierda
        Rect(w - b, -t, t + b, h + 2 * t),       # derecha
    ]


def parse_level(rows) -> LevelData:
    if len(rows) < S.ROWS:
        raise ValueError(f"El nivel debe tener al menos {S.ROWS} filas, tiene {len(rows)}")
    height = S.level_height(len(rows))
    solids, oneway, enemies, spawn, star = border_walls(height), [], [], None, None
    bricks, medkits, coins, bombs = [], [], [], []
    for r, row in enumerate(rows):
        if len(row) != S.COLS:
            raise ValueError(f"Fila {r}: debe tener {S.COLS} columnas")
        for c, ch in enumerate(row):
            x, y = S.cell_pos(c, r)
            if ch == "#":
                solids.append(Rect(x, y, S.TILE, S.TILE))
            elif ch == "L":
                brick = Rect(x, y, S.TILE, S.TILE)
                solids.append(brick)
                bricks.append(brick)
            elif ch == "=":
                oneway.append(Rect(x, y, S.TILE, 12))
            elif ch == "P":
                spawn = (x, y)
            elif ch in "EAN":
                enemies.append((x, y, ch))
            elif ch == "S":
                star = (x, y)
            elif ch == "H":
                medkits.append((x, y))
            elif ch == "C":
                coins.append((x, y))
            elif ch == "B":
                bombs.append((x, y))
            elif ch != " ":
                raise ValueError(f"Fila {r}, columna {c}: carácter desconocido {ch!r}")
    if spawn is None:
        raise ValueError("El nivel no tiene inicio de jugador 'P'")
    return LevelData(solids, oneway, spawn, enemies, star, bricks, height, len(rows), medkits,
                     coins, bombs)


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
