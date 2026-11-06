"""Escenas: menú, juego y puntuaciones."""

import logging
import math
import sqlite3
import sys

import pygame

from . import settings as S
from . import translations
from .controls import Controls, is_confirm, tap_position
from . import levels
from .translations import t
from .ui import Button, FlagButton, draw_message_box, draw_text
from .world import World

IS_IOS = sys.platform == "ios"
log = logging.getLogger(__name__)


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
        self._build_buttons()

    def _tutorial_pending(self) -> bool:
        db = self.app.db
        # Quien ya pasó del nivel 1 en versiones anteriores no necesita el tutorial
        return db.get_setting("tutorial_done") is None and db.unlocked_level() <= 1

    def _next_level_index(self) -> int:
        if self._tutorial_pending():
            return 0
        number = max(1, self.app.db.unlocked_level())
        return levels.index_of(number)

    def _build_buttons(self):
        """(Re)crea los botones con los textos del idioma activo."""
        level = levels.LEVELS[self._next_level_index()]
        play = (t("menu.play_tutorial") if level.tutorial
                else t("menu.play", level=level.number))
        self.buttons = [
            ("play", Button((70, 340, 220, 56), play)),
            ("tutorial", Button((70, 412, 220, 56), t("menu.tutorial"))),
            ("scores", Button((70, 484, 220, 56), t("menu.scores"))),
        ]
        if not IS_IOS:  # en iOS no se "sale" de una app
            self.buttons.append(("quit", Button((70, 556, 220, 56), t("menu.quit"))))
        self.lang_button = FlagButton((S.LOGICAL_W - 66, S.LOGICAL_H - 52, 54, 38),
                                      translations.current().flag)

    def _next_language(self):
        lang = translations.next_language()
        translations.set_language(lang.code)
        try:
            self.app.db.set_setting("language", lang.code)
        except sqlite3.Error:
            log.error("No se pudo guardar el idioma %s; solo se aplica a esta sesión", lang.code)
        self._build_buttons()

    def _activate(self, name):
        if name == "play":
            self.app.change_scene(GameScene(self.app, level_index=self._next_level_index()))
        elif name == "tutorial":
            self.app.change_scene(GameScene(self.app, level_index=0))
        elif name == "scores":
            self.app.change_scene(ScoresScene(self.app))
        elif name == "quit":
            self.app.quit()

    def handle_event(self, event):
        pos = tap_position(event, self.app.display)
        if pos is not None:
            if self.lang_button.hit(pos):
                self._next_language()
                return
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
        draw_text(surf, self.small, t("menu.subtitle"), S.WHITE,
                  center=(S.LOGICAL_W // 2, 270))
        for _, button in self.buttons:
            button.draw(surf, self.font)
        self.lang_button.draw(surf)


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
        draw_text(surf, self.title, t("scores.title"), S.BUBBLE, center=(S.LOGICAL_W // 2, 70))
        if not self.rows:
            draw_text(surf, self.font, t("scores.empty"), S.WHITE,
                      center=(S.LOGICAL_W // 2, 200))
        for i, row in enumerate(self.rows):
            y = 130 + i * 40
            draw_text(surf, self.font, f"{i + 1:>2}.  {row['player']}", S.WHITE, topleft=(30, y))
            draw_text(surf, self.font, f"{row['score']}  ({t('scores.level', level=row['level'])})", S.PLATFORM,
                      topleft=(215, y))
        draw_text(surf, self.font, t("scores.back"), S.WHITE,
                  center=(S.LOGICAL_W // 2, S.LOGICAL_H - 60))


class GameScene(Scene):
    def __init__(self, app, level_index=0, lives=S.START_LIVES, score=0):
        super().__init__(app)
        self.world = World(level_index, lives, score)
        self.controls = Controls()
        self.hud = pygame.font.Font(None, 26)
        self.big = pygame.font.Font(None, 54)
        self.font = pygame.font.Font(None, 30)
        self.title = pygame.font.Font(None, 42)
        self.small = pygame.font.Font(None, 22)
        self.saved = False
        self.t = 0.0
        self.won_t = 0.0         # tiempo desde que se completó el nivel

    # --- ciclo ---
    def handle_event(self, event):
        self.controls.handle_event(event, self.app.display)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.change_scene(MenuScene(self.app))
        elif self._overlay_visible() and is_confirm(event, self.app.display):
            self._advance()

    def _overlay_visible(self) -> bool:
        w = self.world
        if w.state == "won":  # deja ver la estrella azul un momento
            return self.won_t >= S.STAR_DELAY
        return w.state == "lost"

    def update(self, dt):
        self.t += dt
        w = self.world
        w.update(dt, self.controls.actions())
        if w.state == "won":
            self.won_t += dt
        if w.state == "won" and not self.saved:
            self.saved = True
            if w.tutorial:
                self.app.db.set_setting("tutorial_done", 1)
            self.app.db.unlock_level(w.number + 1, levels.LEVELS[-1].number)
            if w.is_last_level and not w.tutorial:
                self._save_score()
        elif w.state == "lost" and not self.saved:
            self.saved = True
            if not w.tutorial:
                self._save_score()

    def _save_score(self):
        name = self.app.db.get_setting("player_name", t("player.default"))
        self.app.db.add_score(name, self.world.score, self.world.number)

    def _advance(self):
        w = self.world
        if w.state == "won" and not w.is_last_level:
            if w.tutorial:  # el tutorial es práctica: se empieza de cero
                scene = GameScene(self.app, w.level_index + 1)
            else:
                scene = GameScene(self.app, w.level_index + 1, w.lives, w.score)
            self.app.change_scene(scene)
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

        if w.star is not None:
            self._draw_star(surf, w)
        for e in w.enemies:
            if e.alive:
                self._draw_enemy(surf, e)
        for b in w.bubbles:
            self._draw_bubble(surf, b)
        self._draw_player(surf, w.player)

        draw_text(surf, self.hud, t("hud.score", score=w.score), S.WHITE, topleft=(10, 10))
        level = t("hud.tutorial") if w.tutorial else t("hud.level", level=w.number)
        draw_text(surf, self.hud, level, S.WHITE,
                  center=(S.LOGICAL_W // 2, 20))
        draw_text(surf, self.hud, t("hud.lives", lives=w.lives), S.WHITE, topleft=(S.LOGICAL_W - 90, 10))

        pygame.draw.rect(surf, (10, 12, 26), (0, S.FIELD_H, S.LOGICAL_W, S.LOGICAL_H - S.FIELD_H))
        self.controls.draw(surf, self.controls.actions())

        if w.tutorial_step is not None:
            self._draw_tutorial_hint(surf, w.tutorial_step)
        if w.message_timer > 0 and w.state == "playing":
            draw_message_box(surf, [(self.font, t(w.message), S.WHITE)],
                             center=(S.LOGICAL_W // 2, S.FIELD_H // 2), accent=S.STAR_YELLOW)
        if self._overlay_visible():
            self._draw_overlay(surf)

    def _draw_tutorial_hint(self, surf, step):
        keys = "" if IS_IOS else " (Z)"
        draw_message_box(surf, [(self.small, t(f"tutorial.{step}", keys=keys), S.STAR_YELLOW)],
                         center=(S.LOGICAL_W // 2, S.FIELD_H - 20), width=340,
                         padding=8, accent=S.STAR_YELLOW)

    def _draw_star(self, surf, w):
        star = w.star
        if star.lit:
            color, scale = S.STAR_BLUE, 1.0 + 0.15 * math.sin(self.t * 8)
        else:
            color = S.STAR_YELLOW
            # Late cuando ya se puede recoger (no quedan enemigos)
            scale = 1.0 + 0.12 * math.sin(self.t * 6) if w.enemies_left == 0 else 1.0
        pygame.draw.polygon(surf, color, star.points(scale))
        pygame.draw.polygon(surf, S.WHITE, star.points(scale), 2)

    def _draw_player(self, surf, p):
        if p.invuln > 0 and int(self.t * 10) % 2 == 0:
            return  # parpadeo
        pygame.draw.rect(surf, S.PLAYER, p.rect, border_radius=10)
        ex = p.rect.centerx + p.facing * 5
        pygame.draw.circle(surf, S.WHITE, (ex, p.rect.y + 12), 5)
        pygame.draw.circle(surf, S.BLACK, (ex + p.facing * 2, p.rect.y + 12), 2)

    def _draw_enemy(self, surf, e):
        if e.kind == "laser":
            color = (40, 90, 255) if e.angry else S.ENEMY_BLUE
        else:
            color = (255, 60, 60) if e.angry else S.ENEMY
        pygame.draw.rect(surf, color, e.rect, border_radius=8)
        if e.kind == "tongue":
            self._draw_tongue(surf, e)
        look = e.direction * 2  # las pupilas miran hacia donde camina
        for dx in (-6, 6):
            eye = (e.rect.centerx + dx, e.rect.y + e.EYE_Y)
            pygame.draw.circle(surf, S.WHITE, eye, 4)
            pupil = (eye[0] + look, eye[1])
            if e.kind == "laser":
                self._draw_laser_eye(surf, e, pupil)
            else:
                pygame.draw.circle(surf, S.BLACK, pupil, 2)
        if e.kind == "laser" and e.attack == "fire":
            self._draw_laser(surf, e)

    def _draw_tongue(self, surf, e):
        rect = e.attack_rect()
        mx, my = e.mouth()
        if rect is None:
            pygame.draw.line(surf, S.BLACK, (mx - e.direction * 8, my), (mx - e.direction * 2, my), 2)
            return
        tip = (mx + e.direction * int(e.tongue_length), my)
        pygame.draw.line(surf, S.TONGUE, (mx - e.direction * 4, my), tip, 6)
        pygame.draw.circle(surf, S.TONGUE, tip, 7)
        pygame.draw.circle(surf, (200, 60, 110), tip, 7, 2)

    def _draw_laser_eye(self, surf, e, pupil):
        if e.attack is not None:  # cargando o disparando: ojos al rojo vivo
            glow = 3 + int(2 * abs(math.sin(self.t * 20)))
            pygame.draw.circle(surf, S.LASER, pupil, glow)
        else:  # el color indica la energía: gris (vacío) -> rojo (cargado)
            k = max(0.0, min(1.0, e.charge))
            col = tuple(int(90 + (c - 90) * k) for c in S.LASER)
            pygame.draw.circle(surf, col, pupil, 2)

    def _draw_laser(self, surf, e):
        rect = e.attack_rect()
        if rect is None:
            return
        halo = rect.inflate(0, 8)
        layer = pygame.Surface(halo.size, pygame.SRCALPHA)
        flicker = int(40 * abs(math.sin(self.t * 30)))
        pygame.draw.rect(layer, (*S.LASER, 70 + flicker), layer.get_rect(), border_radius=6)
        surf.blit(layer, halo.topleft)
        ey = rect.centery
        for dy in (-3, 3):  # un rayo por cada ojo
            pygame.draw.line(surf, S.LASER, (rect.left, ey + dy), (rect.right, ey + dy), 3)
        pygame.draw.line(surf, (255, 200, 200), (rect.left, ey), (rect.right, ey), 1)

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
        center = (S.LOGICAL_W // 2, S.FIELD_H // 2)
        if w.state == "won":
            minutes, seconds = divmod(int(w.elapsed), 60)
            if w.tutorial:
                rows = [(self.title, t("win.tutorial"), S.STAR_BLUE),
                        (self.font, t("win.next"), S.STAR_YELLOW)]
            else:
                rows = [(self.title, t("win.title", level=w.number), S.STAR_BLUE)]
                if w.is_last_level:
                    rows.append((self.font, t("win.game"), S.STAR_YELLOW))
            rows += [
                (self.font, t("win.time", time=f"{minutes:02d}:{seconds:02d}"), S.WHITE),
                (self.font, t("win.points", points=w.level_points), S.WHITE),
                (self.hud, t("win.total", score=w.score), S.PLATFORM),
                (self.hud, t("common.continue"), S.WHITE),
            ]
            draw_message_box(surf, rows, center, width=320, accent=S.STAR_BLUE)
        else:
            draw_message_box(surf, [
                (self.big, t("lost.title"), S.BUBBLE),
                (self.font, t("lost.points", score=w.score), S.WHITE),
                (self.hud, t("common.continue"), S.WHITE),
            ], center, width=320)
