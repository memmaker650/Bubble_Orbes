"""Escenas: menú, juego y puntuaciones."""

import math
import sys

import pygame

from . import settings as S
from .controls import Controls, is_confirm, tap_position
from .levels import LEVELS
from .ui import Button, draw_text
from .world import World

IS_IOS = sys.platform == "ios"


class Scene:
    def __init__(self, app):
        self.app = app

    def handle_event(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.title_font = pygame.font.Font(None, 96)
        self.font = pygame.font.Font(None, 38)
        self.small = pygame.font.Font(None, 22)
        self.t = 0.0
        level = app.db.unlocked_level()
        self.buttons = [
            ("play", Button((70, 340, 220, 56), f"Jugar (nivel {level})")),
            ("scores", Button((70, 412, 220, 56), "Puntuaciones")),
        ]
        if not IS_IOS:  # en iOS no se "sale" de una app
            self.buttons.append(("quit", Button((70, 484, 220, 56), "Salir")))

    def _activate(self, name):
        if name == "play":
            level = min(self.app.db.unlocked_level(), len(LEVELS)) - 1
            self.app.change_scene(GameScene(self.app, level_index=level))
        elif name == "scores":
            self.app.change_scene(ScoresScene(self.app))
        elif name == "quit":
            self.app.quit()

    def handle_event(self, event):
        pos = tap_position(event, self.app.display)
        if pos is not None:
            for name, button in self.buttons:
                if button.hit(pos):
                    self._activate(name)
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._activate("play")
            elif event.key == pygame.K_ESCAPE and not IS_IOS:
                self.app.quit()

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        surf.fill(S.BG)
        for i in range(6):  # orbes decorativos flotando
            x = 40 + i * 56
            y = 240 - ((self.t * 30 + i * 70) % 260) + 120
            r = 12 + (i % 3) * 5
            pygame.draw.circle(surf, S.BUBBLE, (x + math.sin(self.t + i) * 12, y), r, 2)
        draw_text(surf, self.title_font, "ORBES", S.BUBBLE, center=(S.LOGICAL_W // 2, 200))
        draw_text(surf, self.small, "Atrapa enemigos en burbujas y revienta", S.WHITE,
                  center=(S.LOGICAL_W // 2, 270))
        for _, button in self.buttons:
            button.draw(surf, self.font)


class ScoresScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.title = pygame.font.Font(None, 56)
        self.font = pygame.font.Font(None, 30)
        self.rows = app.db.top_scores(10)

    def handle_event(self, event):
        if is_confirm(event, self.app.display) or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            self.app.change_scene(MenuScene(self.app))

    def draw(self, surf):
        surf.fill(S.BG)
        draw_text(surf, self.title, "Puntuaciones", S.BUBBLE, center=(S.LOGICAL_W // 2, 70))
        if not self.rows:
            draw_text(surf, self.font, "Aún no hay partidas", S.WHITE,
                      center=(S.LOGICAL_W // 2, 200))
        for i, row in enumerate(self.rows):
            y = 130 + i * 40
            draw_text(surf, self.font, f"{i + 1:>2}.  {row['player']}", S.WHITE, topleft=(30, y))
            draw_text(surf, self.font, f"{row['score']}  (N{row['level']})", S.PLATFORM,
                      topleft=(215, y))
        draw_text(surf, self.font, "Toca para volver", S.WHITE,
                  center=(S.LOGICAL_W // 2, S.LOGICAL_H - 60))


class GameScene(Scene):
    def __init__(self, app, level_index=0, lives=S.START_LIVES, score=0):
        super().__init__(app)
        self.world = World(level_index, lives, score)
        self.controls = Controls()
        self.hud = pygame.font.Font(None, 26)
        self.big = pygame.font.Font(None, 54)
        self.font = pygame.font.Font(None, 30)
        self.saved = False
        self.t = 0.0

    # --- ciclo ---
    def handle_event(self, event):
        self.controls.handle_event(event, self.app.display)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.change_scene(MenuScene(self.app))
        elif self.world.state != "playing" and is_confirm(event, self.app.display):
            self._advance()

    def update(self, dt):
        self.t += dt
        w = self.world
        w.update(dt, self.controls.actions())
        if w.state == "won" and not self.saved:
            self.saved = True
            self.app.db.unlock_level(w.level_index + 2, len(LEVELS))
            if w.is_last_level:
                self._save_score()
        elif w.state == "lost" and not self.saved:
            self.saved = True
            self._save_score()

    def _save_score(self):
        name = self.app.db.get_setting("player_name", "Jugador")
        self.app.db.add_score(name, self.world.score, self.world.level_index + 1)

    def _advance(self):
        w = self.world
        if w.state == "won" and not w.is_last_level:
            self.app.change_scene(
                GameScene(self.app, w.level_index + 1, w.lives, w.score))
        else:
            self.app.change_scene(MenuScene(self.app))

    # --- dibujo ---
    def draw(self, surf):
        w = self.world
        surf.fill(S.BG)
        for s in w.solids:
            pygame.draw.rect(surf, S.SOLID, s)
        for p in w.oneway:
            pygame.draw.rect(surf, S.PLATFORM, p, border_radius=5)

        for e in w.enemies:
            if e.alive:
                self._draw_enemy(surf, e)
        for b in w.bubbles:
            self._draw_bubble(surf, b)
        self._draw_player(surf, w.player)

        draw_text(surf, self.hud, f"Puntos {w.score}", S.WHITE, topleft=(10, 10))
        draw_text(surf, self.hud, f"Nivel {w.level_index + 1}", S.WHITE,
                  center=(S.LOGICAL_W // 2, 20))
        draw_text(surf, self.hud, f"Vidas {w.lives}", S.WHITE, topleft=(S.LOGICAL_W - 90, 10))

        pygame.draw.rect(surf, (10, 12, 26), (0, S.FIELD_H, S.LOGICAL_W, S.LOGICAL_H - S.FIELD_H))
        self.controls.draw(surf, self.controls.actions())

        if w.state != "playing":
            self._draw_overlay(surf)

    def _draw_player(self, surf, p):
        if p.invuln > 0 and int(self.t * 10) % 2 == 0:
            return  # parpadeo
        pygame.draw.rect(surf, S.PLAYER, p.rect, border_radius=10)
        ex = p.rect.centerx + p.facing * 5
        pygame.draw.circle(surf, S.WHITE, (ex, p.rect.y + 12), 5)
        pygame.draw.circle(surf, S.BLACK, (ex + p.facing * 2, p.rect.y + 12), 2)

    def _draw_enemy(self, surf, e):
        color = (255, 60, 60) if e.angry else S.ENEMY
        pygame.draw.rect(surf, color, e.rect, border_radius=8)
        for dx in (-6, 6):
            pygame.draw.circle(surf, S.WHITE, (e.rect.centerx + dx, e.rect.y + 12), 4)
            pygame.draw.circle(surf, S.BLACK, (e.rect.centerx + dx, e.rect.y + 12), 2)

    def _draw_bubble(self, surf, b):
        if b.captured is not None:
            self._draw_enemy(surf, b.captured)
        layer = pygame.Surface((S.BUBBLE_SIZE + 8, S.BUBBLE_SIZE + 8), pygame.SRCALPHA)
        c = layer.get_width() // 2
        pygame.draw.circle(layer, (*S.BUBBLE, 70), (c, c), c - 2)
        pygame.draw.circle(layer, (*S.BUBBLE, 220), (c, c), c - 2, 2)
        surf.blit(layer, layer.get_rect(center=b.rect.center))

    def _draw_overlay(self, surf):
        w = self.world
        dim = pygame.Surface((S.LOGICAL_W, S.FIELD_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surf.blit(dim, (0, 0))
        cx = S.LOGICAL_W // 2
        if w.state == "won":
            title = "¡Has ganado!" if w.is_last_level else "¡Nivel completado!"
        else:
            title = "Fin de la partida"
        draw_text(surf, self.big, title, S.BUBBLE, center=(cx, 260))
        draw_text(surf, self.font, f"Puntos: {w.score}", S.WHITE, center=(cx, 320))
        draw_text(surf, self.font, "Toca para continuar", S.WHITE, center=(cx, 380))
