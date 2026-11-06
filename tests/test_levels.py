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
    assert [lv.number for lv in LEVELS] == [0, 1, 2, 3]
    assert (LEVELS_DIR / "level_00.json").exists()


def test_tutorial_uses_same_map_as_level_one():
    tutorial, level1 = LEVELS[0], LEVELS[1]
    assert tutorial.tutorial and not tutorial.enemies_attack
    assert not level1.tutorial and level1.enemies_attack
    assert tutorial.rows == level1.rows


def test_json_files_match_generator():
    """Los JSON del repositorio son los que produce el generador (no se han desincronizado)."""
    for level in LevelGenerator().default_levels():
        path = LEVELS_DIR / LevelGenerator.filename(level)
        assert json.loads(path.read_text(encoding="utf-8")) == level.to_dict()


def test_export_and_reload_roundtrip(tmp_path):
    gen = LevelGenerator()
    custom = gen.make(7, gen.build_map(r2="B     B"), name="Prueba")
    gen.export_all([custom], tmp_path)
    loaded = load_levels(tmp_path)
    assert loaded == [custom]


def test_invalid_map_is_rejected(tmp_path):
    bad = LevelDef(1, "Malo", ["#########"] * S.ROWS).to_dict()
    (tmp_path / "level_01.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="level_01.json"):
        load_levels(tmp_path)
    with pytest.raises(ValueError):
        LevelGenerator().build_map(r2="XXXXXXX")


def test_index_of_level_number():
    assert index_of(0) == 0
    assert index_of(1) == 1
    assert index_of(3) == 3
    assert index_of(99) == 3


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


def test_normal_level_has_no_tutorial():
    w = World(1, seed=1)
    assert w.tutorial_step is None and w.message == ""
