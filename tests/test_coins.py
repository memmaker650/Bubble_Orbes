"""Monedas de oro: +100 puntos; 2 o 3 por nivel según su tamaño."""

import json

from bubblequest import settings as S
from bubblequest.level_generator import place_coins
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World
from enemy_helpers import enemy_of  # noqa: E402

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def test_every_level_has_two_or_three_coins_by_size():
    for lv in LEVELS:
        coins = sum(row.count("C") for row in lv.rows)
        if lv.tutorial:
            assert coins == 2                    # el tutorial tiene su propio mapa con 2
        else:
            assert coins == (2 if len(lv.rows) <= 20 else 3), lv.number


def test_coins_sit_on_platforms():
    for lv in LEVELS:
        for r, row in enumerate(lv.rows):
            for c, ch in enumerate(row):
                if ch == "C":
                    assert lv.rows[r + 1][c] == "=", (lv.number, r, c)


def test_coin_gives_100_points_once():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    coin = w.coins[0]
    score = w.score
    w.player.place(coin.rect.x, coin.rect.y)
    step(w, 1)
    assert w.score == score + S.POINTS_COIN == score + 100
    assert coin not in w.coins and w.popups and w.popups[0][3] == "+100"
    step(w, 5)
    assert w.score == score + 100                  # no se cuenta dos veces


def test_popup_fades_away():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    w.player.place(w.coins[0].rect.x, w.coins[0].rect.y)
    step(w, 1)
    step(w, int(S.POPUP_TIME * 60) + 2)
    assert not w.popups


def test_coin_points_count_for_level_points():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    for c in list(w.coins):
        w.player.place(c.rect.x, c.rect.y)
        step(w, 1)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.level_points == 2 * S.POINTS_COIN + S.POINTS_LEVEL


def test_place_coins_keeps_everything_else_and_is_idempotent():
    rows = list(LEVELS[index_of(10)].rows)            # nivel retocado a mano
    plain = [r.replace("C", " ") for r in rows]
    again = place_coins(plain, 10)
    assert all(a == b or (a == " " and b == "C") for ra, rb in zip(plain, again)
               for a, b in zip(ra, rb))
    assert place_coins(again, 10) == again            # si ya tiene monedas, no toca
    assert rows[22] == "==       "                    # tu edición sigue intacta


def test_coin_parsed_from_map():
    rows = ["         "] * 14 + ["  C      ", "    P    "]
    assert parse_level(rows).coins == [S.cell_pos(2, 14)]


def test_taken_coins_stay_taken_after_save():
    from bubblequest import savegame
    w = World(index_of(5), seed=1)
    for e in w.enemies:
        e.alive = False
    taken = w.coins[0]
    w.player.place(taken.rect.x, taken.rect.y)
    step(w, 1)
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert len(r.coins) == 2 and taken.cell not in [c.cell for c in r.coins]
    assert r.score == w.score


# --- "+100" al matar enemigos, en su color ---
import pytest  # noqa: E402

from bubblequest.entities import Bubble, LaserEnemy, TongueEnemy  # noqa: E402


def _pop_enemy(cls, angry=False):
    w = World(1, seed=1)
    e = enemy_of(w, cls)
    e.angry = angry
    b = Bubble(*e.rect.center, 1)
    e.trap()
    b.captured = e
    b._to_float()
    b.age = 1.0
    w.bubbles = [b]
    score = w.score
    w._pop(b)
    return w, e, score


@pytest.mark.parametrize("cls,angry,color", [
    (TongueEnemy, False, S.ENEMY), (TongueEnemy, True, S.ENEMY_ANGRY),
    (LaserEnemy, False, S.ENEMY_BLUE), (LaserEnemy, True, S.ENEMY_BLUE_ANGRY),
])
def test_killing_enemy_shows_points_in_its_color(cls, angry, color):
    w, e, score = _pop_enemy(cls, angry)
    assert w.score == score + S.POINTS_ENEMY
    x, y, age, text, popup_color = w.popups[-1]
    assert text == f"+{S.POINTS_ENEMY}" and popup_color == color
    assert x == e.rect.centerx


def test_coin_popup_is_gold_and_empty_bubble_has_none():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    w.player.place(w.coins[0].rect.x, w.coins[0].rect.y)
    step(w, 1)
    assert w.popups[-1][4] == S.GOLD
    w.popups.clear()
    b = Bubble(*w.player.rect.center, 1)
    w.bubbles = [b]
    w._pop(b)                                     # burbuja vacía: sin texto
    assert not w.popups
