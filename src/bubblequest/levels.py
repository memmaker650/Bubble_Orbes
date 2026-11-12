"""Niveles: se cargan desde ficheros JSON en ``resources/levels`` (ver level_generator.py).

Cada mapa describe solo el interior del nivel: 9 caracteres por fila y 16 filas o más. Si
tiene más de 16, el nivel es más alto que la pantalla y se hace scroll vertical. Los bordes
(finos) se añaden solos alrededor; ``#`` sirve para poner bloques u obstáculos dentro.

  #  bloque sólido      =  plataforma (se puede atravesar saltando desde abajo)
  L  ladrillo/cemento: sólido que además sirve de parapeto (bloquea ataques y visión)
  H  botiquín: recupera un corazón
  C  moneda de oro: +100 puntos
  G  gema (obligatoria: sin ella la estrella no termina el nivel). Su color depende del
     nivel (ver S.GEM_LEVELS): 10 rubí, 15 esmeralda, 20 amarilla, 25 aguamarina, 30 blanca
  B  bomba: se enciende con una burbuja o con la acción encima; explota a los 3 s
  P  inicio del jugador E  enemigo rojo (lengua)
  A  enemigo azul (láser por los ojos)
  N  enemigo naranja (cuchillo, cuerpo a cuerpo; se agacha para esquivar burbujas)
  S  estrella de fin de nivel
  J  jefe final (uno como mucho): apoya los pies en esta casilla y ocupa unas 2 x 3
     casillas por encima. Se le derrota con burbujas y bombas; da S.BOSS_POINTS puntos
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pygame import Rect

from . import settings as S

log = logging.getLogger(__name__)

LEVELS_DIR = Path(__file__).parent / "resources" / "levels"


class LevelError(ValueError):
    """Nivel mal definido. Además del texto (para el log) lleva una clave de traducción y
    sus parámetros para poder explicarlo en pantalla en el idioma del jugador."""

    def __init__(self, message, key="level_error.generic", **params):
        super().__init__(message)
        self.key = key
        self.params = params
        self.params.setdefault("detail", message)


@dataclass
class LevelDef:
    """Definición de un nivel tal y como se guarda en JSON."""

    number: int                  # número que ve el jugador (0 = tutorial)
    name: str
    rows: list
    tutorial: bool = False       # muestra la guía de pasos
    enemies_attack: bool = True  # False: los enemigos no hacen daño
    # Datos de la carga (no forman parte del nivel ni cuentan al comparar)
    error: LevelError | None = field(default=None, compare=False)  # fichero dañado
    file: str = field(default="", compare=False)    # nombre del fichero JSON

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
            raise LevelError(f"Nivel mal definido: {exc}") from exc
        parse_level(level.rows)  # valida el mapa
        return level


def _number_from(path, data) -> int | None:
    """Número del nivel: el del JSON si se puede leer y, si no, el del nombre del fichero."""
    try:
        return int(data["number"])
    except (KeyError, TypeError, ValueError):
        m = re.search(r"(\d+)", path.stem)
        return int(m.group(1)) if m else None


def load_levels(directory=LEVELS_DIR) -> list[LevelDef]:
    """Lee todos los ``level_*.json`` de la carpeta, ordenados por número de nivel.

    Un fichero mal escrito (JSON roto, una fila con un espacio de más o de menos...) no tumba
    el juego: el nivel queda en la lista marcado con ``error`` y, al intentar jugarlo, se
    explica en pantalla qué le pasa (ver LevelErrorScene)."""
    levels = []
    for path in sorted(Path(directory).glob("level_*.json")):
        data = None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            level = LevelDef.from_dict(data)
        except (OSError, ValueError) as exc:
            if not isinstance(exc, LevelError):
                exc = LevelError(str(exc), "level_error.file", detail=str(exc))
            number = _number_from(path, data)
            log.error("Nivel %s dañado (%s): %s", number, path.name, exc)
            if number is None:
                continue
            rows = data.get("map") if isinstance(data, dict) else None
            level = LevelDef(number=number, name=f"Nivel {number}",
                             rows=list(rows) if isinstance(rows, list) else [],
                             tutorial=bool(data.get("tutorial")) if isinstance(data, dict)
                             else number == 0, error=exc)
        level.file = path.name
        levels.append(level)
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
    gems: list = field(default_factory=list)     # posiciones (casillas) de las gemas
    boss: tuple | None = None                    # casilla del jefe final (J)


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
        raise LevelError(f"El nivel debe tener al menos {S.ROWS} filas, tiene {len(rows)}",
                         "level_error.few_rows", rows=len(rows), min=S.ROWS)
    height = S.level_height(len(rows))
    solids, oneway, enemies, spawn, star = border_walls(height), [], [], None, None
    bricks, medkits, coins, bombs, gems = [], [], [], [], []
    boss = None
    for r, row in enumerate(rows):
        if not isinstance(row, str):
            raise LevelError(f"Fila {r + 1}: no es un texto", "level_error.row_type", row=r + 1)
        if len(row) != S.COLS:
            extra = len(row) - S.COLS
            key = "level_error.row_long" if extra > 0 else "level_error.row_short"
            raise LevelError(
                f"Fila {r + 1}: tiene {len(row)} caracteres y debe tener {S.COLS} "
                f"({'sobran' if extra > 0 else 'faltan'} {abs(extra)}): {row!r}",
                key, row=r + 1, length=len(row), cols=S.COLS, count=abs(extra), text=row)
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
            elif ch == "G":
                gems.append((x, y))
            elif ch == "J":
                if boss is not None:
                    raise LevelError(f"Fila {r + 1}, columna {c + 1}: solo puede haber un jefe 'J'",
                                     "level_error.two_bosses", row=r + 1, col=c + 1)
                boss = (x, y)
            elif ch != " ":
                raise LevelError(f"Fila {r + 1}, columna {c + 1}: carácter desconocido {ch!r}",
                                 "level_error.unknown_char", row=r + 1, col=c + 1, char=ch)
    if spawn is None:
        raise LevelError("El nivel no tiene inicio de jugador 'P'", "level_error.no_player")
    return LevelData(solids, oneway, spawn, enemies, star, bricks, height, len(rows), medkits,
                     coins, bombs, gems, boss)


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
