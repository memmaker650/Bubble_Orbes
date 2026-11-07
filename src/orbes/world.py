"""Reglas del juego sin dependencia de ventana ni de dibujo."""

import logging
import random

from pygame import Rect

from . import settings as S
from .entities import ENEMY_TYPES, Bubble, Ghost, Player, Star
from . import levels
from .levels import parse_level

log = logging.getLogger(__name__)

# Zona interior del nivel (dentro de los bordes)
INTERIOR = Rect(S.BORDER, S.BORDER, S.FIELD_W - 2 * S.BORDER, S.FIELD_H - 2 * S.BORDER)

# Pasos del tutorial, en orden. Cada uno se completa con el evento del mismo nombre;
# el texto de ayuda es la clave de traducción "tutorial.<paso>".
TUTORIAL_STEPS = ("move", "jump", "bubble", "trap", "pop", "clear", "star")


class World:
    def __init__(self, level_index=0, lives=None, score=0, seed=None,
                 difficulty=S.DEFAULT_DIFFICULTY):
        self.rng = random.Random(seed)
        self.level_index = level_index
        if difficulty not in S.DIFFICULTIES:
            difficulty = S.DEFAULT_DIFFICULTY
        self.difficulty = difficulty
        self.rules = S.DIFFICULTIES[difficulty]
        self.lives = self.rules["lives"] if lives is None else lives
        self.score = score
        self.state = "playing"   # "playing" | "dying" | "won" | "lost"
        self.ghosts: list[Ghost] = []     # enemigos eliminados subiendo al cielo
        self.death_t = 0.0                # tiempo tumbado (animación de muerte)
        self.level_start_score = score
        self.elapsed = 0.0       # segundos jugados en este nivel
        self.message = ""        # clave de traducción del aviso temporal
        self.message_timer = 0.0
        self._touching_star = False
        self._prev: set = set()
        self.tutorial_done: set = set()   # pasos del tutorial ya hechos
        # Celebración de fin de nivel: el jugador termina su salto, hace pie y saluda
        self.landed = False
        self.win_t = 0.0             # tiempo desde que se tocó la estrella
        self.celebrate_t = 0.0       # tiempo celebrando ya en el suelo
        self.load_level()
        if self.tutorial:
            self.show_message("tutorial.safe")

    @property
    def is_last_level(self) -> bool:
        return self.level_index >= len(levels.LEVELS) - 1

    @property
    def number(self) -> int:
        """Número de nivel que ve el jugador (0 = tutorial)."""
        return self.level.number

    @property
    def tutorial(self) -> bool:
        return self.level.tutorial

    @property
    def tutorial_step(self) -> str | None:
        """Paso del tutorial que toca ahora, o None si no es tutorial o ya terminó."""
        if not self.tutorial or self.state != "playing":
            return None
        return next((s for s in TUTORIAL_STEPS if s not in self.tutorial_done), None)

    def _tutorial_event(self, name):
        if self.tutorial:
            self.tutorial_done.add(name)

    def load_level(self):
        self.level = levels.LEVELS[self.level_index]
        data = parse_level(self.level.rows)
        self.solids = data.solids
        self.oneway = data.oneway
        self.spawn = data.player_spawn
        self.player = Player(*self.spawn)
        speed = S.ENEMY_BASE_SPEED + S.ENEMY_SPEED_STEP * max(0, self.number - 1)
        speed *= self.rules["enemy_speed"]
        self.enemies = [ENEMY_TYPES[kind](x, y, speed, self.rng)
                        for x, y, kind in data.enemy_spawns]
        for e in self.enemies:
            e.cooldown_factor = self.rules["cooldown"]
        self.bubbles: list[Bubble] = []
        self.star = Star(*data.star_pos) if data.star_pos else None

    @property
    def level_points(self) -> int:
        """Puntos conseguidos en este nivel (incluye el bonus de nivel)."""
        return self.score - self.level_start_score

    @property
    def enemies_left(self) -> int:
        return sum(1 for e in self.enemies if e.alive)

    def show_message(self, key):
        self.message = key
        self.message_timer = S.MESSAGE_TIME

    def update(self, dt, actions):
        self.message_timer = max(0.0, self.message_timer - dt)
        self._update_ghosts(dt)
        if self.state == "dying":
            self._update_dying(dt)
            return
        if self.state == "won":
            self._update_celebration(dt)
            return
        if self.state != "playing":
            return
        self.elapsed += dt
        pressed = set(actions)
        just = pressed - self._prev   # acciones recién pulsadas este frame
        self._prev = pressed

        p = self.player
        p.update(dt, pressed, just, self.solids, self.oneway)
        if pressed & {"left", "right"}:
            self._tutorial_event("move")
        if "jump" in just:
            self._tutorial_event("jump")
        if "bubble" in just and p.shoot_cd <= 0:
            self._shoot()
            self._tutorial_event("bubble")
        # Sin objetivo los enemigos nunca inician un ataque (tutorial)
        target = self.player.rect if self.level.enemies_attack else None
        for e in self.enemies:
            if e.alive:
                e.update(dt, self.solids, self.oneway, target)
        self._update_bubbles(dt)
        self._rescue_escaped()
        self._check_player_hit()
        if self.enemies_left == 0:
            self._tutorial_event("clear")
        if self.state == "playing":
            self._check_star()

    # --- red de seguridad ---
    def _rescue_escaped(self):
        """Devuelve al campo a quien se haya salido de él, para que el nivel nunca se bloquee
        (un enemigo vivo fuera de la pantalla haría imposible terminarlo)."""
        for e in self.enemies:
            if e.alive and e.state == "walk" and not INTERIOR.colliderect(e.rect):
                log.warning("Enemigo %s fuera del campo en %s; vuelve a su inicio",
                            e.kind, e.rect.topleft)
                e.place(*e.spawn)
                e.vx = e.vy = 0.0
                e.attack = None
        p = self.player
        if not INTERIOR.colliderect(p.rect):
            log.warning("Jugador fuera del campo en %s; vuelve al inicio", p.rect.topleft)
            p.respawn(self.spawn)

    # --- estrella ---
    def _check_star(self):
        if self.star is None:  # nivel sin estrella: se gana al vaciarlo
            if self.enemies_left == 0:
                self._win()
            return
        touching = self.player.rect.colliderect(self.star.rect)
        if touching and not self._touching_star:  # solo al empezar a tocarla
            if self.enemies_left > 0:
                self.show_message("star.kill_all")
            else:
                self.star.lit = True
                self._win()
        self._touching_star = touching

    def _win(self):
        self.state = "won"
        self.score += S.POINTS_LEVEL
        self.message_timer = 0.0
        self.player.invuln = 0.0     # sin parpadeo durante la celebración
        self.landed = False
        self.win_t = self.celebrate_t = 0.0

    # --- celebración ---
    @property
    def celebrating(self) -> bool:
        """El jugador ya está en el suelo saludando."""
        return self.state == "won" and self.landed

    @property
    def celebration_done(self) -> bool:
        """Ya se puede mostrar la ventana de nivel completado."""
        if self.state != "won":
            return False
        return self.celebrate_t >= S.CELEBRATE_TIME or self.win_t >= S.CELEBRATE_MAX

    def _update_celebration(self, dt):
        self.win_t += dt
        p = self.player
        if not self.landed:
            # Sin control: conserva el impulso horizontal y cae hasta hacer pie
            p.physics(dt, self.solids, self.oneway)
            if p.on_ground:
                self.landed = True
                p.vx = 0.0
        else:
            self.celebrate_t += dt

    # --- burbujas ---
    def _shoot(self):
        p = self.player
        p.shoot_cd = S.SHOOT_COOLDOWN
        cx, cy = p.rect.center
        self.bubbles.append(Bubble(cx + p.facing * 26, cy, p.facing))

    def _update_bubbles(self, dt):
        for b in list(self.bubbles):
            b.update(dt, self.solids)
            if b.state == "shot" and b.captured is None:
                for e in self.enemies:
                    if e.alive and e.state == "walk" and b.rect.colliderect(e.rect):
                        e.trap()
                        self._tutorial_event("trap")
                        b.captured = e
                        b.life = self.rules["bubble_life"]
                        b._to_float()
                        break
            if b.state == "float":
                if b.armed and b.rect.colliderect(self.player.rect):
                    self._pop(b)
                elif b.life <= 0:
                    self._expire(b)

    def _pop(self, b):
        if b.captured is not None:
            b.captured.alive = False
            self.ghosts.append(Ghost(b.captured))
            self._tutorial_event("pop")
            self.score += S.POINTS_ENEMY
        else:
            self.score += S.POINTS_BUBBLE
        self.bubbles.remove(b)

    def _expire(self, b):
        e = b.captured
        if e is not None:  # el enemigo se escapa, más rápido y enfadado
            e.release()
        self.bubbles.remove(b)

    # --- daño ---
    def _check_player_hit(self):
        p = self.player
        if p.invuln > 0 or not self.level.enemies_attack:
            return
        for e in self.enemies:
            if not (e.alive and e.state == "walk"):
                continue
            attack = e.attack_rect()
            if p.rect.colliderect(e.rect) or (attack is not None and p.rect.colliderect(attack)):
                self.lives -= 1
                self._die()
                return

    # --- muerte del jugador ---
    def _die(self):
        """Empieza la animación de muerte: la acción se detiene, el jugador cae hasta el suelo
        y se queda tumbado con el ojo en X. Después reaparece o termina la partida."""
        self.state = "dying"
        self.death_t = 0.0
        p = self.player
        p.dead = True
        p.vx = 0.0
        p.vy = max(p.vy, 0.0)        # si iba subiendo, empieza a caer
        p.invuln = 0.0
        self.message_timer = 0.0

    @property
    def player_down(self) -> bool:
        """El jugador muerto ya está tumbado en el suelo."""
        return self.state in ("dying", "lost") and self.player.landed_dead

    def _update_dying(self, dt):
        p = self.player
        if not p.landed_dead:
            p.physics(dt, self.solids, self.oneway)
            if p.on_ground:
                p.landed_dead = True
            return
        self.death_t += dt
        if self.death_t >= S.DEATH_TIME:
            self.finish_dying()

    def finish_dying(self):
        """Termina la animación: reaparece si quedan vidas; si no, fin de la partida."""
        if self.state != "dying":
            return
        if self.lives <= 0:
            self.state = "lost"
            return
        self.player.respawn(self.spawn)
        self.state = "playing"

    def _update_ghosts(self, dt):
        for g in self.ghosts:
            g.update(dt)
        self.ghosts = [g for g in self.ghosts if not g.gone]
