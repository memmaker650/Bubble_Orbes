"""Niveles definidos como mapas de texto de 9 columnas x 16 filas.

  #  muro sólido        =  plataforma (se puede atravesar saltando desde abajo)
  P  inicio del jugador E  enemigo
"""

from dataclasses import dataclass

from pygame import Rect

from . import settings as S

_BASE = [
    "#########",
    "#       #",
    "#{r2}#",
    "# ===== #",
    "#       #",
    "#E     E#",
    "#==   ==#",
    "#       #",
    "#   E   #",
    "# ===== #",
    "#       #",
    "#{r11}#",
    "#==   ==#",
    "#       #",
    "#   P   #",
    "#########",
]


def _build(r2="       ", r11="       "):
    return [row.replace("{r2}", r2).replace("{r11}", r11) for row in _BASE]


LEVELS = [
    _build(),                                  # 3 enemigos
    _build(r2="  E E  "),                      # 5 enemigos
    _build(r2="  E E  ", r11="E     E"),       # 7 enemigos
]


@dataclass
class LevelData:
    solids: list
    oneway: list
    player_spawn: tuple
    enemy_spawns: list


def parse_level(rows) -> LevelData:
    if len(rows) != S.ROWS:
        raise ValueError(f"El nivel debe tener {S.ROWS} filas, tiene {len(rows)}")
    solids, oneway, enemies, spawn = [], [], [], None
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
            elif ch == "E":
                enemies.append((x, y))
    if spawn is None:
        raise ValueError("El nivel no tiene inicio de jugador 'P'")
    return LevelData(solids, oneway, spawn, enemies)
