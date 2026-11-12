"""Gemas: una en los niveles 10 (rubí), 15 (esmeralda), 20 (amarilla), 25 (aguamarina) y
30 (blanca). Son obligatorias: la estrella no termina el nivel hasta cogerla."""

import json

import pytest

from bubblequest import savegame
from bubblequest import settings as S
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World

DT = 1 / 60
EXPECTED = {10: "ruby", 15: "emerald", 20: "yellow", 25: "aquamarine", 30: "white"}


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _cleared(number):
    """Nivel `number` sin enemigos y con el jugador invulnerable."""
    w = World(index_of(number), seed=1)
    for e in w.enemies:
        e.alive = False
    if w.boss is not None:      # el jefe final del 30 (ver test_boss.py)
        w.boss.alive = False
    w.player.invuln = 999
    return w


def _touch(w, rect):
    w.player.place(rect.x, rect.y)
    w.player.vx = w.player.vy = 0.0
    step(w, 1)


# --- niveles ---

def test_gem_parsed_from_map():
    rows = ["         "] * 14 + ["   G     ", "    P    "]
    assert parse_level(rows).gems == [S.cell_pos(3, 14)]


def test_one_gem_in_levels_10_15_20_25_30_and_none_elsewhere():
    for lv in LEVELS:
        count = sum(row.count("G") for row in lv.rows)
        assert count == (1 if lv.number in EXPECTED else 0), lv.number
    assert S.GEM_LEVELS == EXPECTED


def test_gems_sit_on_platforms():
    for n in EXPECTED:
        rows = LEVELS[index_of(n)].rows
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "G":
                    assert rows[r + 1][c] in "=#L", (n, r, c)


@pytest.mark.parametrize("number,kind", EXPECTED.items())
def test_gem_color_depends_on_level(number, kind):
    w = World(index_of(number), seed=1)
    assert [g.kind for g in w.gems] == [kind]


# --- obligatoria ---

def test_star_needs_the_gem():
    w = _cleared(10)
    _touch(w, w.star.rect)
    assert w.state == "playing" and not w.star.lit
    assert w.message == "star.gem_needed"


def test_taking_gem_then_star_wins():
    w = _cleared(10)
    _touch(w, w.gems[0].rect)
    assert w.gems == [] and w.message == "gem.taken.ruby"
    step(w, 30)
    _touch(w, w.star.rect)
    assert w.state == "won"


def test_enemies_message_comes_before_gem_message():
    w = World(index_of(10), seed=1)
    w.player.invuln = 999
    _touch(w, w.star.rect)
    assert w.message == "star.kill_all"


def test_level_without_gem_is_unchanged():
    w = _cleared(11)
    assert w.gems == []
    _touch(w, w.star.rect)
    assert w.state == "won"


# --- gemas conseguidas ---

def test_gems_owned_follow_progress():
    assert World(index_of(9), seed=1).gems_owned == []
    w = World(index_of(10), seed=1)
    assert w.gems_owned == []
    w.player.invuln = 999
    _touch(w, w.gems[0].rect)
    assert w.gems_owned == ["ruby"]
    assert World(index_of(26), seed=1).gems_owned == ["ruby", "emerald", "yellow",
                                                      "aquamarine"]


def test_level_30_needs_white_gem_to_finish_and_then_has_all_five():
    w = _cleared(30)
    assert w.gems_owned == ["ruby", "emerald", "yellow", "aquamarine"]
    _touch(w, w.star.rect)
    assert w.state == "playing"
    _touch(w, w.gems[0].rect)
    assert w.message == "gem.taken.white"
    assert w.gems_owned == list(EXPECTED.values())
    step(w, 30)
    _touch(w, w.star.rect)
    assert w.state == "won"


# --- guardar ---

def test_taken_gem_stays_taken_after_save():
    w = _cleared(15)
    _touch(w, w.gems[0].rect)
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert r.gems == [] and "emerald" in r.gems_owned


def test_untaken_gem_is_kept_after_save():
    w = World(index_of(15), seed=1)
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert [g.cell for g in r.gems] == [g.cell for g in w.gems]


def test_gem_messages_are_translated():
    from bubblequest import translations
    for lang in translations.languages():
        for kind in EXPECTED.values():
            assert f"gem.taken.{kind}" in lang.texts
        assert "star.gem_needed" in lang.texts
