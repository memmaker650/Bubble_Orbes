from orbes.app import App
from orbes.scenes import GameScene, ScoresScene


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

    from orbes import translations
    from orbes.scenes import MenuScene

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
    from orbes.scenes import MenuScene, PlayScene

    app = App(db_path=tmp_path / "t.db")
    menu = MenuScene(app)
    names = [name for name, _ in menu.buttons]
    assert "tutorial" not in names and names[0] == "play"
    assert dict(menu.buttons)["play"].label == "Jugar"
    menu._activate("play")
    play = app.scene
    assert isinstance(play, PlayScene)
    assert [n for n, _ in play.buttons] == ["start", "difficulty", "tutorial", "back"]
    play._activate("back")
    assert isinstance(app.scene, MenuScene)
    app.db.close()


def test_difficulty_cycles_saves_and_applies(tmp_path):
    from orbes import settings as S
    from orbes.scenes import GameScene, PlayScene

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
    from orbes.scenes import PlayScene

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
    from orbes import settings as S
    from orbes.scenes import GameScene

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
