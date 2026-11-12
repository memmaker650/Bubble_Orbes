"""Generador de niveles: construye mapas a partir de una plantilla y los exporta a JSON.

Para crear los ficheros que falten en ``resources/levels``::

    python -m bubblequest.level_generator

Los niveles que ya existen NO se sobrescriben (se pueden haber editado a mano). Para
regenerarlos todos desde la plantilla, perdiendo esos cambios::

    python -m bubblequest.level_generator --force
"""

import random
import sys

import json
from pathlib import Path

from . import settings as S
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

# Tutorial (nivel 0): mapa propio, más alto que la pantalla (27 filas) para enseñar el scroll
# vertical. Se empieza abajo y la estrella está arriba. Tiene los tres tipos de enemigo
# (inofensivos en el tutorial), de abajo arriba por dificultad: un rojo cerca del inicio para
# practicar atrapar y reventar, el naranja (se agacha para esquivar) y el azul; y monedas.
TUTORIAL_MAP = [
    "         ",   # fila 0 libre: ahí se dibuja la ayuda del tutorial (taparía la estrella)
    "    S    ",
    "         ",
    "  =====  ",
    "         ",
    "E      C ",
    "===   ===",
    "         ",
    "   A     ",
    "  =====  ",
    "         ",
    " C      N",
    "===   ===",
    "         ",
    "         ",
    "  =====  ",
    "         ",
    "         ",
    "===   ===",
    "         ",
    "  E      ",
    "  =====  ",
    "         ",
    "         ",
    "===   ===",
    "         ",
    "    P    ",
]

# Nivel alto (32 filas = 2 pantallas): se empieza abajo y se sube con scroll vertical.
# Plataformas cada 3 filas alternando centro (columnas 2-6) y laterales (0-2 y 6-8); se pasa
# de unas a otras por las columnas 2 y 6. Los ladrillos (L) sirven de parapeto: bloquean el
# paso, la vista de los enemigos, la lengua, el láser y las burbujas.
TALL_LEVEL = [
    "    S    ",
    "  N L E  ",
    "  =====  ",
    "         ",
    "E       L",
    "===   ===",
    "         ",
    "    L    ",
    "  =====  ",
    "         ",
    "N       E",
    "===   ===",
    "         ",
    "   L N   ",
    "  =====  ",
    "         ",
    "LE      N",
    "===   ===",
    "         ",
    "  E L    ",
    "  =====  ",
    "         ",
    "E       N",
    "===   ===",
    "         ",
    "    L    ",
    "  =====  ",
    "         ",
    "         ",
    "===   ===",
    "         ",
    "    P    ",
]


# --- Niveles procedurales (5 a 20) ---
# Plataformas centrales y laterales: todas incluyen las columnas 2 y 6, por donde se pasa de
# unas a otras (y que nunca se tapan con ladrillos), así que siempre se puede subir.
CENTER_PLATFORMS = ("  =====  ", " ======= ", "  == ==  ")
SIDE_PLATFORMS = ("===   ===", "=== = ===", "==== ====")
TOP_PLATFORMS = ("  =====  ", " ======= ")     # la de la estrella: sin hueco en el centro
PATH_COLS = (2, 6)
FIRST_GENERATED, LAST_GENERATED = 5, 30


def coin_count(rows) -> int:
    """2 monedas en niveles de una pantalla; 3 en los más altos."""
    return 2 if len(rows) <= 20 else 3


