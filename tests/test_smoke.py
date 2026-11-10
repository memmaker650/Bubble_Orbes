from bubblequest.app import App
from bubblequest.scenes import GameScene, ScoresScene


def test_app_runs_menu_game_scores_headless(tmp_path):
    app = App(db_path=tmp_path / "t.db")
    app.run(max_frames=3)  # menú

    app = App(db_path=tmp_path / "t.db")
    app.change_scene(GameScene(app))
    app.run(max_frames=30)

    app = App(db_path=tmp_path / "t.db")
    app.change_scene(ScoresScene(app))
    app.run(max_frames=3)


def test_flag_button_changes_and_saves_language(tmp_path):
    import pygame

    from bubblequest import translations
    from bubblequest.scenes import MenuScene

    app = App(db_path=tmp_path / "t.db")
    menu = MenuScene(app)
    pos = menu.lang_button.rect.center
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos, touch=False)
    app.display.to_logical = lambda x, y: (x, y)
    menu.handle_event(event)
    assert translations.current().code == "en"
    assert app.db.get_setting("language") == "en"
    assert dict(menu.buttons)["scores"].label == "High scores"
    app.db.close()
    translations.set_language("es")

    # Al reabrir la app se recupera el idioma guardado
    app = App(db_path=tmp_path / "t.db")
    assert translations.current().code == "en"
    app.db.close()
    translations.set_language("es")


def test_menu_play_opens_play_screen_with_three_options(tmp_path):
    from bubblequest.scenes import MenuScene, PlayScene

    app = App(db_path=tmp_path / "t.db")
    menu = MenuScene(app)
    names = [name for name, _ in menu.buttons]
    assert "tutorial" not in names and names[0] == "play"
    assert dict(menu.buttons)["play"].label == "Jugar"
    menu._activate("play")
    play = app.scene
    assert isinstance(play, PlayScene)
    assert [n for n, _ in play.buttons][:4] == ["start", "difficulty", "tutorial", "back"]
    play._activate("back")
    assert isinstance(app.scene, MenuScene)
    app.db.close()


def test_difficulty_cycles_saves_and_applies(tmp_path):
    from bubblequest import settings as S
    from bubblequest.scenes import GameScene, PlayScene

    app = App(db_path=tmp_path / "t.db")
    play = PlayScene(app)
    assert "Medio" in dict(play.buttons)["difficulty"].label
    seen = []
    for _ in range(3):
        play._activate("difficulty")
        seen.append(app.db.get_setting("difficulty"))
    assert seen == ["hard", "easy", "normal"]

    play._activate("difficulty")
    play._activate("difficulty")   # -> easy
    assert "Fácil" in dict(play.buttons)["difficulty"].label
    play._activate("start")
    w = app.scene.world
    assert isinstance(app.scene, GameScene)
    assert w.number == 1 and w.difficulty == "easy"
    assert w.lives == S.DIFFICULTIES["easy"]["lives"]
    app.db.close()


def test_tutorial_button_then_level_one_keeps_difficulty(tmp_path):
    from bubblequest.scenes import PlayScene

    app = App(db_path=tmp_path / "t.db")
    app.db.set_setting("difficulty", "hard")
    PlayScene(app)._activate("tutorial")
    game = app.scene
    w = game.world
    assert w.tutorial and w.difficulty == "hard"

    w.score = 1234
    for e in w.enemies:
        e.alive = False
    game.update(1 / 60)
    w.player.place(*w.star.rect.topleft)
    game.update(1 / 60)
    assert w.state == "won"
    assert app.db.top_scores() == []          # el tutorial no guarda puntuación
    game._advance()
    nxt = app.scene.world
    assert nxt.number == 1 and nxt.score == 0 and nxt.difficulty == "hard"
    assert PlayScene(app)._next_level_index() == 1
    app.db.close()


def test_celebration_draws_and_overlay_appears_after(tmp_path):
    from bubblequest import settings as S
    from bubblequest.scenes import GameScene

    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1)
    w = game.world
    for e in w.enemies:
        e.alive = False
    w.player.place(*w.star.rect.topleft)
    game.update(1 / 60)
    assert w.state == "won" and not game._overlay_visible()
    for _ in range(int((S.CELEBRATE_MAX + 0.5) * 60)):
        game.update(1 / 60)
        game.draw(app.display.surface)       # dibuja caída, celebración y ventana
    assert w.celebrating and game._overlay_visible()
    app.db.close()


