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
    assert menu.buttons[1][1].label == "High scores"
    app.db.close()
    translations.set_language("es")

    # Al reabrir la app se recupera el idioma guardado
    app = App(db_path=tmp_path / "t.db")
    assert translations.current().code == "en"
    app.db.close()
    translations.set_language("es")
