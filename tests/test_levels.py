import json

import pytest

from orbes import settings as S
from orbes.level_generator import LevelGenerator
from orbes.levels import LEVELS, LEVELS_DIR, LevelDef, index_of, load_levels
from orbes.world import TUTORIAL_STEPS, World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


# --- JSON y generador ---

def test_levels_are_loaded_from_json_in_order():
    assert [lv.number for lv in LEVELS] == list(range(21))      # tutorial + 20 niveles
    assert (LEVELS_DIR / "level_00.json").exists()


def test_tutorial_flags():
    tutorial, level1 = LEVELS[0], LEVELS[1]
    assert tutorial.tutorial and not tutorial.enemies_attack
    assert not level1.tutorial and level1.enemies_attack


def test_generator_template_produces_valid_levels():
    # Los JSON se pueden editar a mano, así que no tienen por qué coincidir con la plantilla;
    # lo que sí debe cumplirse es que la plantilla genere niveles válidos.
    gen = LevelGenerator()
    levels = gen.default_levels()
    assert [lv.number for lv in levels] == list(range(21))
    # el tutorial parte del mapa del nivel 1, pero sin monedas
    assert levels[0].rows == [row.replace("C", " ") for row in levels[1].rows]


def test_export_does_not_overwrite_hand_edited_levels(tmp_path):
    gen = LevelGenerator()
    level = gen.default_levels()[1]
    path = gen.export(level, tmp_path)
    path.write_text(path.read_text().replace("Nivel 1", "Editado"))
    assert gen.export_all([level], tmp_path, overwrite=False) == []
    assert "Editado" in path.read_text()
    assert gen.export_all([level], tmp_path, overwrite=True) == [path]
    assert "Editado" not in path.read_text()


def test_export_and_reload_roundtrip(tmp_path):
    gen = LevelGenerator()
    custom = gen.make(7, gen.build_map(r3="B       B"), name="Prueba")
    gen.export_all([custom], tmp_path)
    loaded = load_levels(tmp_path)
    assert loaded == [custom]


def test_invalid_map_is_rejected(tmp_path):
    bad = LevelDef(1, "Malo", ["#########"] * S.ROWS).to_dict()
    (tmp_path / "level_01.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="level_01.json"):
        load_levels(tmp_path)
    with pytest.raises(ValueError):
        LevelGenerator().build_map(r3="XXXXXXXXX")


def test_index_of_level_number():
    assert index_of(0) == 0
    assert index_of(1) == 1
    assert index_of(3) == 3
    assert index_of(4) == 4
    assert index_of(99) == len(LEVELS) - 1


# --- tutorial ---

def test_tutorial_enemies_never_hurt_or_attack():
    w = World(0, seed=1)
    p = w.player
    lives = w.lives
    for e in w.enemies:
        e.cooldown = 0.0
    for _ in range(300):  # 5 s con todos los enemigos encima del jugador
        p.invuln = 0
        for e in w.enemies:
            e.place(*p.rect.topleft)
        step(w, 1)
        assert all(e.attack is None for e in w.enemies)
    assert w.lives == lives and w.state == "playing"


def test_tutorial_guides_through_steps():
    w = World(0, seed=1)
    assert w.message == "tutorial.safe"
    assert w.tutorial_step == "move"
    step(w, 2, {"right"})
    assert w.tutorial_step == "jump"
    step(w, 1)
    step(w, 1, {"jump"})
    assert w.tutorial_step == "jump"         # un salto corto no basta...
    step(w, 6)
    step(w, 1, {"jump"})
    assert w.tutorial_step == "drop"         # ...hace falta la segunda pulsación en el aire
    step(w, 60)
    step(w, 1, {"down"})                     # en el suelo no cuenta: no hay nada que bajar
    assert w.tutorial_step == "drop"
    # De pie en una plataforma fina (la primera que encuentre en el mapa del tutorial)
    plat = w.oneway[0]
    w.player.place(plat.x + 6, plat.top - w.player.rect.height)
    step(w, 10)
    step(w, 1, {"down"})
    assert w.tutorial_step == "bubble"
    step(w, 40)
    step(w, 1, {"bubble"})
    assert w.tutorial_step == "trap"
    w.tutorial_done.update({"trap", "pop"})
    assert w.tutorial_step == "clear"
    for e in w.enemies:
        e.alive = False
    step(w, 1)
    assert w.tutorial_step == "star"
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "won" and w.tutorial_step is None
    assert TUTORIAL_STEPS[-1] == "star"
    assert TUTORIAL_STEPS.index("drop") == TUTORIAL_STEPS.index("jump") + 1


def test_normal_level_has_no_tutorial():
    w = World(1, seed=1)
    assert w.tutorial_step is None and w.message == ""


# --- bordes finos ---

def test_borders_are_thin_and_interior_is_bigger():
    assert S.BORDER <= S.TILE * 0.4          # al menos un 60 % más estrechos
    assert (S.COLS, S.ROWS) == (9, 16)       # antes el interior era 7 x 14
    assert S.FIELD_W == S.COLS * S.TILE + 2 * S.BORDER
    assert all(len(lv.rows) >= S.ROWS and all(len(r) == S.COLS for r in lv.rows)
               for lv in LEVELS)


def test_player_cannot_fall_through_thin_floor():
    w = World(1, seed=1)
    p = w.player
    p.place(S.FIELD_W // 2, S.FLOOR_Y - 200)
    for _ in range(120):
        p.vy = S.MAX_FALL                    # cayendo siempre a la velocidad máxima
        w.player.physics(1 / 30, w.solids, w.oneway)
    assert p.rect.bottom == S.FLOOR_Y


def test_player_cannot_walk_through_thin_side_walls():
    w = World(1, seed=1)
    p = w.player
    p.invuln = 99
    for e in w.enemies:
        e.alive = False
    step(w, 200, {"left"})
    assert p.rect.left == S.BORDER
    step(w, 300, {"right"})
    assert p.rect.right == S.FIELD_W - S.BORDER


def test_inner_blocks_are_solid_obstacles():
    rows = LevelGenerator().build_map()
    rows[14] = "    #    "                       # bloque en mitad del suelo
    from orbes.levels import parse_level
    data = parse_level(rows)
    block = S.cell_pos(4, 14)
    assert any(s.topleft == block and s.size == (S.TILE, S.TILE) for s in data.solids)
