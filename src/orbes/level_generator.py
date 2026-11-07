"""Generador de niveles: construye mapas a partir de una plantilla y los exporta a JSON.

Para crear los ficheros que falten en ``resources/levels``::

    python -m orbes.level_generator

Los niveles que ya existen NO se sobrescriben (se pueden haber editado a mano). Para
regenerarlos todos desde la plantilla, perdiendo esos cambios::

    python -m orbes.level_generator --force
"""

import sys

import json
from pathlib import Path

from .levels import LEVELS_DIR, LevelDef, parse_level

# Interior del nivel (9 x 16). Los bordes se añaden solos. Plataformas cada 3 filas
# (lo que alcanza un salto): filas 13, 10, 7 y 4; la estrella arriba, en la fila 1.
TEMPLATE = [
    "         ",
    "    S    ",
    "         ",
    "{r3}",
    "  =====  ",
    "         ",
    "E       E",
    "===   ===",
    "         ",
    "    {m}    ",
    "  =====  ",
    "         ",
    "{r12}",
    "===   ===",
    "         ",
    "    P    ",
]
EMPTY = " " * 9


class LevelGenerator:
    """Crea niveles a partir de una plantilla con huecos ({r3}, {r12}, {m}) y los guarda en JSON."""

    def __init__(self, template=None):
        self.template = list(template or TEMPLATE)

    def build_map(self, r3=EMPTY, r12=EMPTY, m="E") -> list[str]:
        """Rellena los huecos de la plantilla: fila 3, fila 12 y el enemigo del centro."""
        rows = [row.replace("{r3}", r3).replace("{r12}", r12).replace("{m}", m)
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
            self.make(2, self.build_map(r3="   E B   ", m="B")),            # 3 rojos + 2 azules
            self.make(3, self.build_map(r3="   B B   ", r12="E       B")),  # 4 rojos + 3 azules
        ]

    @staticmethod
    def filename(level: LevelDef) -> str:
        return f"level_{level.number:02d}.json"

    def export(self, level: LevelDef, directory=LEVELS_DIR, overwrite=True) -> Path | None:
        """Guarda el nivel en JSON. Con ``overwrite=False`` no toca un fichero que ya exista
        (y devuelve None)."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.filename(level)
        if path.exists() and not overwrite:
            return None
        path.write_text(json.dumps(level.to_dict(), ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        return path

    def export_all(self, levels=None, directory=LEVELS_DIR, overwrite=True) -> list[Path]:
        """Exporta los niveles; devuelve las rutas escritas (sin las que se han respetado)."""
        written = [self.export(level, directory, overwrite)
                   for level in (levels or self.default_levels())]
        return [p for p in written if p is not None]


if __name__ == "__main__":
    force = "--force" in sys.argv[1:]
    gen = LevelGenerator()
    written = gen.export_all(overwrite=force)
    for p in written:
        print(f"Exportado {p}")
    skipped = len(gen.default_levels()) - len(written)
    if skipped:
        print(f"{skipped} nivel(es) ya existían y no se han tocado (usa --force para regenerarlos)")
