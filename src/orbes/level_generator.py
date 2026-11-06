"""Generador de niveles: construye mapas a partir de una plantilla y los exporta a JSON.

Para regenerar los ficheros de ``resources/levels``::

    python -m orbes.level_generator
"""

import json
from pathlib import Path

from .levels import LEVELS_DIR, LevelDef, parse_level

TEMPLATE = [
    "#########",
    "#   S   #",
    "#{r2}#",
    "# ===== #",
    "#       #",
    "#E     E#",
    "#==   ==#",
    "#       #",
    "#   {m}   #",
    "# ===== #",
    "#       #",
    "#{r11}#",
    "#==   ==#",
    "#       #",
    "#   P   #",
    "#########",
]
EMPTY = "       "


class LevelGenerator:
    """Crea niveles a partir de una plantilla con huecos ({r2}, {r11}, {m}) y los guarda en JSON."""

    def __init__(self, template=None):
        self.template = list(template or TEMPLATE)

    def build_map(self, r2=EMPTY, r11=EMPTY, m="E") -> list[str]:
        """Rellena los huecos de la plantilla: fila 2, fila 11 y el enemigo del centro."""
        rows = [row.replace("{r2}", r2).replace("{r11}", r11).replace("{m}", m)
                for row in self.template]
        parse_level(rows)  # falla aquí si el mapa resultante no es válido
        return rows

    def make(self, number, rows, name=None, tutorial=False, enemies_attack=True) -> LevelDef:
        name = name or ("Tutorial" if tutorial else f"Nivel {number}")
        return LevelDef(number, name, rows, tutorial, enemies_attack)

    def default_levels(self) -> list[LevelDef]:
        """Niveles del juego. El tutorial (0) usa el mismo mapa que el nivel 1."""
        level1 = self.build_map(m="B")                                  # 2 rojos + 1 azul
        return [
            self.make(0, level1, tutorial=True, enemies_attack=False),
            self.make(1, level1),
            self.make(2, self.build_map(r2="  E B  ", m="B")),          # 3 rojos + 2 azules
            self.make(3, self.build_map(r2="  B B  ", r11="E     B")),  # 4 rojos + 3 azules
        ]

    @staticmethod
    def filename(level: LevelDef) -> str:
        return f"level_{level.number:02d}.json"

    def export(self, level: LevelDef, directory=LEVELS_DIR) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.filename(level)
        path.write_text(json.dumps(level.to_dict(), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return path

    def export_all(self, levels=None, directory=LEVELS_DIR) -> list[Path]:
        return [self.export(level, directory) for level in (levels or self.default_levels())]


if __name__ == "__main__":
    for p in LevelGenerator().export_all():
        print(f"Exportado {p}")
