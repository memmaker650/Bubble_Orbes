"""Animación final tras el nivel 30: el personaje coloca las cinco gemas en el púlpito, con el
gusano encerrado en la cárcel de la mazmorra."""

import pygame

from bubblequest import ending_art
from bubblequest import settings as S
from bubblequest.app import App
from bubblequest.levels import LEVELS
from bubblequest.scenes import EndingScene, GameScene, MenuScene

DT = 1 / 60
ENTER = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)


def make_app(tmp_path):
    return App(db_path=tmp_path / "t.db")


def test_winning_last_level_shows_ending_then_menu(tmp_path):
    app = make_app(tmp_path)
    game = GameScene(app, level_index=len(LEVELS) - 1)
    assert game.world.number == 30 and game.world.is_last_level
    game.world.state = "won"
    game._advance()
    assert isinstance(app.scene, EndingScene)
    app.db.close()


def test_other_levels_and_game_over_do_not_show_ending(tmp_path):
    app = make_app(tmp_path)
    game = GameScene(app, level_index=len(LEVELS) - 1)
    game.world.state = "lost"
    game._advance()
    assert isinstance(app.scene, MenuScene)
    game = GameScene(app, level_index=2)
    game.world.state = "won"
    game._advance()
    assert isinstance(app.scene, GameScene)
    app.db.close()


def test_player_places_the_five_gems_in_order(tmp_path):
    app = make_app(tmp_path)
    end = EndingScene(app)
    assert ending_art.GEM_ORDER == ("ruby", "emerald", "yellow", "aquamarine", "white")
    assert len(ending_art.slot_centers()) == 5
    end.update(S.ENDING_PLAYER_AT - 0.1)
    assert end.gems_placed() == 0
    placed = []
    while not end.done:
        end.update(DT)
        end.draw(app.display.surface)
        placed.append(end.gems_placed())
    assert placed == sorted(placed) and placed[-1] == 5          # una a una, sin saltos atrás
    assert set(placed) == {0, 1, 2, 3, 4, 5}
    # El personaje se queda fuera de la cárcel, sin pisar al gusano
    assert end.player_rect().right < ending_art.CAGE.left
    assert end.player_rect().right < end.worm_x() - 15
    app.db.close()


def test_cage_opens_after_the_gems_and_worm_comes_out(tmp_path):
    app = make_app(tmp_path)
    end = EndingScene(app)
    end.t = end.all_placed_t() - 0.01                  # aún falta encajar la última gema
    assert end.lock_open() == 0 and end.cage_open() == 0
    assert end.worm_x() == ending_art.WORM_X
    steps = []
    while not end.done:
        end.update(DT)
        end.draw(app.display.surface)
        steps.append((end.lock_open(), end.cage_open(), end.exit_progress()))
    # Primero el candado, luego la reja y por último sale el gusano
    first = [next(i for i, s in enumerate(steps) if s[j] > 0) for j in range(3)]
    assert first == sorted(first) and len(set(first)) == 3
    assert steps[-1] == (1.0, 1.0, 1.0)
    assert end.worm_x() < ending_art.WORM_X            # ha salido hacia el personaje
    assert end.meet_t() >= 0                           # y se han reencontrado
    app.db.close()


def test_tap_skips_to_end_then_returns_to_menu(tmp_path):
    app = make_app(tmp_path)
    end = EndingScene(app)
    app.change_scene(end)
    end.update(0.5)
    end.handle_event(ENTER)
    assert app.scene is end and end.done and end.gems_placed() == 5
    end.draw(app.display.surface)
    end.handle_event(ENTER)
    assert isinstance(app.scene, MenuScene)
    app.db.close()