def test_death_animations_draw(tmp_path):
    from bubblequest.entities import Ghost
    from bubblequest.scenes import GameScene

    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1, lives=1)
    w = game.world
    w.ghosts.append(Ghost(w.enemies[1]))
    w.enemies[1].alive = False
    w.hit_player(1.0)
    for _ in range(int(4 * 60)):
        game.update(1 / 60)
        game.draw(app.display.surface)
    assert w.state == "lost" and game._overlay_visible()
    assert not app.db.has_saved_game()
    app.db.close()


def test_game_over_saves_score_with_difficulty(tmp_path):
    from bubblequest.scenes import GameScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1, difficulty="hard")
    w = game.world
    w.score = 450
    w.state = "lost"
    game.update(1 / 60)
    row = app.db.top_scores()[0]
    assert row["score"] == 450 and row["difficulty"] == "hard"
    app.db.close()


def test_hud_hearts_match_difficulty(tmp_path):
    from bubblequest import settings as S
    from bubblequest.scenes import GameScene
    from bubblequest import ui
    calls = []
    real = ui.draw_heart
    ui.draw_heart = lambda surf, center, size, filled: calls.append(filled) or real(surf, center, size, filled)
    try:
        app = App(db_path=tmp_path / "t.db")
        for difficulty in ("easy", "normal", "hard"):
            game = GameScene(app, level_index=1, difficulty=difficulty)
            game.world.lives -= 1                      # una vida gastada
            calls.clear()
            game.draw(app.display.surface)
            start = S.DIFFICULTIES[difficulty]["lives"]
            total = S.DIFFICULTIES[difficulty]["max_lives"]   # se ven todos los posibles
            assert len(calls) == total
            assert calls == [True] * (start - 1) + [False] * (total - start + 1)
        app.db.close()
    finally:
        ui.draw_heart = real


def test_scores_screen_shows_difficulty_letter(tmp_path):
    from bubblequest.scenes import ScoresScene
    from bubblequest import translations
    app = App(db_path=tmp_path / "t.db")
    app.db.add_score("Ana", 900, 3, "hard")
    app.db.add_score("Leo", 500, 2, "easy")
    app.db.add_score("Viejo", 100, 1)
    scene = ScoresScene(app)
    scene.draw(app.display.surface)             # sin errores con y sin dificultad
    translations.set_language("es")
    from bubblequest.translations import t
    assert [t(f"difficulty_short.{d}") for d in ("easy", "normal", "hard")] == ["F", "M", "D"]
    app.db.close()


def test_hud_draws_half_heart(tmp_path):
    from bubblequest.scenes import GameScene
    from bubblequest import ui
    calls = []
    real = ui.draw_heart
    ui.draw_heart = lambda surf, center, size, filled: calls.append(filled) or real(surf, center, size, filled)
    try:
        app = App(db_path=tmp_path / "t.db")
        game = GameScene(app, level_index=1, difficulty="normal")
        game.world.lives = 1.5
        game.draw(app.display.surface)
        assert calls == [1.0, 0.5, 0.0]
        app.db.close()
    finally:
        ui.draw_heart = real


def _win_level(app, game):
    w = game.world
    for e in w.enemies:
        e.alive = False
    w.player.place(*w.star.rect.topleft)
    for _ in range(60 * 6):
        game.update(1 / 60)
        if game._overlay_visible():
            break


def test_new_game_always_starts_at_level_one(tmp_path):
    from bubblequest.scenes import GameScene, PlayScene
    app = App(db_path=tmp_path / "t.db")
    # Completa los niveles 1, 2 y 3 seguidos
    game = GameScene(app, level_index=1)
    for _ in range(3):
        _win_level(app, game)
        game._advance()
        game = app.scene
    assert game.world.number == 4
    # Una partida nueva no sigue donde se quedó: empieza en el nivel 1
    play = PlayScene(app)
    assert dict(play.buttons)["start"].label == "Empezar"
    play._activate("start")
    assert app.scene.world.number == 1
    assert not app.db.has_saved_game()              # y descarta la partida guardada
    app.db.close()