def place_coins(rows, number) -> list[str]:
    """Añade monedas (C) al mapa encima de plataformas, repartidas en altura y siempre en
    huecos libres. Respeta todo lo demás (sirve también para niveles retocados a mano).
    Siempre las mismas para el mismo mapa y número de nivel. Si ya tiene monedas, no toca."""
    if any("C" in row for row in rows):
        return list(rows)
    rng = random.Random(number * 104729)
    grid = [list(row) for row in rows]
    spots = [(r, c) for r in range(len(grid) - 1) for c in range(9)
             if grid[r][c] == " " and grid[r + 1][c] == "="]
    rng.shuffle(spots)
    want = coin_count(rows)
    gap = max(2, len(rows) // (want + 1) // 2)        # separación mínima en filas
    chosen = []
    for r, c in spots:
        if len(chosen) == want:
            break
        if all(abs(r - cr) >= gap for cr, _ in chosen):
            chosen.append((r, c))
    for r, c in chosen:
        grid[r][c] = "C"
    return ["".join(row) for row in grid]


def place_boss(rows, number) -> list[str]:
    """En el nivel del jefe (S.BOSS_LEVEL) pone la J sobre la plataforma más alta, en el
    centro, y deja libre su arena (las filas de encima, salvo la estrella). Si ya tiene jefe o
    no es su nivel, no toca nada."""
    if number != S.BOSS_LEVEL or any("J" in row for row in rows):
        return list(rows)
    grid = [list(row) for row in rows]
    # Primera plataforma central con sitio encima para el jefe (mide unas 3 filas)
    top = next(r for r in range(4, len(grid)) if grid[r][4] == "=")
    for r in range(top - 3, top):
        for c in range(9):
            if grid[r][c] not in "S= ":
                grid[r][c] = " "
    grid[top - 1][4] = "J"
    return ["".join(row) for row in grid]


# --- Dónde empieza el jugador y dónde está la estrella ---
# "up": abajo -> estrella arriba     "down": arriba del todo -> estrella abajo del todo
# "middle_up" / "middle_down": a mitad del nivel -> estrella arriba / abajo
LAYOUTS = ("up", "down", "middle_up", "middle_down")
SAFE_ROWS = 4                  # sin enemigos a menos de estas filas del inicio del jugador


def layout_for(number) -> str:
    """Disposición de los niveles generados: rotan las cuatro (5 sube, 6 baja, 7 y 8 desde
    la mitad...). Los niveles 1-4 empiezan siempre abajo."""
    if number < FIRST_GENERATED or number == S.BOSS_LEVEL:   # al jefe final se sube
        return "up"
    return LAYOUTS[(number - FIRST_GENERATED) % len(LAYOUTS)]


def set_layout(rows, layout, number) -> list[str]:
    """Coloca el inicio (P) y la estrella (S) según `layout`, sobre cualquier mapa (también
    retocado a mano): solo mueve P y S y, si algún enemigo queda pegado al nuevo inicio, lo
    pasa a otra plataforma. Reglas: si empieza arriba del todo, la estrella está abajo del
    todo; si empieza a mitad, la estrella puede estar arriba o abajo."""
    if layout not in LAYOUTS:
        raise ValueError(f"Disposición desconocida: {layout}")
    grid = [list(row) for row in rows]
    n = len(grid)
    for row in grid:                                   # quitar P y S de donde estén
        for c, ch in enumerate(row):
            if ch in "PS":
                row[c] = " "
    top, bottom = (0, 4), (n - 1, 4)                   # arriba del todo / suelo, en el centro

    def on_platform(r, c):
        return 0 <= r < n - 1 and grid[r][c] == " " and grid[r + 1][c] == "="

    if layout == "up":
        start, star = bottom, top
    elif layout == "down":
        start, star = top, bottom
    else:
        # A mitad: encima de la plataforma más cercana al centro del nivel (columna libre
        # lo más centrada posible)
        candidates = [(abs(r - n // 2), abs(c - 4), r, c)
                      for r in range(n - 1) for c in range(9) if on_platform(r, c)]
        if not candidates:
            raise ValueError("El mapa no tiene plataformas donde empezar a mitad")
        _, _, r, c = min(candidates)
        start = (r, c)
        star = top if layout == "middle_up" else bottom
    for (r, c), ch in ((start, "P"), (star, "S")):
        if grid[r][c] not in " PS":                    # el sitio debe estar libre
            raise ValueError(f"Casilla ocupada para {ch}: fila {r}, columna {c}")
        grid[r][c] = ch

    # Enemigos demasiado cerca del inicio: a otra plataforma, lejos (siempre los mismos)
    rng = random.Random(number * 31337)
    near = [(r, c) for r in range(n) for c in range(9)
            if grid[r][c] in "EAN" and abs(r - start[0]) <= SAFE_ROWS]
    far = [(r, c) for r in range(n - 1) for c in range(9)
           if on_platform(r, c) and abs(r - start[0]) > SAFE_ROWS + 2 and (r, c) != star]
    rng.shuffle(far)
    for (r, c), (fr, fc) in zip(near, far):
        grid[fr][fc], grid[r][c] = grid[r][c], " "
    result = ["".join(row) for row in grid]
    parse_level(result)
    return result


# --- Bombas (niveles 10+) ---
FIRST_BOMB_LEVEL = 10


def bomb_count(rows, number) -> int:
    """Ninguna antes del nivel 10; 1 en niveles de hasta 45 filas y 2 en los más altos."""
    if number < FIRST_BOMB_LEVEL:
        return 0
    return 1 if len(rows) <= 45 else 2


def place_bombs(rows, number) -> list[str]:
    """Añade bombas (B) encima de plataformas, donde más enemigos quedan dentro de su radio
    de explosión, lejos del inicio del jugador y separadas entre sí. Respeta todo lo demás
    (sirve para niveles retocados a mano). Si ya tiene bombas, no toca nada."""
    want = bomb_count(rows, number)
    if want == 0 or any("B" in row for row in rows):
        return list(rows)
    grid = [list(row) for row in rows]
    n = len(grid)
    p_row = next(r for r, row in enumerate(rows) if "P" in row)
    enemies = [(r, c) for r in range(n) for c in range(9) if grid[r][c] in "EAN"]
    reach = S.BOMB_RADIUS / S.TILE                     # radio en casillas

    def hits(r, c):
        return sum(1 for er, ec in enemies if (er - r) ** 2 + (ec - c) ** 2 <= reach ** 2)

    rng = random.Random(number * 4099)
    spots = [(r, c) for r in range(n - 1) for c in range(9)
             if grid[r][c] == " " and grid[r + 1][c] == "=" and abs(r - p_row) > SAFE_ROWS + 2]
    rng.shuffle(spots)                                 # desempate, siempre igual
    spots.sort(key=lambda rc: -hits(*rc))
    chosen = []
    for r, c in spots:
        if len(chosen) == want:
            break
        if all(abs(r - cr) >= 8 for cr, _ in chosen):
            chosen.append((r, c))
    for r, c in chosen:
        grid[r][c] = "B"
    result = ["".join(row) for row in grid]
    parse_level(result)
    return result


ENEMIES_PER_ROW = 25 / 67      # densidad del nivel 20 (25 enemigos en 67 filas)


def level_rows(number) -> int:
    """Alto de los niveles generados: +3 filas por nivel hasta el 25 (22 -> 82) y +6 desde
    el 26 (88 -> 112)."""
    if number <= 25:
        return 22 + 3 * (number - FIRST_GENERATED)
    return level_rows(25) + 6 * (number - 25)


def _progress(number):
    """0 en el nivel 5 y 1 en el 20 (más allá sigue creciendo). Fijo sobre ese tramo para que
    los niveles 5-20 no cambien al añadir niveles nuevos."""
    return (number - FIRST_GENERATED) / (20 - FIRST_GENERATED)


# --- Tipos de enemigo (niveles 5+) ---
FIRST_LASER_LEVEL = 5          # los azules (ojos rojos, láser) aparecen desde aquí...
KNIFE_SHARE = 0.25             # ...el resto, rojos y algunos naranjas


def laser_count(enemies, number) -> int:
    """Azules del nivel: 1 en el 5, 2 en el 6... uno más por nivel, como mucho la mitad."""
    if number < FIRST_LASER_LEVEL:
        return 0
    return min(number - FIRST_LASER_LEVEL + 1, enemies // 2)


def assign_enemy_kinds(rows, number) -> list[str]:
    """Decide el tipo de cada enemigo (E rojo, A azul, N naranja) sin moverlo de su casilla:
    `laser_count` azules repartidos por todo el nivel y el resto rojos con algunos naranjas.
    Sirve para niveles retocados a mano. Siempre igual para el mismo mapa y número."""
    if number < FIRST_LASER_LEVEL:
        return list(rows)
    grid = [list(row) for row in rows]
    cells = sorted((r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch in "EAN")
    n = len(cells)
    lasers = laser_count(n, number)
    laser_idx = {min(n - 1, int((i + 0.5) * n / lasers)) for i in range(lasers)} if lasers else set()
    rng = random.Random(number * 7907)
    for i, (r, c) in enumerate(cells):
        if i in laser_idx:
            grid[r][c] = "A"
        else:
            grid[r][c] = "N" if rng.random() < KNIFE_SHARE else "E"
    return ["".join(row) for row in grid]


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
        return [
            self.make(0, self.tutorial_map(), tutorial=True, enemies_attack=False),
            # Niveles 1 y 2: el enemigo naranja (cuchillo) en lugar de los azules (láser)
            self.make(1, place_coins(self.build_map(m="N"), 1)),           # 2 rojos + 1 naranja
            self.make(2, place_coins(self.build_map(r3="   E N   ", m="N"), 2)),
            self.make(3, place_coins(self.build_map(r3="   N N   ", r12="E       N"), 3)),
            self.make(4, place_coins(self.tall_map(), 4), name="La torre"),
        ] + [self.make(n, self.generated_map(n)) for n in range(FIRST_GENERATED, LAST_GENERATED + 1)]

    def generated_map(self, number) -> list[str]:
        """Nivel procedural: más alto, con más enemigos y más láseres según avanza; con una
        cantidad variable de ladrillos protectores. Siempre igual para el mismo número."""
        rng = random.Random(number * 7919)
        k = _progress(number)
        rows = level_rows(number)                          # 22 ... 112 filas
        grid = [[" "] * 9 for _ in range(rows)]
        grid[0][4] = "S"                                   # estrella arriba del todo
        grid[rows - 1][4] = "P"                            # el jugador empieza abajo

        # Plataformas cada 3 filas desde el suelo; la de más arriba (fila 2..4), central.
        plat_rows = list(range(rows - 3, 1, -3))
        top = plat_rows[-1]
        for r in plat_rows:
            center = ((top - r) // 3) % 2 == 0            # alternan desde arriba: centro, lado...
            if r == top:
                pattern = rng.choice(TOP_PLATFORMS)
            else:
                pattern = rng.choice(CENTER_PLATFORMS if center else SIDE_PLATFORMS)
            grid[r] = list(pattern)

        # Huecos encima de las plataformas (donde se apoyan enemigos y ladrillos)
        spots = [(r - 1, c) for r in plat_rows for c in range(9) if grid[r][c] == "="]
        spots = [(r, c) for r, c in spots if r >= 1 and r != rows - 1 and grid[r][c] == " "]
        rng.shuffle(spots)

        # Ladrillos: cantidad variable (algunos niveles con muchos, otros con pocos), con
        # tendencia a menos en los niveles finales. Nunca en las columnas de paso ni junto a
        # la estrella.
        many = rng.random() < 0.5
        share = (0.30 if many else 0.12) * (1.0 - 0.5 * min(k, 1.0))   # desde el 20, estable
        n_bricks = max(1, round(len(plat_rows) * 3 * share))
        bricks = [(r, c) for r, c in spots
                  if c not in PATH_COLS and not (r == top - 1 and 3 <= c <= 5)][:n_bricks]
        for r, c in bricks:
            grid[r][c] = "L"

        # Enemigos: cada vez más, y más azules (láser)
        free = [(r, c) for r, c in spots if (r, c) not in bricks and r < rows - 4]
        if number <= 20:
            n_enemies = min(len(free), round(7 + 18 * k))
        else:   # niveles 21+: misma densidad que el 20 (enemigos por fila), no más apiñados
            n_enemies = min(len(free), round(len(grid) * ENEMIES_PER_ROW))
        laser_share = 0.35 + 0.25 * k
        for r, c in free[:n_enemies]:
            grid[r][c] = "A" if rng.random() < laser_share else "E"

        # Botiquines (recuperan un corazón): uno más cada ~15 filas, repartidos en altura.
        # Se colocan al final para no alterar el resto del nivel.
        n_medkits = 1 + (rows - 22) // 15                 # 1 ... 4
        medkits = []
        for r, c in free[n_enemies:]:
            if len(medkits) == n_medkits:
                break
            if all(abs(r - mr) >= 6 for mr, _ in medkits):
                medkits.append((r, c))
                grid[r][c] = "H"

        result = place_coins(["".join(row) for row in grid], number)   # al final: no altera lo demás
        result = set_layout(result, layout_for(number), number)       # inicio y estrella
        result = assign_enemy_kinds(result, number)                   # rojos, azules, naranjas
        result = place_bombs(result, number)                          # bombas (nivel 10+)
        result = place_boss(result, number)                           # jefe final (nivel 30)
        parse_level(result)
        return result

    def tutorial_map(self) -> list[str]:
        rows = list(TUTORIAL_MAP)
        parse_level(rows)
        return rows

    def tall_map(self) -> list[str]:
        rows = list(TALL_LEVEL)
        parse_level(rows)
        return rows

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
