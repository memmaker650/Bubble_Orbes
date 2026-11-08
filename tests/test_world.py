import pytest

from orbes import settings as S
from orbes.levels import LEVELS, parse_level
from orbes.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


@pytest.mark.parametrize("i", range(len(LEVELS)))
def test_levels_parse(i):
    data = parse_level(LEVELS[i].rows)
    assert data.player_spawn is not None
    assert len(data.enemy_spawns) >= 1


def test_player_stands_on_floor_and_jumps():
    w = World(1, seed=1)
    step(w, 30)
    assert w.player.coyote > 0
    y0 = w.player.rect.y
    step(w, 1, {"jump"})
    step(w, 8)
    assert w.player.rect.y < y0 - 40
    step(w, 120)
    assert abs(w.player.rect.y - y0) <= 1  # vuelve a aterrizar


def test_player_can_reach_first_platform():
    w = World(1, seed=1)
    p = w.player
    # En el suelo, justo bajo la plataforma lateral de la fila 13 (columnas 0-2).
    x, platform_y = S.cell_pos(1, 13)
    p.place(x, S.FLOOR_Y - p.rect.height)
    step(w, 10)
    assert p.rect.bottom == S.FLOOR_Y
    step(w, 1, {"jump"})
    step(w, 80)
    # Atraviesa la plataforma desde abajo y aterriza encima de ella.
    assert p.rect.bottom == platform_y


def test_bubble_traps_then_pop_scores():
    w = World(1, seed=1)
    e = w.enemies[0]
    p = w.player
    e.place(p.rect.x + 90, p.rect.y)
    e.direction = 1
    step(w, 3, {"bubble"})
    step(w, 40)
    assert e.state == "trapped"
    bubble = w.bubbles[0]
    assert bubble.captured is e

    step(w, 20)  # la burbuja ya está "armada"
    p.place(*bubble.rect.topleft)
    step(w, 1)
    assert not e.alive
    assert w.score >= S.POINTS_ENEMY


def test_trapped_enemy_escapes_angry():
    w = World(1, seed=1)
    e = w.enemies[0]
    e.place(w.player.rect.x + 90, w.player.rect.y)
    e.direction = 1
    step(w, 3, {"bubble"})
    step(w, 40)
    w.bubbles[0].life = 0.01
    step(w, 3)
    assert e.state == "walk" and e.angry and not w.bubbles


def _until_not_dying(w, limit=600):
    for _ in range(limit):
        if w.state != "dying":
            return
        step(w, 1)
    raise AssertionError("la animación de muerte no termina")


def test_enemy_contact_costs_life_then_game_over():
    w = World(1, lives=2, seed=1)
    e = w.enemies[0]
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.lives == 1 and w.state == "dying"     # animación de muerte antes de reaparecer
    _until_not_dying(w)
    assert w.state == "playing" and w.player.invuln > 0 and not w.player.dead
    w.player.invuln = 0
    e.place(*w.player.rect.topleft)
    step(w, 1)
    assert w.lives == 0 and w.state == "dying"
    _until_not_dying(w)
    assert w.state == "lost"


def test_every_level_has_star():
    for level in LEVELS:
        assert parse_level(level.rows).star_pos is not None


def test_clearing_enemies_alone_does_not_win():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit


def test_star_before_enemies_dead_shows_message():
    w = World(1, seed=1)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "playing"
    assert not w.star.lit
    assert w.message_timer > 0
    assert w.message == "star.kill_all"


def test_star_after_enemies_dead_wins_level():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    step(w, 30)
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "won"
    assert w.star.lit
    assert w.score == S.POINTS_LEVEL
    assert w.level_points == S.POINTS_LEVEL
    assert w.elapsed > 0.4


