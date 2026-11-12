"""Jefe final del nivel 30: muñeco de anillos el triple de grande que el jugador. Se le hace
daño con burbujas (1) y bombas; ataca agachándose y barriendo el suelo con las manos, y salta
en vertical haciendo temblar el suelo. Derrotado da 5.000 puntos y una lluvia de monedas."""

import json

import pytest

from bubblequest import savegame
from bubblequest import settings as S
from bubblequest.entities import Bomb, Boss, Bubble
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _arena(difficulty="normal"):
    """Nivel 30 sin enemigos normales ni bombas, con el jugador en la plataforma del jefe."""
    w = World(index_of(S.BOSS_LEVEL), seed=1, difficulty=difficulty)
    for e in w.enemies:
        e.alive = False
    w.bombs = []
    w.gems = []
    return w


def _put_player(w, dx, invuln=0.0):
    """Jugador de pie en el piso del jefe, a `dx` px de su centro."""
    b = w.boss
    w.player.place(b.rect.centerx + dx - 14, b.rect.bottom - 32)
    w.player.vx = w.player.vy = 0.0
    w.player.on_ground = True
    w.player.invuln = invuln


def _shoot_at_boss(w, from_left=True):
    b = w.boss
    x = b.rect.left - 30 if from_left else b.rect.right + 30
    bubble = Bubble(x, b.rect.bottom - 30, 1 if from_left else -1)
    w.bubbles.append(bubble)
    return bubble


# --- nivel ---

def test_boss_only_in_level_30_at_the_top_and_level_is_climbed():
    for lv in LEVELS:
        count = sum(row.count("J") for row in lv.rows)
        assert count == (1 if lv.number == S.BOSS_LEVEL else 0), lv.number
    rows = LEVELS[index_of(S.BOSS_LEVEL)].rows
    j_row = next(r for r, row in enumerate(rows) if "J" in row)
    assert j_row <= 5                                     # arriba del todo
    assert "P" in rows[-1] and "S" in rows[0]             # se empieza abajo y se sube
    assert rows[j_row + 1][4] == "="                      # de pie sobre una plataforma


def test_boss_parsed_and_only_one():
    rows = ["         "] * 14 + ["   J     ", "    P    "]
    assert parse_level(rows).boss == S.cell_pos(3, 14)
    with pytest.raises(ValueError):
        parse_level(["         "] * 14 + ["   J J   ", "    P    "])


def test_boss_is_three_times_the_player():
    w = _arena()
    assert w.boss.rect.size == (3 * w.player.rect.width, 3 * w.player.rect.height)


@pytest.mark.parametrize("difficulty", list(S.BOSS_HP))
def test_boss_health_depends_on_difficulty(difficulty):
    assert _arena(difficulty).boss.max_hp == S.BOSS_HP[difficulty]


def test_star_needs_boss_defeated():
    w = _arena()
    w.player.place(*w.star.rect.topleft)
    w.player.invuln = 999
    step(w, 1)
    assert w.state == "playing" and w.message == "star.kill_all"


# --- daño al jefe ---

def test_bubble_hurts_boss_and_is_spent_without_trapping():
    w = _arena()
    _put_player(w, -150, invuln=999)
    bubble = _shoot_at_boss(w)
    hp = w.boss.hp
    step(w, 20)
    assert w.boss.hp == hp - 1
    assert bubble not in w.bubbles and bubble.captured is None
    assert w.boss.hurt_t > 0 or w.boss.hp == hp - 1


def test_bomb_hurts_boss_a_lot():
    w = _arena()
    _put_player(w, -200, invuln=999)
    bomb = Bomb(*S.cell_pos(4, 4))
    bomb.rect.center = (w.boss.rect.centerx + 40, w.boss.rect.bottom - 12)
    w.bombs = [bomb]
    hp = w.boss.hp
    w.explode(bomb)
    assert w.boss.hp == hp - S.BOSS_BOMB_DAMAGE


def test_defeat_gives_5000_points_and_coin_shower():
    w = _arena()
    _put_player(w, -150, invuln=999)
    w.boss.hp = 1
    score = w.score
    _shoot_at_boss(w)
    step(w, 20)
    assert w.boss.dying and w.boss.alive and w.message == "boss.defeated"
    assert w.enemies_left == 1                            # aún cayendo
    step(w, round(S.BOSS_DEATH_TIME / DT) + 2)
    assert not w.boss.alive and w.enemies_left == 0
    assert w.score - score == S.BOSS_POINTS == 5000
    assert len(w.loot) == S.BOSS_COINS
    step(w, 180)                                          # caen y se quedan en el suelo
    assert all(c.on_ground for c in w.loot)
    assert all(w.interior.contains(c.rect) for c in w.loot)


