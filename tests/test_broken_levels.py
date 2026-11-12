"""Un JSON de nivel mal editado (una fila con un espacio de más o de menos, JSON roto...) no
cierra el juego: el nivel queda marcado como dañado y, al jugarlo, se explica en pantalla."""

import json

import pygame
import pytest

from bubblequest import levels, savegame
from bubblequest import settings as S
from bubblequest.levels import LevelDef, LevelError, load_levels, parse_level

GOOD = ["         "] * (S.ROWS - 1) + ["    P    "]


def _write(tmp_path, number, rows=None, raw=None):
    path = tmp_path / f"level_{number:02d}.json"
    if raw is None:
        raw = json.dumps(LevelDef(number, f"N{number}", rows or GOOD).to_dict())
    path.write_text(raw, encoding="utf-8")


@pytest.mark.parametrize("row, key, count", [("          ", "level_error.row_long", 1),
                                             ("        ", "level_error.row_short", 1),
                                             ("      ", "level_error.row_short", 3)])
def test_row_with_extra_or_missing_spaces_is_explained(row, key, count):
    rows = list(GOOD)
    rows[4] = row
    with pytest.raises(LevelError) as info:
        parse_level(rows)
    e = info.value
    assert e.key == key and e.params["row"] == 5 and e.params["count"] == count
    assert e.params["length"] == len(row) and e.params["text"] == row


def test_broken_files_do_not_stop_the_other_levels(tmp_path):
    _write(tmp_path, 1)
    bad = list(GOOD)
    bad[3] += " "
    _write(tmp_path, 2, bad)
    _write(tmp_path, 3, raw='{"number": 3, "map": [')          # JSON roto
    loaded = load_levels(tmp_path)
    assert [lv.number for lv in loaded] == [1, 2, 3]
    assert loaded[0].error is None
    assert loaded[1].error.key == "level_error.row_long"
    assert loaded[2].error.key == "level_error.file" and loaded[2].file == "level_03.json"


@pytest.fixture
def broken_level(monkeypatch):
    """Nivel 1 del juego con una fila con un espacio de más."""
    real = levels.LEVELS
    i = levels.index_of(1)
    rows = list(real[i].rows)
    rows[2] = rows[2] + " "
    try:
        parse_level(rows)
    except LevelError as exc:
        error = exc
    broken = LevelDef(1, real[i].name, rows, error=error)
    broken.file = "level_01.json"
    monkeypatch.setattr(levels, "_cache", real[:i] + [broken] + real[i + 1:])
    return i


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("BUBBLEQUEST_DATA", str(tmp_path))
    from bubblequest.app import App
    return App(db_path=tmp_path / "t.db")


def test_playing_a_broken_level_shows_the_error_instead_of_crashing(app, broken_level):
    from bubblequest.scenes import LevelErrorScene, MenuScene, PlayScene
    play = PlayScene(app)
    play._start(broken_level)
    scene = app.scene
    assert isinstance(scene, LevelErrorScene)
    texts = [text for _, text, _ in scene.lines()]
    assert any("level_01.json" in x for x in texts)
    assert any("sobran 1" in x for x in texts)
    surf = pygame.Surface((S.LOGICAL_W, S.LOGICAL_H))
    scene.update(0.1)
    scene.draw(surf)                                         # se dibuja sin fallar
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert isinstance(app.scene, MenuScene)


def test_next_level_broken_shows_the_error(app, broken_level):
    from bubblequest.scenes import GameScene, LevelErrorScene
    game = GameScene(app, level_index=broken_level - 1)
    game.world.state = "won"
    game._advance()
    assert isinstance(app.scene, LevelErrorScene)


def test_continue_into_broken_level_keeps_the_save(app, broken_level):
    from bubblequest.scenes import LevelErrorScene, MenuScene
    data = {"version": savegame.SAVE_VERSION, "level_number": 1, "lives": 3, "score": 0,
            "fresh": True}
    app.db.save_game(data)
    MenuScene(app)._continue()
    assert isinstance(app.scene, LevelErrorScene)
    assert app.db.load_game() is not None                   # al arreglarlo se puede seguir


def test_error_texts_are_translated():
    from bubblequest import translations
    keys = ["level_error.title", "level_error.file_name", "level_error.row_long",
            "level_error.row_short", "level_error.hint"]
    for lang in translations.languages():
        assert all(k in lang.texts for k in keys), lang.code