def test_new_game_after_game_over_starts_at_level_one(tmp_path):
    from bubblequest.scenes import GameScene, PlayScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=3, lives=1)
    game.world.hit_player(1.0)
    for _ in range(60 * 6):
        game.update(1 / 60)
        if game.world.state == "lost":
            break
    game.update(1 / 60)
    assert game.world.state == "lost" and not app.db.has_saved_game()
    PlayScene(app)._activate("start")
    assert app.scene.world.number == 1
    app.db.close()


def test_continue_resumes_where_left_but_new_game_does_not(tmp_path):
    from bubblequest import savegame
    from bubblequest.scenes import MenuScene, PlayScene
    from bubblequest.world import World
    app = App(db_path=tmp_path / "t.db")
    app.db.save_game(savegame.snapshot(World(3, lives=2, score=1500, seed=1)))
    MenuScene(app)._activate("continue")
    w = app.scene.world
    assert (w.number, w.lives, w.score) == (3, 2, 1500)    # continuar: donde lo dejó
    PlayScene(app)._activate("start")
    assert app.scene.world.number == 1                    # empezar: desde el principio
    app.db.close()


def test_medkits_draw(tmp_path):
    from bubblequest.levels import index_of
    from bubblequest.scenes import GameScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=index_of(20))
    assert game.world.medkits
    for _ in range(5):
        game.update(1 / 60)
        game.draw(app.display.surface)
    app.db.close()


def test_level_complete_window_shows_heart_and_next_level_keeps_it(tmp_path):
    from bubblequest.scenes import GameScene
    from bubblequest import translations
    translations.set_language("es")
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1, lives=2)
    w = game.world
    for e in w.enemies:
        e.alive = False
    w.player.place(*w.star.rect.topleft)
    for _ in range(60 * 6):
        game.update(1 / 60)
        if game._overlay_visible():
            break
    game.draw(app.display.surface)
    assert w.hearts_gained == 1
    game._advance()
    assert app.scene.world.number == 2 and app.scene.world.lives == 3
    app.db.close()



def test_level_selector_picks_starting_level(tmp_path):
    import pygame
    from bubblequest.scenes import PlayScene
    app = App(db_path=tmp_path / "t.db")
    play = PlayScene(app)
    names = [n for n, _ in play.buttons]
    assert {"level_prev", "level", "level_next"} <= set(names)
    assert play.selected == 1 and dict(play.buttons)["level"].label == "Nivel 1"
    play._activate("level_next")
    play._activate("level_next")
    assert play.selected == 3 and dict(play.buttons)["level"].label == "Nivel 3"
    play._activate("level_prev")
    assert play.selected == 2
    play.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert play.selected == 3
    app.db.set_setting("difficulty", "hard")
    play._activate("start")
    w = app.scene.world
    assert w.number == 3 and w.difficulty == "hard"
    app.db.close()


def test_level_selector_wraps_and_resets(tmp_path):
    from bubblequest.levels import LEVELS
    from bubblequest.scenes import PlayScene
    app = App(db_path=tmp_path / "t.db")
    play = PlayScene(app)
    play._activate("level_prev")                    # del 1 salta al último
    assert play.selected == LEVELS[-1].number == 20
    play._activate("level_next")
    assert play.selected == 1
    play._activate("level_next")
    assert PlayScene(app).selected == 1             # al volver a la pantalla, otra vez el 1
    app.db.close()


def test_level_selector_can_be_hidden(tmp_path):
    from bubblequest import settings as S
    from bubblequest.scenes import PlayScene
    app = App(db_path=tmp_path / "t.db")
    S.LEVEL_SELECT = False
    try:
        play = PlayScene(app)
        assert "level" not in dict(play.buttons)
        play._activate("start")
        assert app.scene.world.number == 1
    finally:
        S.LEVEL_SELECT = True
        app.db.close()