def test_loot_coins_give_coin_points():
    w = _arena()
    w.boss.hit(999)
    w._defeat_boss()
    coin = w.loot[0]
    score = w.score
    w.player.place(coin.rect.x, coin.rect.y)
    w.player.invuln = 999
    step(w, 1)
    assert w.score - score >= S.POINTS_COIN and coin not in w.loot


def test_dying_boss_ignores_more_damage():
    w = _arena()
    w.boss.hit(999)
    assert not w.boss.hit(5) and w.boss.hp == 0


# --- ataques del jefe ---

def _wait_for(w, cond, frames=400, actions=()):
    for _ in range(frames):
        if cond():
            return True
        step(w, 1, actions)
    return cond()


@pytest.mark.parametrize("side", [1, -1])
def test_boss_crouches_and_slaps_towards_the_player(side):
    w = _arena()
    w.boss.cooldown = 0.0
    w.boss.jump_cd = 99
    _put_player(w, side * 95, invuln=999)
    assert _wait_for(w, lambda: w.boss.state == "crouch")
    assert w.boss.side == side
    assert _wait_for(w, lambda: w.boss.attack_rects())
    hand = w.boss.attack_rects()[0]
    assert hand.bottom == w.boss.rect.bottom              # barre el suelo
    assert (hand.centerx - w.boss.rect.centerx) * side > 0


def test_slap_hurts_a_standing_player():
    w = _arena()
    w.boss.cooldown = 0.0
    w.boss.jump_cd = 99
    _put_player(w, 100)
    lives = w.lives
    assert _wait_for(w, lambda: w.state != "playing")
    assert w.state == "dying" and w.lives < lives


def test_jumping_player_dodges_the_slap():
    w = _arena()
    b = w.boss
    b._set("slap")
    b.state_t = S.BOSS_SLAP_OUT + 0.01
    b.side = 1
    hand = b.attack_rects()[0]
    w.player.place(hand.centerx - 14, hand.top - 40)     # en el aire, por encima de la mano
    assert not any(w.player.rect.colliderect(r) for r in b.attack_rects())


def test_angry_boss_can_slap_both_sides():
    w = _arena()
    w.boss.hp = 1
    sides = set()
    for seed in range(40):
        w = _arena()
        w.rng.seed(seed)
        w.boss.rng = w.rng
        w.boss.hp = 1
        w.boss.cooldown = 0.0
        w.boss.jump_cd = 99
        _put_player(w, 95, invuln=999)
        _wait_for(w, lambda: w.boss.state == "crouch", 60)
        sides.add(w.boss.side)
    assert 0 in sides and 1 in sides
    assert len(Boss(0, 0, 1, w.rng).slap_sides()) == 1


def test_boss_jumps_vertically_and_shockwave_hurts_grounded_player():
    w = _arena()
    b = w.boss
    x0 = b.rect.x
    _put_player(w, 120)
    b._set("prep")
    assert _wait_for(w, lambda: b.state == "air", 60)
    top = b.rect.bottom
    _wait_for(w, lambda: b.state != "air", 120)
    assert b.rect.x == x0                                  # salto vertical
    assert b.state == "land"
    assert top - min(top, b.rect.bottom) >= 0
    assert w.state == "dying" or w.player.invuln > 0       # el temblor le ha dado


def test_shockwave_spares_player_in_the_air():
    w = _arena()
    b = w.boss
    _put_player(w, 120)
    w.player.on_ground = False
    lives = w.lives
    b.landed_now = True
    w._boss_shockwave()
    assert w.lives == lives


def test_boss_stays_on_its_platform():
    w = _arena()
    _put_player(w, 0, invuln=999)
    w.player.place(20, w.height - 60)                      # lejos: el jefe pasea
    left, right = w.boss.home
    for _ in range(20 * 60):
        step(w, 1)
        assert w.boss.rect.left >= left - 1 and w.boss.rect.right <= right + 1
        assert w.boss.rect.bottom == S.BORDER + 5 * S.TILE or w.boss.state in ("air", "land")


# --- guardar ---

def test_boss_state_survives_save():
    w = _arena()
    w.boss.hp = 7
    w.boss.facing = 1
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert r.boss.hp == 7 and r.boss.facing == 1 and r.boss.alive


def test_defeated_boss_and_loot_survive_save():
    w = _arena()
    w.boss.hit(999)
    w._defeat_boss()
    w.loot = w.loot[:5]
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert not r.boss.alive and len(r.loot) == 5


def test_boss_texts_are_translated():
    from bubblequest import translations
    for lang in translations.languages():
        assert "boss.name" in lang.texts and "boss.defeated" in lang.texts
