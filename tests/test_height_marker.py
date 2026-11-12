"""Bola roja de altura en el borde derecho: abajo del todo con el jugador en el suelo y arriba
del todo cuando está en lo más alto del nivel."""

import pygame

from bubblequest import settings as S
from bubblequest.levels import index_of
from bubblequest.scenes import height_marker_range, height_marker_y, height_progress
from bubblequest.world import World


def _world_at(feet_y, number=30):
    w = World(index_of(number), seed=1)
    w.player.place(100, feet_y - w.player.rect.height)
    return w


def test_marker_at_bottom_when_on_the_floor():
    w = World(index_of(30), seed=1)              # el 30 empieza en el suelo
    assert w.player.rect.bottom == w.floor_y
    assert height_progress(w) == 0.0
    assert height_marker_y(w) == height_marker_range()[1]


def test_marker_at_top_when_at_the_top():
    w = _world_at(S.BORDER + 32)                  # cabeza contra el techo
    assert height_progress(w) == 1.0
    assert height_marker_y(w) == height_marker_range()[0]


def test_marker_moves_up_as_player_climbs():
    w = World(index_of(30), seed=1)
    ys = []
    for feet in range(w.floor_y, S.BORDER + 32, -200):
        w.player.place(100, feet - 32)
        ys.append(height_marker_y(w))
    assert ys == sorted(ys, reverse=True) and len(set(ys)) == len(ys)


def test_marker_half_way():
    w = World(index_of(30), seed=1)
    mid = (w.floor_y + S.BORDER + 32) / 2
    w.player.place(100, round(mid) - 32)
    assert abs(height_progress(w) - 0.5) < 0.01


def test_marker_stays_inside_the_right_border():
    top, bottom = height_marker_range()
    assert S.HUD_H <= top < bottom <= S.HUD_H + S.FIELD_H


def test_marker_drawn_only_in_tall_levels(tmp_path, monkeypatch):
    from bubblequest.scenes import GameScene
    calls = []
    monkeypatch.setattr(GameScene, "_draw_height_marker",
                        staticmethod(lambda surf, w: calls.append(w.number)))
    monkeypatch.setenv("BUBBLEQUEST_DATA", str(tmp_path))
    from bubblequest.app import App
    app = App(db_path=tmp_path / "t.db")
    surf = pygame.Surface((S.LOGICAL_W, S.LOGICAL_H))
    for number in (1, 30):
        GameScene(app, level_index=index_of(number)).draw(surf)
    assert calls == [30]
