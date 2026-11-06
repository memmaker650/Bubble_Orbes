import json
import sqlite3

import pygame
import pytest

from orbes import settings as S
from orbes import savegame
from orbes.app import App
from orbes.db import Database
from orbes.scenes import GameScene, MenuScene
from orbes.world import World

DT = 1 / 60


def step(world, n, actions=()):
    for _ in range(n):
        world.update(DT, set(actions))


def _mid_game_world():
    """Partida a medias en el nivel 2: enemigo atrapado en burbuja, otro muerto, puntos..."""
    w = World(2, lives=2, score=700, seed=3)
    w.player.invuln = 99      # que nadie le quite vidas mientras preparamos la escena
    step(w, 60)
    e, p = w.enemies[0], w.player
    floor_y = (S.ROWS - 1) * S.TILE - p.rect.height
    p.place(60, floor_y)
    e.place(150, floor_y)
    e.direction = 1           # de espaldas: no ataca
    p.facing = 1
    step(w, 1)
    step(w, 1, {"bubble"})
    step(w, 30)
    w.enemies[1].alive = False
    w.score += 100
    w.player.invuln = 0.5
    return w


# --- base de datos ---

def test_db_save_load_clear_and_migration(tmp_path):
    path = tmp_path / "o.db"
    # Base de datos "antigua" (versión 1, sin tabla de partida guardada)
    conn = sqlite3.connect(path)
    from orbes.db import SCHEMA_V1
    conn.executescript(SCHEMA_V1)
    conn.close()

    db = Database(path)
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert db.load_game() is None
    db.save_game({"a": 1})
    db.save_game({"a": 2})  # sobrescribe: solo hay una partida
    assert db.load_game() == {"a": 2}
    assert db.conn.execute("SELECT COUNT(*) FROM saved_game").fetchone()[0] == 1
    db.clear_game()
    assert not db.has_saved_game()


def test_corrupt_save_is_discarded():
    db = Database(":memory:")
    db.conn.execute("INSERT INTO saved_game (slot, data) VALUES (1, '{roto')")
    assert db.load_game() is None
    assert db.conn.execute("SELECT COUNT(*) FROM saved_game").fetchone()[0] == 0


# --- snapshot / restore ---

def test_roundtrip_restores_full_state():
    w = _mid_game_world()
    assert w.bubbles and w.bubbles[0].captured is w.enemies[0]
    data = json.loads(json.dumps(savegame.snapshot(w)))  # pasa por JSON como en la BD
    r = savegame.restore(data)

    assert (r.number, r.lives, r.score) == (2, 2, w.score)
    assert r.level_start_score == 700 and abs(r.elapsed - w.elapsed) < 1e-9
    assert r.player.rect.topleft == w.player.rect.topleft
    assert r.player.invuln >= S.RESUME_INVULN
    for a, b in zip(r.enemies, w.enemies):
        assert (a.kind, a.alive, a.state, a.rect.topleft, a.direction) == \
               (b.kind, b.alive, b.state, b.rect.topleft, b.direction)
    assert len(r.bubbles) == len(w.bubbles)
    assert r.bubbles[0].captured is r.enemies[0]
    assert r.bubbles[0].rect.topleft == w.bubbles[0].rect.topleft


def test_restored_game_keeps_playing_identically():
    w = _mid_game_world()
    r = savegame.restore(savegame.snapshot(w))
    w.player.invuln = r.player.invuln
    step(w, 60)
    step(r, 60)
    assert r.player.rect.topleft == w.player.rect.topleft
    assert [b.rect.topleft for b in r.bubbles] == [b.rect.topleft for b in w.bubbles]


def test_lost_game_saves_nothing_and_won_level_saves_next():
    w = World(1, seed=1)
    w.state = "lost"
    assert savegame.snapshot(w) is None

    w = World(1, lives=2, score=900, seed=1)
    w.state = "won"
    data = savegame.snapshot(w)
    assert data["fresh"] and data["level_number"] == 2
    r = savegame.restore(data)
    assert (r.number, r.lives, r.score, r.state) == (2, 2, 900, "playing")

    w = World(3, seed=1)
    w.state = "won"  # último nivel: juego terminado
    assert savegame.snapshot(w) is None


def test_tutorial_won_saves_level_one_from_scratch():
    w = World(0, seed=1)
    w.score = 500
    w.state = "won"
    data = savegame.snapshot(w)
    assert data["level_number"] == 1 and data["score"] == 0


def test_changed_level_restarts_it_and_bad_data_raises():
    w = _mid_game_world()
    data = savegame.snapshot(w)
    data["enemies"] = data["enemies"][:-1]  # el mapa "ha cambiado"
    r = savegame.restore(data)
    assert r.number == 2 and r.score == 700 and not r.bubbles
    with pytest.raises(ValueError):
        savegame.restore({"version": 99})
    with pytest.raises(ValueError):
        savegame.restore({"version": 1})


# --- integración con la app ---

def test_quit_saves_and_menu_continues(tmp_path):
    db_path = tmp_path / "t.db"
    app = App(db_path=db_path)
    app.change_scene(GameScene(app, world=_mid_game_world()))
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.run(max_frames=5)  # el cierre guarda y cierra la BD

    app = App(db_path=db_path)
    menu = app.scene
    assert isinstance(menu, MenuScene)
    names = [name for name, _ in menu.buttons]
    assert names[0] == "continue"
    assert "2" in dict(menu.buttons)["continue"].label
    menu._activate("continue")
    assert isinstance(app.scene, GameScene)
    w = app.scene.world
    assert w.number == 2 and w.lives == 2 and w.bubbles
    app.db.close()


def test_background_event_saves_without_quitting(tmp_path):
    app = App(db_path=tmp_path / "t.db")
    app.change_scene(GameScene(app, level_index=1))
    pygame.event.post(pygame.event.Event(pygame.APP_WILLENTERBACKGROUND))
    app.run(max_frames=3)
    db = Database(tmp_path / "t.db")
    assert db.load_game()["level_number"] == 1


def test_new_game_and_game_over_discard_save(tmp_path):
    app = App(db_path=tmp_path / "t.db")
    app.db.save_game(savegame.snapshot(World(2, seed=1)))
    from orbes.scenes import PlayScene
    PlayScene(app)._activate("start")
    assert not app.db.has_saved_game()
    menu = MenuScene(app)
    assert "continue" not in dict(menu.buttons)

    game = GameScene(app, level_index=1)
    game.save_progress()
    assert app.db.has_saved_game()
    game.world.state = "lost"
    game.update(DT)
    assert not app.db.has_saved_game()
    app.db.close()


def test_invalid_save_is_dropped_from_menu(tmp_path):
    app = App(db_path=tmp_path / "t.db")
    app.db.save_game({"version": 99, "level_number": 1})
    menu = MenuScene(app)
    menu._activate("continue")
    assert app.scene is not None and not isinstance(app.scene, GameScene)
    assert "continue" not in dict(menu.buttons)
    app.db.close()


def test_difficulty_is_saved_and_restored():
    w = World(2, seed=1, difficulty="hard")
    r = savegame.restore(json.loads(json.dumps(savegame.snapshot(w))))
    assert r.difficulty == "hard"
    assert all(e.cooldown_factor == S.DIFFICULTIES["hard"]["cooldown"] for e in r.enemies)
    w.state = "won"
    assert savegame.restore(savegame.snapshot(w)).difficulty == "hard"


def test_old_save_without_difficulty_is_normal():
    data = savegame.snapshot(World(1, seed=1))
    del data["difficulty"]
    assert savegame.restore(data).difficulty == "normal"
