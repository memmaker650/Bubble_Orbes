"""Enemigo naranja (N): cuchillada cuerpo a cuerpo y se agacha para esquivar burbujas."""

import pytest

from bubblequest import settings as S
from bubblequest.entities import Bubble, KnifeEnemy
from bubblequest.levels import LEVELS, index_of, parse_level
from bubblequest.world import World

DT = 1 / 60
FLOOR_Y = S.FLOOR_Y - 32


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _duel(gap, chance=None, monkeypatch=None):
    """Jugador a la izquierda y un enemigo naranja a `gap` px, mirándolo."""
    w = World(1, seed=1)
    e = next(x for x in w.enemies if isinstance(x, KnifeEnemy))
    w.enemies = [e]
    p = w.player
    p.place(60, FLOOR_Y)
    e.place(60 + 28 + gap, FLOOR_Y)
    e.direction, e.cooldown, e.jump_cd, e.coyote = -1, 0.0, 99, S.COYOTE_TIME
    if chance is not None:
        monkeypatch.setattr(S, "DODGE_CHANCE", chance)
    return w, e, p


# --- niveles ---

def test_levels_one_and_two_have_knife_enemies_instead_of_lasers():
    for n in (1, 2):
        rows = LEVELS[index_of(n)].rows
        assert sum(r.count("N") for r in rows) == n           # 1 en el nivel 1, 2 en el 2
        assert not any("A" in r for r in rows)
        kinds = {e.kind for e in World(index_of(n), seed=1).enemies}
        assert kinds == {"tongue", "knife"}


def test_n_is_parsed_as_knife_enemy():
    rows = ["         "] * 14 + ["   N     ", "    P    "]
    data = parse_level(rows)
    assert data.enemy_spawns == [(*S.cell_pos(3, 14), "N")]


def test_orange_color():
    assert S.enemy_color("knife") == S.ENEMY_ORANGE
    assert S.enemy_color("knife", angry=True) == S.ENEMY_ORANGE_ANGRY


# --- cuchillada ---

def test_stab_phases_out_hold_in_then_recharge():
    w, e, p = _duel(gap=20)
    p.invuln = 99
    step(w, 1)
    assert e.stab_phase == "out" and 0 < e.stab_extension < 1
    step(w, round(S.STAB_OUT * 60) + 1)
    assert e.stab_phase == "hold" and e.stab_extension == 1
    step(w, round(S.STAB_HOLD * 60) + 1)
    assert e.stab_phase == "in" and 0 < e.stab_extension < 1   # retrae
    for _ in range(round(S.STAB_IN * 60) + 5):
        step(w, 1)
        if e.attack is None:
            break
    assert e.attack is None                                    # la cuchillada ha terminado
    assert e.cooldown == pytest.approx(S.KNIFE_COOLDOWN * w.rules["cooldown"], abs=0.02)


def test_stab_hits_close_player_for_a_full_heart():
    w, e, p = _duel(gap=20)
    lives = w.lives
    assert not p.rect.colliderect(e.rect)                     # no se tocan: es la cuchillada
    for _ in range(30):
        step(w, 1)
        if w.lives != lives:
            break
    assert w.lives == lives - S.DAMAGE_ATTACK and w.state == "dying"


def test_knife_reach_matches_drawn_tip():
    w, e, p = _duel(gap=20)
    e.attack, e.attack_t = "stab", S.STAB_OUT + 0.01          # estirado
    r = e.attack_rect()
    assert r.width == round(S.KNIFE_REST + S.KNIFE_REACH)
    assert r.right == e.rect.left and r.left == e.rect.left - r.width


def test_no_stab_when_player_is_not_close():
    w, e, p = _duel(gap=100)
    p.invuln = 99
    step(w, 30)
    assert e.attack is None
    e.direction = 1                                            # de espaldas
    w2, e2, p2 = _duel(gap=20)
    e2.direction = 1
    step(w2, 5)
    assert e2.attack is None


# --- agacharse ---

def _shoot_at(w, e, p):
    p.facing = 1
    p.shoot_cd = 0
    w._prev = set()
    step(w, 1, {"bubble"})


def test_crouches_to_dodge_bubble_and_is_not_trapped(monkeypatch):
    w, e, p = _duel(gap=120, chance=1.0, monkeypatch=monkeypatch)
    p.invuln = 99
    e.cooldown = 99                                            # que no ataque en la prueba
    _shoot_at(w, e, p)
    for _ in range(40):
        step(w, 1)
        if e.crouching:
            break
    assert e.crouching
    step(w, 30)
    assert e.state == "walk"                                   # la burbuja le pasó por encima
    step(w, round(S.CROUCH_TIME * 60))
    assert not e.crouching


def test_cannot_crouch_again_right_away_so_second_bubble_traps(monkeypatch):
    w, e, p = _duel(gap=120, chance=1.0, monkeypatch=monkeypatch)
    p.invuln = 99
    e.cooldown = 99
    _shoot_at(w, e, p)
    for _ in range(60):
        step(w, 1)
        if e.crouching:
            break
    while e.crouching:
        step(w, 1)
    assert e.crouch_cd > 0                                      # aún recuperándose
    e.place(p.rect.right + 60, FLOOR_Y)
    _shoot_at(w, e, p)
    step(w, 20)
    assert e.state == "trapped"


def test_sometimes_does_not_dodge(monkeypatch):
    w, e, p = _duel(gap=120, chance=0.0, monkeypatch=monkeypatch)
    p.invuln = 99
    e.cooldown = 99
    _shoot_at(w, e, p)
    step(w, 30)
    assert not e.crouching and e.state == "trapped"


def test_crouching_enemy_does_not_attack_or_move():
    w, e, p = _duel(gap=20)
    p.invuln = 99
    e.crouch_t = S.CROUCH_TIME
    x = e.rect.x
    step(w, 10)
    assert e.attack is None and e.rect.x == x


def test_crouch_state_survives_save():
    from bubblequest import savegame
    w = World(1, seed=1)
    e = next(x for x in w.enemies if isinstance(x, KnifeEnemy))
    e.crouch_t, e.crouch_cd = 0.3, 1.0
    r = savegame.restore(savegame.snapshot(w))
    re = r.enemies[w.enemies.index(e)]
    assert re.crouch_t == pytest.approx(0.3) and re.crouch_cd == pytest.approx(1.0)


def test_killed_knife_enemy_shows_orange_points():
    w = World(1, seed=1)
    e = next(x for x in w.enemies if isinstance(x, KnifeEnemy))
    b = Bubble(*e.rect.center, 1)
    e.trap()
    b.captured = e
    b._to_float()
    w.bubbles = [b]
    w._pop(b)
    assert w.popups[-1][4] == S.ENEMY_ORANGE and w.ghosts[-1].kind == "knife"


def test_dodges_even_if_bubble_was_first_seen_while_in_the_air(monkeypatch):
    """Regresión: si la burbuja llegaba mientras no tenía los pies en el suelo, ya no volvía
    a intentar agacharse con esa burbuja aunque aterrizase a tiempo."""
    w, e, p = _duel(gap=120, chance=1.0, monkeypatch=monkeypatch)
    p.invuln = 99
    e.cooldown = 99
    e.coyote = 0.0                                             # justo en el aire
    _shoot_at(w, e, p)
    for _ in range(40):
        step(w, 1)
        if e.crouching:
            break
    assert e.crouching
    step(w, 30)
    assert e.state == "walk"
