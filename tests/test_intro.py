"""Presentación antes del nivel 1: el gusano amigo sale de la tierra y llega el personaje."""

import pygame
import pytest

from bubblequest import settings as S
from bubblequest.app import App
from bubblequest.levels import index_of
from bubblequest.scenes import GameScene, IntroScene, PlayScene, game_scene

DT = 1 / 60


@pytest.fixture(autouse=True)
def _intro_on(monkeypatch):
    monkeypatch.setattr(S, "INTRO_ENABLED", True)


def make_app(tmp_path):
    return App(db_path=tmp_path / "t.db")


def test_level_one_starts_with_intro_then_game(tmp_path):
    app = make_app(tmp_path)
    PlayScene(app)._activate("start")
    intro = app.scene
    assert isinstance(intro, IntroScene)
    for _ in range(int(S.INTRO_DURATION / DT) + 2):
        app.scene.update(DT)
        app.scene.draw(app.display.surface)
    assert isinstance(app.scene, GameScene) and app.scene.world.number == 1
    app.db.close()


def test_other_levels_and_tutorial_have_no_intro(tmp_path):
    app = make_app(tmp_path)
    assert isinstance(game_scene(app, index_of(2)), GameScene)
    assert isinstance(game_scene(app, 0), GameScene)          # tutorial
    app.db.close()


def test_tap_or_key_skips_intro(tmp_path):
    app = make_app(tmp_path)
    intro = game_scene(app, index_of(1))
    app.change_scene(intro)
    intro.update(0.2)
    intro.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert isinstance(app.scene, GameScene)
    game = app.scene
    intro.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert app.scene is game                                  # no crea el nivel dos veces
    app.db.close()


def test_worm_first_then_player_after_one_second(tmp_path):
    app = make_app(tmp_path)
    intro = IntroScene(app, lambda: None)
    intro.update(0.5)
    assert intro.worm_rise() > 0.5 and not intro.player_visible()
    intro.update(0.6)                                         # t = 1.1 s
    assert intro.player_visible()
    start_x = intro.player_rect().centerx
    intro.update(S.INTRO_PLAYER_WALK)
    assert intro.player_rect().centerx > start_x               # ha caminado hacia el gusano
    assert intro.player_rect().right < intro.WORM_X - 15       # sin pisarlo
    app.db.close()