def test_coins_and_popup_draw(tmp_path):
    from bubblequest.scenes import GameScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1)
    w = game.world
    w.player.place(w.coins[0].rect.x, w.coins[0].rect.y)
    for _ in range(10):
        game.update(1 / 60)
        game.draw(app.display.surface)
    assert w.popups or w.score >= 100
    app.db.close()


def test_no_black_boxes_background_surfaces_stay_opaque(tmp_path):
    """Regresión: el fantasma (y otras capas semitransparentes) mostraba a veces un cuadro
    negro. Las superficies de fondo no deben tener canal alfa ni acabar con píxeles
    transparentes, se dibuje lo que se dibuje encima."""
    from bubblequest import settings as S
    from bubblequest.entities import Bubble, Ghost, LaserEnemy, TongueEnemy
    from bubblequest.scenes import GameScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=1)
    w = game.world
    for e in w.enemies:
        w.ghosts.append(Ghost(e))
    w.popup(100, 300, 100, S.ENEMY_BLUE)
    w.popup(200, 300, 100, S.GOLD)
    w.bubbles = [Bubble(250, 450, 1)]
    laser = next(e for e in w.enemies if isinstance(e, LaserEnemy))
    laser.attack, laser.super_attack = "fire", True
    laser._aim(w.solids)
    tongue = next(e for e in w.enemies if isinstance(e, TongueEnemy))
    tongue.tired = True                                # se dibuja inclinado en otra capa
    for _ in range(3):
        game.draw(app.display.surface)
    for surf in (app.display.surface, game._world_surf):
        assert surf.get_masks()[3] == 0                # sin canal de transparencia
        sw, sh = surf.get_size()
        assert {surf.get_at((x, y))[3] for x in range(0, sw, 4) for y in range(0, sh, 4)} == {255}
    # Alrededor del fantasma se ve el fondo, no negro
    g = w.ghosts[0]
    x, y = g.rect.x - 22, S.HUD_H + g.rect.y - round(w.camera_y) - 16
    if S.HUD_H < y < S.HUD_H + S.FIELD_H and 0 <= x < S.LOGICAL_W:
        assert app.display.surface.get_at((x, y))[:3] != (0, 0, 0)
    app.db.close()


def test_fade_keeps_transparent_pixels_transparent():
    import pygame
    from bubblequest.ui import fade, transparent_layer
    layer = transparent_layer((20, 20))
    pygame.draw.rect(layer, (200, 50, 50), (5, 5, 10, 10))
    fade(layer, 153)
    assert layer.get_at((0, 0))[3] == 0                # el fondo sigue transparente
    assert layer.get_at((10, 10))[3] == 153            # el dibujo, al 60 %
    assert layer.get_alpha() in (None, 255)            # sin opacidad general (set_alpha)


def test_icons_exist_for_every_platform():
    """Generados con tools/make_icons.py (iOS, macOS, Windows, Linux, Android y ventana)."""
    from pathlib import Path

    import pygame
    res = Path(__file__).parents[1] / "src" / "bubblequest" / "resources"
    sizes = (20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024,   # iOS
             16, 32, 64, 128, 256, 512)                                   # Linux
    for size in sizes:
        img = pygame.image.load(str(res / f"icon-{size}.png"))
        assert img.get_size() == (size, size)
    for size in (48, 72, 96, 144, 192):                                   # Android
        assert (res / f"icon-round-{size}.png").exists()
        assert (res / f"icon-square-{size}.png").exists()
    assert (res / "icon.icns").read_bytes()[:4] == b"icns"               # macOS
    assert (res / "icon.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"    # Windows
    assert (res / "icon.png").exists() and (res / "icon-macos.png").exists()


def test_bombs_and_explosions_draw(tmp_path):
    from bubblequest.levels import index_of
    from bubblequest.scenes import GameScene
    app = App(db_path=tmp_path / "t.db")
    game = GameScene(app, level_index=index_of(13))
    w = game.world
    w.bombs[0].light()
    for _ in range(int((3.0 + 0.7) * 60)):
        w.player.invuln = 99
        game.update(1 / 60)
        game.draw(app.display.surface)
    assert len(w.bombs) == 1
    app.db.close()
