"""Escenas: menú, juego y puntuaciones."""

import logging
import math
import sqlite3
import sys

import pygame

from . import settings as S
from . import translations
from . import savegame
from .controls import Controls, is_confirm, tap_position
from . import levels
from .translations import t
from .ui import Button, FlagButton, draw_hearts, draw_message_box, draw_text
from .world import World

IS_IOS = sys.platform == "ios"
_BTN_X = (S.LOGICAL_W - 260) // 2      # botones de menú centrados
_SCORES_X = (S.LOGICAL_W - 300) // 2
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

    def on_close(self):
        """La app se cierra o pasa a segundo plano."""
        pass


class MenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.title_font = pygame.font.Font(None, 96)
        self.font = pygame.font.Font(None, 38)
        self.small = pygame.font.Font(None, 22)
        self.t = 0.0
        self._build_buttons()

    def _build_buttons(self):
        """(Re)crea los botones con los textos del idioma activo."""
        entries = []
        saved = self.app.db.load_game()
        if saved is not None:
            label = (t("menu.continue_tutorial") if saved.get("tutorial")
                     else t("menu.continue", level=saved.get("level_number", "?")))
            entries.append(("continue", label))
        entries += [("play", t("menu.play")), ("scores", t("menu.scores"))]
        if not IS_IOS:  # en iOS no se "sale" de una app
            entries.append(("quit", t("menu.quit")))
        self.buttons = [(name, Button((_BTN_X, 340 + i * 72, 260, 54), label))
                        for i, (name, label) in enumerate(entries)]
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
        if name == "continue":
            self._continue()
        elif name == "play":
            self.app.change_scene(PlayScene(self.app))
        elif name == "scores":
            self.app.change_scene(ScoresScene(self.app))
        elif name == "quit":
            self.app.quit()

    def _continue(self):
        data = self.app.db.load_game()
        try:
            world = savegame.restore(data) if data else None
        except ValueError:
            log.exception("No se pudo retomar la partida guardada; se descarta")
            world = None
        if world is None:
            self.app.db.clear_game()
            self._build_buttons()
            return
        self.app.change_scene(GameScene(self.app, world=world))

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
                names = [name for name, _ in self.buttons]
                self._activate("continue" if "continue" in names else "play")
            elif event.key == pygame.K_ESCAPE and not IS_IOS:
                self.app.quit()

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        surf.fill(S.BG)
        for i in range(6):  # orbes decorativos flotando
            x = (S.LOGICAL_W - 280) // 2 + i * 56
            y = 240 - ((self.t * 30 + i * 70) % 260) + 120
            r = 12 + (i % 3) * 5
            pygame.draw.circle(surf, S.BUBBLE, (x + math.sin(self.t + i) * 12, y), r, 2)
        draw_text(surf, self.title_font, "ORBES", S.BUBBLE, center=(S.LOGICAL_W // 2, 200))
        draw_text(surf, self.small, t("menu.subtitle"), S.WHITE,
                  center=(S.LOGICAL_W // 2, 270))
        for _, button in self.buttons:
            button.draw(surf, self.font)
        self.lang_button.draw(surf)


def get_difficulty(db) -> str:
    value = db.get_setting("difficulty", S.DEFAULT_DIFFICULTY)
    return value if value in S.DIFFICULTIES else S.DEFAULT_DIFFICULTY


class PlayScene(Scene):
    """Pantalla previa a la partida: Empezar, Dificultad (Fácil/Medio/Difícil) y Tutorial."""

    def __init__(self, app):
        super().__init__(app)
        self.title_font = pygame.font.Font(None, 56)
        self.font = pygame.font.Font(None, 38)
        self.small = pygame.font.Font(None, 24)
        self._build_buttons()

    def _next_level_index(self) -> int:
        return levels.index_of(max(1, self.app.db.unlocked_level()))

    def _build_buttons(self):
        level = levels.LEVELS[self._next_level_index()]
        difficulty = get_difficulty(self.app.db)
        self.buttons = [
            ("start", Button((_BTN_X, 250, 260, 60), t("play.start", level=level.number))),
            ("difficulty", Button((_BTN_X, 330, 260, 60), t(
                "play.difficulty", value=t(f"difficulty.{difficulty}")))),
            ("tutorial", Button((_BTN_X, 410, 260, 60), t("menu.tutorial"))),
            ("back", Button(((S.LOGICAL_W - 140) // 2, S.LOGICAL_H - 110, 140, 46), t("common.back"))),
        ]

    def _cycle_difficulty(self):
        order = S.DIFFICULTY_ORDER
        nxt = order[(order.index(get_difficulty(self.app.db)) + 1) % len(order)]
        try:
            self.app.db.set_setting("difficulty", nxt)
        except sqlite3.Error:
            log.error("No se pudo guardar la dificultad %s", nxt)
        self._build_buttons()

    def _start(self, level_index):
        self.app.db.clear_game()  # empezar de nuevo descarta la partida guardada
        self.app.change_scene(GameScene(self.app, level_index=level_index,
                                        difficulty=get_difficulty(self.app.db)))

    def _activate(self, name):
        if name == "start":
            self._start(self._next_level_index())
        elif name == "difficulty":
            self._cycle_difficulty()
        elif name == "tutorial":
            self._start(0)
        elif name == "back":
            self.app.change_scene(MenuScene(self.app))

    def handle_event(self, event):
        pos = tap_position(event, self.app.display)
        if pos is not None:
            for name, button in self.buttons:
                if button.hit(pos):
                    self._activate(name)
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._activate("start")
            elif event.key == pygame.K_ESCAPE:
                self._activate("back")

    def draw(self, surf):
        surf.fill(S.BG)
        draw_text(surf, self.title_font, t("play.title"), S.BUBBLE, center=(S.LOGICAL_W // 2, 150))
        for name, button in self.buttons:
            button.draw(surf, self.small if name == "back" else self.font)
        # Indicador de dificultad: 1, 2 o 3 estrellas bajo el botón
        stars = S.DIFFICULTY_ORDER.index(get_difficulty(self.app.db)) + 1
        box = dict(self.buttons)["difficulty"].rect
        for i in range(3):
            cx = S.LOGICAL_W // 2 + (i - 1) * 22
            color = S.STAR_YELLOW if i < stars else S.BUTTON
            pygame.draw.circle(surf, color, (cx, box.bottom + 10), 5)


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
            draw_text(surf, self.font, f"{i + 1:>2}.  {row['player']}", S.WHITE, topleft=(_SCORES_X, y))
            # Puntos, letra de la dificultad (F/M/D) y nivel alcanzado
            r = draw_text(surf, self.font, str(row["score"]), S.PLATFORM, topleft=(_SCORES_X + 165, y))
            difficulty = row.get("difficulty")
            if difficulty in S.DIFFICULTIES:
                r = draw_text(surf, self.font, t(f"difficulty_short.{difficulty}"),
                              S.DIFFICULTY_COLORS[difficulty], topleft=(r.right + 6, y))
            draw_text(surf, self.font, f"({t('scores.level', level=row['level'])})", S.PLATFORM,
                      topleft=(r.right + 8, y))
        draw_text(surf, self.font, t("scores.back"), S.WHITE,
                  center=(S.LOGICAL_W // 2, S.LOGICAL_H - 60))


class GameScene(Scene):
    def __init__(self, app, level_index=0, lives=None, score=0, world=None,
                 difficulty=S.DEFAULT_DIFFICULTY):
        super().__init__(app)
        if world is None:
            world = World(level_index, lives, score, difficulty=difficulty)
        self.world = world
        self._world_surf = None      # superficie con el nivel entero (alto variable)
        self._brick_tile = None
        self.controls = Controls()
        self.hud = pygame.font.Font(None, 26)
        self.big = pygame.font.Font(None, 54)
        self.font = pygame.font.Font(None, 30)
        self.title = pygame.font.Font(None, 42)
        self.small = pygame.font.Font(None, 22)
        self.saved = False
        self.t = 0.0

    # --- ciclo ---
    def handle_event(self, event):
        self.controls.handle_event(event, self.app.display)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.save_progress()  # salir al menú también guarda, para poder continuar
            self.app.change_scene(MenuScene(self.app))
        elif self._overlay_visible() and is_confirm(event, self.app.display):
            self._advance()

    def on_close(self):
        self.save_progress()

    def save_progress(self):
        """Guarda la partida en la base de datos (o la borra si ya no hay nada que retomar)."""
        try:
            data = savegame.snapshot(self.world)
            if data is None:
                self.app.db.clear_game()
            else:
                self.app.db.save_game(data)
        except sqlite3.Error:
            log.exception("No se pudo guardar la partida")

    def _overlay_visible(self) -> bool:
        w = self.world
        if w.state == "won":  # primero hace pie y celebra; luego la ventana
            return w.celebration_done
        return w.state == "lost"

    def update(self, dt):
        self.t += dt
        w = self.world
        w.update(dt, self.controls.actions())
        if w.state == "won" and not self.saved:
            self.saved = True
            if w.tutorial:
                self.app.db.set_setting("tutorial_done", 1)
            self.app.db.unlock_level(w.number + 1, levels.LEVELS[-1].number)
            if w.is_last_level and not w.tutorial:
                self._save_score()
            self.save_progress()  # queda guardado el inicio del siguiente nivel
        elif w.state == "lost" and not self.saved:
            self.saved = True
            self.app.db.clear_game()  # partida perdida: no hay nada que continuar
            if not w.tutorial:
                self._save_score()
                self.app.db.reset_progress()  # se vuelve a empezar desde el nivel 1

    def _save_score(self):
        name = self.app.db.get_setting("player_name", t("player.default"))
        self.app.db.add_score(name, self.world.score, self.world.number, self.world.difficulty)

    def _advance(self):
        w = self.world
        if w.state == "won" and not w.is_last_level:
            if w.tutorial:  # el tutorial es práctica: se empieza de cero
                scene = GameScene(self.app, w.level_index + 1, difficulty=w.difficulty)
            else:
                scene = GameScene(self.app, w.level_index + 1, w.lives, w.score,
                                  difficulty=w.difficulty)
            self.app.change_scene(scene)
        else:
            self.app.change_scene(MenuScene(self.app))

    # --- dibujo ---
    def draw(self, surf):
        w = self.world
        surf.fill(S.BG)
        # El nivel entero se dibuja en su propia superficie (puede ser más alto que la
        # pantalla) y luego se copia la parte que ve la cámara bajo la franja del marcador.
        size = (S.FIELD_W, w.height)
        if self._world_surf is None or self._world_surf.get_size() != size:
            self._world_surf = pygame.Surface(size)
        field = self._world_surf
        field.fill(S.BG)
        bricks = {tuple(b) for b in w.bricks}
        for s in w.solids:
            if tuple(s) in bricks:
                field.blit(self._brick(), s)
            else:
                pygame.draw.rect(field, S.SOLID, s)
        for p in w.oneway:
            pygame.draw.rect(field, S.PLATFORM, p, border_radius=5)

        if w.star is not None:
            self._draw_star(field, w)
        for e in w.enemies:
            if e.alive:
                self._draw_enemy(field, e)
        for b in w.bubbles:
            self._draw_bubble(field, b)
        if w.celebrating:
            self._draw_player_celebrating(field, w.player, w.celebrate_t)
        elif w.player.dead:
            sink, rise = w.grave_progress
            self._draw_player_dead(field, w.player, w.death_t if w.player.landed_dead else 0.0,
                                   w.player.landed_dead, sink, rise)
        else:
            self._draw_player(field, w.player)

        camera = round(w.camera_y)
        surf.blit(field, (0, S.HUD_H), pygame.Rect(0, camera, S.FIELD_W, S.FIELD_H))
        if w.scrolls:
            self._draw_scroll_hints(surf, w)

        pygame.draw.rect(surf, (10, 12, 26), (0, 0, S.LOGICAL_W, S.HUD_H))
        hud_y = S.HUD_H // 2
        draw_text(surf, self.hud, t("hud.score", score=w.score), S.WHITE,
                  midleft=(S.BORDER, hud_y))
        level = t("hud.tutorial") if w.tutorial else t("hud.level", level=w.number)
        draw_text(surf, self.hud, level, S.WHITE, center=(S.LOGICAL_W // 2, hud_y))
        # Vidas: un corazón por cada vida de la dificultad; vacíos los ya gastados
        draw_hearts(surf, w.lives, w.rules["lives"], S.LOGICAL_W - S.BORDER, hud_y)

        for g in w.ghosts:  # suben por encima del marcador hasta salir de la pantalla
            self._draw_ghost(surf, g)

        controls_y = S.HUD_H + S.FIELD_H
        pygame.draw.rect(surf, (10, 12, 26), (0, controls_y, S.LOGICAL_W, S.LOGICAL_H - controls_y))
        self.controls.draw(surf, self.controls.actions())

        if w.tutorial_step is not None:
            self._draw_tutorial_hint(surf, w.tutorial_step)
        if w.message_timer > 0 and w.state == "playing":
            draw_message_box(surf, [(self.font, t(w.message), S.WHITE)],
                             center=(S.LOGICAL_W // 2, S.HUD_H + S.FIELD_H // 2),
                             accent=S.STAR_YELLOW)
        if self._overlay_visible():
            self._draw_overlay(surf)

    def _brick(self):
        """Casilla de ladrillos con llagas de cemento (se dibuja una vez y se reutiliza)."""
        if self._brick_tile is None:
            t = S.TILE
            tile = pygame.Surface((t, t))
            tile.fill(S.MORTAR)
            rows, bw = 4, 20
            bh = t // rows
            for r in range(rows):
                offset = 0 if r % 2 == 0 else -bw // 2
                for c in range(-1, t // bw + 1):
                    x = offset + c * bw
                    brick = pygame.Rect(x + 1, r * bh + 1, bw - 2, bh - 2)
                    shade = S.BRICK if (r + c) % 3 else S.BRICK_DARK
                    pygame.draw.rect(tile, shade, brick)
                    pygame.draw.line(tile, (200, 110, 85), brick.topleft,
                                     (brick.right - 1, brick.top))   # brillo superior
            pygame.draw.rect(tile, S.BRICK_DARK, tile.get_rect(), 1)
            self._brick_tile = tile
        return self._brick_tile

    def _draw_scroll_hints(self, surf, w):
        """Flechitas que indican que el nivel sigue por arriba o por abajo."""
        cx = S.LOGICAL_W - S.BORDER - 10
        if w.camera_y > 4:
            y = S.HUD_H + 10
            pygame.draw.polygon(surf, S.WHITE, [(cx - 6, y + 5), (cx, y - 3), (cx + 6, y + 5)])
        if w.camera_y < w.height - S.FIELD_H - 4:
            y = S.HUD_H + S.FIELD_H - 10
            pygame.draw.polygon(surf, S.WHITE, [(cx - 6, y - 5), (cx, y + 3), (cx + 6, y - 5)])

    def _draw_tutorial_hint(self, surf, step):
        keys = "" if IS_IOS else " (Z)"
        # En la fila 0, que está libre en el tutorial
        draw_message_box(surf, [(self.small, t(f"tutorial.{step}", keys=keys), S.STAR_YELLOW)],
                         center=(S.LOGICAL_W // 2, S.HUD_H + S.BORDER + S.TILE // 2),
                         width=S.FIELD_W - 2 * S.BORDER, padding=6, gap=4,
                         accent=S.STAR_YELLOW)

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

    def _draw_player_celebrating(self, surf, p, t):
        """De frente y sonriendo: levanta su brazo derecho (a la izquierda en pantalla, porque
        nos mira) y, después, saca una pequeña lengua roja."""
        r = p.rect
        # Pequeño "rebote" al aterrizar (se aplasta y recupera en 0,15 s)
        squash = max(0.0, 1.0 - t / 0.15) * 4
        body = pygame.Rect(r.x - squash / 2, r.y + squash, r.width + squash, r.height - squash)

        # Brazo derecho del personaje = lado izquierdo de la pantalla. Sube desde el costado
        # y, ya arriba, la mano se balancea saludando.
        raise_k = min(1.0, t / S.CELEBRATE_ARM_TIME)
        raise_k = 1 - (1 - raise_k) ** 2                       # sube rápido y frena al final
        shoulder = (body.left + 3, body.y + 16)
        down = (body.left - 4, body.y + 26)                     # mano junto al costado
        up = (body.left - 9, body.y - 6)                        # mano levantada
        wave = math.sin((t - S.CELEBRATE_ARM_TIME) * 9) * 3 if raise_k >= 1 else 0.0
        hand = (down[0] + (up[0] - down[0]) * raise_k + wave,
                down[1] + (up[1] - down[1]) * raise_k)
        # Pegado al borde izquierdo, el brazo se endereza para no meterse en el muro
        hand = (max(hand[0], S.BORDER + 6), hand[1])

        # Brazo y mano por detrás del cuerpo: si se cruzan con él (junto al muro), asoman
        pygame.draw.line(surf, S.PLAYER_DARK, shoulder, hand, 4)       # brazo
        pygame.draw.circle(surf, S.PLAYER, hand, 5)                    # mano
        pygame.draw.circle(surf, S.PLAYER_DARK, hand, 5, 1)
        pygame.draw.rect(surf, S.PLAYER, body, border_radius=10)

        cx, ey = body.centerx, body.y + 11
        for dx in (-6, 6):                                             # ojos de frente
            pygame.draw.circle(surf, S.WHITE, (cx + dx, ey), 5)
            pygame.draw.circle(surf, S.BLACK, (cx + dx, ey + 1), 2)
        smile = pygame.Rect(cx - 7, body.y + 13, 14, 10)               # sonrisa
        pygame.draw.arc(surf, S.BLACK, smile, math.pi, 2 * math.pi, 2)

        # Lengua: asoma por el centro de la sonrisa cuando el brazo ya está arriba
        if t >= S.CELEBRATE_TONGUE_AT:
            grow = min(1.0, (t - S.CELEBRATE_TONGUE_AT) / S.CELEBRATE_TONGUE_GROW)
            length = 2 + round(5 * grow)
            tongue = pygame.Rect(cx - 3, smile.bottom - 2, 6, length)
            pygame.draw.rect(surf, S.PLAYER_TONGUE, tongue, border_radius=3)
            pygame.draw.line(surf, (150, 20, 35), (cx, tongue.y + 1),
                             (cx, tongue.bottom - 2), 1)               # surco central

    @staticmethod
    def _draw_x_eye(surf, center, r=4):
        """Ojo de muerto: en blanco con una X."""
        x, y = center
        pygame.draw.circle(surf, S.WHITE, (x, y), r + 1)
        d = r - 1
        pygame.draw.line(surf, S.BLACK, (x - d, y - d), (x + d, y + d), 2)
        pygame.draw.line(surf, S.BLACK, (x - d, y + d), (x + d, y - d), 2)

    def _draw_player_dead(self, surf, p, t, landed, sink=0.0, rise=0.0):
        """Ojo en X; al hacer pie se vuelca de espaldas y se queda tumbado en el suelo.
        En la muerte final, además, se hunde en el terreno y aparece una tumba con lápida."""
        r = p.rect
        k = min(1.0, t / S.DEATH_TIP_TIME) if landed else 0.0
        if k < 1.0:
            img = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(img, S.PLAYER, img.get_rect(), border_radius=10)
            self._draw_x_eye(img, (r.width // 2 + p.facing * 5, 12), 4)
            if k > 0:
                img = pygame.transform.rotate(img, 90 * p.facing * k)  # volcándose
            surf.blit(img, img.get_rect(midbottom=r.midbottom))
            return

        ground = r.bottom                 # superficie sobre la que está (suelo o plataforma)
        head = -p.facing                  # cae de espaldas: la cabeza, al lado contrario
        cx = r.centerx
        if rise > 0:
            self._draw_tombstone(surf, cx + head * 13, ground, rise)

        # Todo lo que baje de la superficie queda "dentro de la tierra" y no se ve
        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), ground).clip(old_clip))
        if sink < 1.0:
            body = pygame.Rect(0, 0, 38, 20)
            body.midbottom = (cx, ground + round(sink * (body.height + 2)))
            pygame.draw.rect(surf, S.PLAYER, body, border_radius=9)
            self._draw_x_eye(surf, (body.centerx + head * 11, body.y + 8), 4)
            foot = body.centerx - head * 15                       # pies asomando al otro lado
            pygame.draw.circle(surf, S.PLAYER_DARK, (foot, body.y + 3), 3)
        if sink > 0:
            # Montículo de tierra que crece mientras se hunde
            mound = pygame.Rect(0, 0, 46, round(4 + 14 * sink))
            mound.center = (cx - head * 2, ground)
            pygame.draw.ellipse(surf, S.DIRT, mound)
            pygame.draw.ellipse(surf, S.DIRT_DARK, mound, 1)
            if sink < 1.0:
                self._draw_dirt(surf, cx, ground, sink)
        surf.set_clip(old_clip)

    @staticmethod
    def _draw_dirt(surf, cx, ground, k):
        """Terrones que saltan mientras el cuerpo se hunde."""
        for i, (vx, vy) in enumerate(((-55, 70), (-25, 95), (10, 85), (35, 100), (60, 65))):
            tt = (k * 0.9 + i * 0.07) % 0.6     # cada terrón salta en su momento
            x = cx + vx * tt
            y = ground - (vy * tt - 260 * tt * tt)
            if y <= ground:
                pygame.draw.circle(surf, S.DIRT if i % 2 else S.DIRT_DARK, (x, y), 2)

    @staticmethod
    def _draw_tombstone(surf, x, ground, k):
        """Lápida de piedra con una cruz, saliendo del suelo (k de 0 a 1)."""
        w, h = 22, 30
        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), ground).clip(old_clip))
        stone = pygame.Rect(0, 0, w, h)
        stone.midbottom = (x, ground + round((1 - k) * h) + 2)  # +2: algo enterrada
        radius = w // 2
        pygame.draw.rect(surf, S.STONE, stone, border_top_left_radius=radius,
                         border_top_right_radius=radius)
        pygame.draw.rect(surf, S.STONE_DARK, stone, width=2, border_top_left_radius=radius,
                         border_top_right_radius=radius)
        cross_x, cross_y = stone.centerx, stone.y + 8
        pygame.draw.line(surf, S.STONE_DARK, (cross_x, cross_y), (cross_x, cross_y + 13), 3)
        pygame.draw.line(surf, S.STONE_DARK, (cross_x - 5, cross_y + 4),
                         (cross_x + 5, cross_y + 4), 3)
        surf.set_clip(old_clip)

    def _draw_ghost(self, surf, g):
        """Enemigo eliminado: ojos en cruz, alas que aletean y 60 % de opacidad."""
        wing_w = round(18 * S.GHOST_WING_SCALE)
        pad_x, pad_y = wing_w + 2, round(14 * S.GHOST_WING_SCALE)  # sitio para que no se recorten
        w, h = g.rect.size
        layer = pygame.Surface((w + 2 * pad_x, h + 2 * pad_y), pygame.SRCALPHA)
        body = pygame.Rect(pad_x, pad_y, w, h)
        flap = abs(math.sin(g.t * 10))                       # aleteo
        for side in (-1, 1):
            wing_h = (8 + 8 * flap) * S.GHOST_WING_SCALE
            wing = pygame.Rect(0, 0, wing_w, wing_h)
            if side < 0:
                wing.midright = (body.left + 4, body.y + 12 - flap * 4)
            else:
                wing.midleft = (body.right - 4, body.y + 12 - flap * 4)
            pygame.draw.ellipse(layer, S.WING, wing)
            pygame.draw.ellipse(layer, S.WING_EDGE, wing, 1)
        if g.kind == "laser":
            color = (40, 90, 255) if g.angry else S.ENEMY_BLUE
        else:
            color = (255, 60, 60) if g.angry else S.ENEMY
        pygame.draw.rect(layer, color, body, border_radius=8)
        for dx in (-6, 6):
            self._draw_x_eye(layer, (body.centerx + dx, body.y + 12), 4)
        layer.set_alpha(S.GHOST_ALPHA)
        camera = round(self.world.camera_y)
        surf.blit(layer, (g.rect.x - pad_x, S.HUD_H + g.rect.y - camera - pad_y))

    def _draw_player(self, surf, p):
        if p.invuln > 0 and int(self.t * 10) % 2 == 0:
            return  # parpadeo
        pygame.draw.rect(surf, S.PLAYER, p.rect, border_radius=10)
        ex = p.rect.centerx + p.facing * 5
        pygame.draw.circle(surf, S.WHITE, (ex, p.rect.y + 12), 5)
        pygame.draw.circle(surf, S.BLACK, (ex + p.facing * 2, p.rect.y + 12), 2)

    def _draw_enemy(self, surf, e):
        if e.kind == "tongue" and e.tired and not e.attacking:
            self._draw_enemy_leaning(surf, e)
            return
        self._draw_enemy_body(surf, e)

    def _draw_enemy_leaning(self, surf, e):
        """Cansado: se dibuja en una capa aparte y se inclina hacia delante (hacia donde
        camina), girando sobre los pies para que siga apoyado en el suelo."""
        pad = 16
        layer = pygame.Surface((e.rect.width + 2 * pad, e.rect.height + 2 * pad), pygame.SRCALPHA)
        real = e.rect.topleft
        e.rect.topleft = (pad, pad)          # dibujar en coordenadas de la capa
        try:
            self._draw_enemy_body(layer, e)
            feet = e.rect.midbottom
        finally:
            e.rect.topleft = real
        # Recortar un poco por debajo de los pies (sitio para la punta de la lengua) para que
        # el giro sea, aproximadamente, sobre ellos
        below = 4
        layer = layer.subsurface((0, 0, layer.get_width(), feet[1] + below)).copy()
        leaned = pygame.transform.rotozoom(layer, -e.direction * S.TIRED_LEAN, 1.0)  # suavizado
        x, y = e.rect.midbottom
        surf.blit(leaned, leaned.get_rect(midbottom=(x, y + below)))

    def _draw_enemy_body(self, surf, e):
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
            if e.tired:
                self._draw_open_mouth(surf, e, mx, my)
                self._draw_tired_tongue(surf, e, mx, my)
                pts = self._open_mouth_points(e, mx, my)
                pygame.draw.line(surf, S.BLACK, pts[0], pts[1], 2)  # labio de arriba, sobre la lengua
            else:
                pygame.draw.line(surf, S.BLACK, (mx - e.direction * 8, my),
                                 (mx - e.direction * 2, my), 2)
            return
        tip = (mx + e.direction * int(e.tongue_length), my)
        pygame.draw.line(surf, S.TONGUE, (mx - e.direction * 4, my), tip, 6)
        pygame.draw.circle(surf, S.TONGUE, tip, 7)
        pygame.draw.circle(surf, (200, 60, 110), tip, 7, 2)

    @staticmethod
    def _open_mouth_points(e, mx, my):
        """Cuña de la boca abierta: vértice dentro del cuerpo y abertura de
        TIRED_MOUTH_ANGLE grados en el borde, hacia donde mira."""
        depth = S.TIRED_MOUTH_DEPTH
        half = depth * math.tan(math.radians(S.TIRED_MOUTH_ANGLE / 2))
        vertex = (mx - e.direction * depth, my)
        return [vertex, (mx, my - half), (mx, my + half)]

    def _draw_open_mouth(self, surf, e, mx, my):
        pts = self._open_mouth_points(e, mx, my)
        pygame.draw.polygon(surf, S.MOUTH_INSIDE, pts)
        pygame.draw.lines(surf, S.BLACK, False, [pts[1], pts[0], pts[2]], 2)  # labios

    def _draw_tired_tongue(self, surf, e, mx, my):
        """Cansado: la lengua nace dentro de la boca abierta, sale por la abertura y se curva
        cayendo hacia abajo; se estira y encoge al jadear."""
        pant = abs(math.sin(self.t * 12 + e.rect.x * 0.1))     # cada enemigo a su ritmo
        length = S.TIRED_TONGUE_LEN + S.TIRED_TONGUE_PANT * pant
        d = e.direction
        # Curva de Bézier: base en la boca -> sale hacia fuera -> cae hacia abajo
        p0 = (mx - d * S.TIRED_MOUTH_DEPTH * 0.45, my + 1.5)   # dentro de la boca, mitad baja
        p1 = (p0[0] + d * length * 0.95, p0[1] - length * 0.05)
        p2 = (p0[0] + d * length * 0.85, p0[1] + length * 0.95)
        points = []
        for i in range(13):
            u = i / 12
            points.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                           (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
        for i, pt in enumerate(points):                        # se ensancha hacia la punta
            pygame.draw.circle(surf, S.TONGUE, pt, 2.5 + 1.5 * i / 12)
        pygame.draw.lines(surf, (200, 60, 110), False, points[1:10], 1)  # surco central

    @staticmethod
    def laser_pupil_color(e):
        """Pupilas del enemigo azul: negras mientras recarga, rojas cuando está cargado."""
        return S.LASER if e.charged else S.BLACK

    def _draw_laser_eye(self, surf, e, pupil):
        if e.attack is not None:  # a punto de disparar o disparando: ojos al rojo vivo
            glow = 3 + int(2 * abs(math.sin(self.t * 20)))
            pygame.draw.circle(surf, S.LASER, pupil, glow)
        else:
            pygame.draw.circle(surf, self.laser_pupil_color(e), pupil, 2)

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
        dim = pygame.Surface((S.LOGICAL_W, S.HUD_H + S.FIELD_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surf.blit(dim, (0, 0))
        center = (S.LOGICAL_W // 2, S.HUD_H + S.FIELD_H // 2)
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