def test_star_is_reachable_from_top_platform():
    w = World(1, seed=1)
    p = w.player
    for e in w.enemies:
        e.alive = False
    # De pie sobre la plataforma de la fila 4, bajo la estrella.
    p.place(w.star.rect.centerx - p.rect.width // 2, S.cell_pos(0, 4)[1] - p.rect.height)
    step(w, 5)
    step(w, 1, {"jump"})
    step(w, 40)
    assert w.state == "won"


# --- tipos de enemigo ---
from orbes.entities import LaserEnemy, TongueEnemy  # noqa: E402

FLOOR_Y = S.FLOOR_Y - 32


def _duel(cls, gap):
    """Mundo con un único enemigo en el suelo, a `gap` píxeles del jugador y mirándolo."""
    w = World(1, seed=1)
    w.enemies = [e for e in w.enemies if isinstance(e, cls)][:1]
    e, p = w.enemies[0], w.player
    p.place(60, FLOOR_Y)
    e.place(60 + 28 + gap, FLOOR_Y)
    e.direction = -1
    e.cooldown = 0.0
    e.jump_cd = 99
    e.coyote = S.COYOTE_TIME
    p.invuln = 0
    return w, e, p


def test_every_level_mixes_both_enemy_types():
    for i in range(len(LEVELS)):
        kinds = {e.kind for e in World(i, seed=1).enemies}
        assert kinds == {"tongue", "laser"}


def test_tongue_hits_player_at_range_without_touching():
    w, e, p = _duel(TongueEnemy, gap=80)
    lives = w.lives
    assert e.rect.left - p.rect.right == 80    # separados: solo llega la lengua
    step(w, 2)
    assert e.attack == "tongue"
    step(w, 15)
    assert w.lives == lives - 1


def test_tongue_does_not_attack_behind_or_far():
    w, e, p = _duel(TongueEnemy, gap=80)
    e.direction = 1          # mirando hacia el otro lado
    step(w, 1)
    assert e.attack is None
    w, e, p = _duel(TongueEnemy, gap=200)
    step(w, 1)
    assert e.attack is None


def test_laser_lasts_one_second_then_recharges_four():
    w, e, p = _duel(LaserEnemy, gap=200)
    p.invuln = 99            # observamos el ciclo sin perder vidas
    step(w, 1)
    assert e.attack == "windup"
    step(w, int(S.LASER_WINDUP * 60) + 1)
    assert e.attack == "fire"
    beam = e.attack_rect()
    assert beam.colliderect(p.rect) and beam.left == S.BORDER   # llega hasta el borde
    step(w, 50)              # ~0.85 s disparando: sigue activo
    assert e.attack == "fire"
    step(w, 12)              # pasado 1 s: se apaga
    assert e.attack is None and e.attack_rect() is None
    assert abs(e.cooldown - S.LASER_RECHARGE) < 0.1
    step(w, int(3.8 * 60))
    # Mientras recarga sigue andando: lo devolvemos frente al jugador para comprobar
    # que, aun viéndolo, no dispara hasta completar los 4 s.
    e.place(p.rect.right + 200, FLOOR_Y)
    e.direction = -1
    step(w, 1)
    assert e.attack is None and e.cooldown > 0
    step(w, 20)
    assert e.attack is not None


def test_laser_hits_player_across_room():
    w, e, p = _duel(LaserEnemy, gap=200)
    lives = w.lives
    step(w, int((S.LASER_WINDUP + 0.1) * 60))
    assert w.lives == lives - 1


def test_trapping_cancels_attack():
    w, e, p = _duel(LaserEnemy, gap=200)
    step(w, int((S.LASER_WINDUP + 0.1) * 60))
    e.trap()
    assert e.attack is None and e.attack_rect() is None


# --- dificultad ---

@pytest.mark.parametrize("name", S.DIFFICULTY_ORDER)
def test_difficulty_rules_are_applied(name):
    rules = S.DIFFICULTIES[name]
    w = World(1, seed=1, difficulty=name)
    base = World(1, seed=1)
    assert w.lives == rules["lives"]
    assert w.enemies[0].speed == pytest.approx(base.enemies[0].speed * rules["enemy_speed"])
    assert all(e.cooldown_factor == rules["cooldown"] for e in w.enemies)


def test_normal_difficulty_keeps_laser_one_second_four_recharge():
    w, e, p = _duel(LaserEnemy, gap=200)
    assert w.difficulty == "normal"
    p.invuln = 99
    step(w, int((S.LASER_WINDUP + S.LASER_DURATION) * 60) + 5)
    assert e.attack is None
    assert abs(e.cooldown - 4.0) < 0.1


def test_hard_recharges_faster_easy_slower():
    for name, expected in (("hard", 3.0), ("easy", 5.0)):
        w = World(1, seed=1, difficulty=name)
        e = next(e for e in w.enemies if isinstance(e, LaserEnemy))
        e._end_attack(S.LASER_RECHARGE)
        assert e.cooldown == pytest.approx(expected)


def test_unknown_difficulty_falls_back_to_normal():
    assert World(1, seed=1, difficulty="imposible").difficulty == "normal"


# --- regresión: enemigo que desaparecía al escaparse de una burbuja pegada al techo ---
from orbes.entities import Bubble  # noqa: E402
from orbes.world import INTERIOR  # noqa: E402


def _release_at(w, e, x, y, direction):
    """Atrapa a `e` en una burbuja en (x, y) y deja que caduque."""
    e.direction = direction
    b = Bubble(0, 0, 1)
    b._to_float()
    b.age = 1.0
    b.fx, b.fy = float(x), float(y)
    b.rect.topleft = (x, y)
    e.trap()
    b.captured = e
    b.life = 0.05
    w.bubbles = [b]
    while w.bubbles:
        w.update(DT, set())


@pytest.mark.parametrize("direction", (1, -1))
def test_enemy_released_at_ceiling_stays_in_field(direction):
    w = World(1, seed=1)
    w.player.invuln = 999
    e = next(e for e in w.enemies if isinstance(e, LaserEnemy))
    _release_at(w, e, 180, S.BORDER, direction)
    step(w, 1)
    assert INTERIOR.contains(e.rect), e.rect
    step(w, 600)
    assert INTERIOR.contains(e.rect), e.rect


def test_release_anywhere_along_borders_never_escapes():
    top, left, right = S.BORDER, S.BORDER, S.FIELD_W - S.BORDER - S.BUBBLE_SIZE
    spots = [(x, top) for x in range(left, right + 1, 16)]
    spots += [(left, y) for y in range(top, S.FLOOR_Y - 40, 40)]
    spots += [(right, y) for y in range(top, S.FLOOR_Y - 40, 40)]
    for x, y in spots:
        for direction in (1, -1):
            w = World(1, seed=1)
            w.player.invuln = 999
            e = w.enemies[0]
            _release_at(w, e, x, y, direction)
            step(w, 2)
            assert INTERIOR.contains(e.rect), (x, y, direction, e.rect)


def test_push_out_uses_nearest_side_not_velocity():
    from pygame import Rect
    from orbes.entities import Enemy
    import random
    e = Enemy(0, 0, 50, random.Random(1))
    block = Rect(100, 100, 40, 40)
    e.place(130, 120)          # metido por la derecha del bloque
    e.vx = 200                 # aunque vaya hacia la derecha... (antes lo mandaba al otro lado)
    e.physics(DT, [block], [])
    assert not e.rect.colliderect(block)
    assert e.rect.left >= block.right - 1


def test_safety_net_brings_back_enemy_outside_field():
    w = World(1, seed=1)
    w.player.invuln = 999
    e = w.enemies[0]
    e.place(-500, -500)
    step(w, 1)
    assert INTERIOR.colliderect(e.rect)
    assert e.alive


def test_level_can_always_be_finished_after_escape():
    """El caso del bloqueo: tras escaparse del techo, el enemigo se puede atrapar y la
    estrella termina el nivel."""
    w = World(1, seed=1)
    w.player.invuln = 999
    e = next(e for e in w.enemies if isinstance(e, LaserEnemy))
    _release_at(w, e, 180, S.BORDER, 1)
    step(w, 5)
    assert INTERIOR.contains(e.rect)
    for other in w.enemies:
        other.alive = False
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "won"


# --- celebración de fin de nivel ---

def _win_in_mid_air(level=1):
    """Toca la estrella en pleno salto (como al saltar desde la plataforma de arriba)."""
    w = World(level, seed=1)
    for e in w.enemies:
        e.alive = False
    p = w.player
    p.place(w.star.rect.x, w.star.rect.y)
    p.vy = -100.0
    step(w, 1, {"right"})                       # avanzando hacia la derecha al tocarla
    assert w.state == "won"
    return w, p


def test_player_keeps_falling_after_touching_star_and_lands():
    w, p = _win_in_mid_air()
    y0 = p.rect.y
    assert not w.landed and not w.celebrating
    step(w, 5)
    assert p.rect.x > w.star.rect.x            # conserva el impulso horizontal
    for _ in range(240):
        step(w, 1)
        if w.landed:
            break
    assert w.landed and w.celebrating
    assert p.rect.y > y0                        # ha bajado hasta hacer pie
    assert p.on_ground and p.vx == 0
    x = p.rect.x
    step(w, 30)
    assert p.rect.x == x                        # ya en el suelo, quieto


def test_window_waits_for_landing_and_celebration():
    w, p = _win_in_mid_air()
    while not w.landed:
        step(w, 1)
    assert not w.celebration_done
    step(w, int(S.CELEBRATE_TIME * 60) + 2)
    assert w.celebration_done


def test_win_while_standing_celebrates_at_once():
    w = World(1, seed=1)
    for e in w.enemies:
        e.alive = False
    p = w.player
    # De pie sobre la plataforma de la fila 4, justo bajo la estrella: salta y la toca
    p.place(w.star.rect.centerx - p.rect.width // 2, S.cell_pos(0, 4)[1] - p.rect.height)
    step(w, 5)
    step(w, 1, {"jump"})
    while w.state != "won":
        step(w, 1)
    while not w.landed:
        step(w, 1)
    assert p.rect.bottom == S.cell_pos(0, 4)[1]  # vuelve a la plataforma de la que saltó


def test_celebration_has_time_limit():
    w, p = _win_in_mid_air()
    w.landed = False
    p.physics = lambda *a: False                # "nunca" llega al suelo
    step(w, int(S.CELEBRATE_MAX * 60) + 2)
    assert w.celebration_done



# --- animaciones de muerte ---
from orbes.entities import Ghost  # noqa: E402


def test_popped_enemy_becomes_ghost_that_rises_off_screen():
    w = World(1, seed=1)
    e = w.enemies[0]
    b = Bubble(*w.player.rect.center, 1)
    e.trap()
    b.captured = e
    b._to_float()
    b.age = 1.0
    w.bubbles = [b]
    w._pop(b)
    assert not e.alive and len(w.ghosts) == 1
    g = w.ghosts[0]
    assert g.kind == e.kind and g.rect.topleft == e.rect.topleft
    y0 = g.rect.y
    step(w, 30)
    assert g.rect.y < y0                            # sube
    assert w.enemies_left == len(w.enemies) - 1     # no cuenta como enemigo vivo
    for _ in range(60 * 10):
        step(w, 1)
        if not w.ghosts:
            break
    assert not w.ghosts                             # salió por arriba y se eliminó
    assert g.rect.bottom < -S.HUD_H                 # ...por encima del marcador


def test_ghost_accelerates_up_to_max_speed():
    import random
    from orbes.entities import TongueEnemy
    g = Ghost(TongueEnemy(100, 400, 50, random.Random(1)))
    g.update(0.1)
    v1 = g.vy
    for _ in range(200):
        g.update(0.05)
    assert S.GHOST_RISE_START < v1 < g.vy == S.GHOST_RISE_MAX


def test_ghosts_do_not_block_finishing_level():
    w = World(1, seed=1)
    for e in w.enemies:
        w.ghosts.append(Ghost(e))
        e.alive = False
    w.player.place(*w.star.rect.topleft)
    step(w, 1)
    assert w.state == "won"
    step(w, 10)
    assert w.ghosts                                 # siguen subiendo durante la celebración


def test_player_killed_in_air_falls_and_lies_on_floor():
    w = World(1, lives=3, seed=1)
    p = w.player
    p.place(S.cell_pos(4, 11)[0], S.cell_pos(0, 11)[1])   # en el aire, en mitad del nivel
    p.vy = -300.0
    w.enemies[0].place(*p.rect.topleft)
    step(w, 1)
    assert w.state == "dying" and p.dead and not p.landed_dead
    others = [(e.rect.topleft) for e in w.enemies]
    for _ in range(300):
        step(w, 1)
        if p.landed_dead:
            break
    assert p.landed_dead and w.player_down
    assert p.rect.bottom in (S.FLOOR_Y, S.cell_pos(0, 13)[1])   # en el suelo o plataforma
    assert [e.rect.topleft for e in w.enemies] == others        # la acción está detenida
    x, y = p.rect.topleft
    step(w, int(S.DEATH_TIME * 60) - 5)
    assert w.state == "dying" and p.rect.topleft == (x, y)       # sigue tumbado
    step(w, 10)
    assert w.state == "playing" and not p.dead and p.invuln > 0


def test_closing_during_death_saves_respawned_or_nothing():
    from orbes import savegame
    w = World(1, lives=2, seed=1)
    w.enemies[0].place(*w.player.rect.topleft)
    step(w, 1)
    assert w.state == "dying"
    data = savegame.snapshot(w)
    r = savegame.restore(data)
    assert r.state == "playing" and r.lives == 1 and not r.player.dead
    assert r.player.rect.topleft == (w.spawn[0] + 6, w.spawn[1] + 8)

    w.lives = 0
    assert savegame.snapshot(w) is None


# --- muerte final: tumba ---

def _kill(w):
    w.player.invuln = 0
    w.enemies[0].place(*w.player.rect.topleft)
    step(w, 1)
    assert w.state == "dying"


def test_final_death_sinks_then_grave_then_game_over():
    w = World(1, lives=1, seed=1)
    _kill(w)
    assert w.final_death
    while not w.player.landed_dead:
        step(w, 1)
    assert w.grave_progress == (0.0, 0.0)              # primero, tumbado como siempre
    step(w, int((S.DEATH_TIP_TIME + S.GRAVE_LIE) * 60) + 3)
    sink, rise = w.grave_progress
    assert 0 < sink < 1 and rise == 0                  # se está hundiendo
    step(w, int(S.GRAVE_SINK * 60))
    sink, rise = w.grave_progress
    assert sink == 1 and 0 < rise                      # hundido; sale la lápida
    step(w, int(S.GRAVE_RISE * 60))
    assert w.grave_progress == (1.0, 1.0) and w.state == "dying"
    step(w, int(S.GRAVE_HOLD * 60) + 2)
    assert w.state == "lost"                           # tumba a la vista y fin de partida
    assert w.grave_progress == (1.0, 1.0)


def test_non_final_death_has_no_grave():
    w = World(1, lives=2, seed=1)
    _kill(w)
    assert not w.final_death
    assert w.death_duration == S.DEATH_TIME
    for _ in range(int(S.DEATH_TIME * 60) + 120):
        assert w.grave_progress == (0.0, 0.0)
        step(w, 1)
        if w.state == "playing":
            break
    assert w.state == "playing" and w.lives == 1
