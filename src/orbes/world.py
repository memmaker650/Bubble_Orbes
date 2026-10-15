"""Reglas del juego sin dependencia de ventana ni de dibujo."""

import random

from . import settings as S
from .entities import Bubble, Enemy, Player
from .levels import LEVELS, parse_level


class World:
    def __init__(self, level_index=0, lives=S.START_LIVES, score=0, seed=None):
        self.rng = random.Random(seed)
        self.level_index = level_index
        self.lives = lives
        self.score = score
        self.state = "playing"   # "playing" | "won" | "lost"
        self._prev: set = set()
        self.load_level()

    @property
    def is_last_level(self) -> bool:
        return self.level_index >= len(LEVELS) - 1

    def load_level(self):
        data = parse_level(LEVELS[self.level_index])
        self.solids = data.solids
        self.oneway = data.oneway
        self.spawn = data.player_spawn
        self.player = Player(*self.spawn)
        speed = S.ENEMY_BASE_SPEED + S.ENEMY_SPEED_STEP * self.level_index
        self.enemies = [Enemy(x, y, speed, self.rng) for x, y in data.enemy_spawns]
        self.bubbles: list[Bubble] = []

    def update(self, dt, actions):
        if self.state != "playing":
            return
        pressed = set(actions)
        just = pressed - self._prev   # acciones recién pulsadas este frame
        self._prev = pressed

        p = self.player
        p.update(dt, pressed, just, self.solids, self.oneway)
        if "bubble" in just and p.shoot_cd <= 0:
            self._shoot()
        for e in self.enemies:
            if e.alive:
                e.update(dt, self.solids, self.oneway)
        self._update_bubbles(dt)
        self._check_player_hit()

        if self.state == "playing" and not any(e.alive for e in self.enemies):
            self.state = "won"
            self.score += S.POINTS_LEVEL

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
                        e.state = "trapped"
                        e.vx = e.vy = 0.0
                        b.captured = e
                        b.life = S.BUBBLE_ENEMY_LIFE
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
            self.score += S.POINTS_ENEMY
        else:
            self.score += S.POINTS_BUBBLE
        self.bubbles.remove(b)

    def _expire(self, b):
        e = b.captured
        if e is not None:  # el enemigo se escapa, más rápido y enfadado
            e.state = "walk"
            e.angry = True
            e.vy = 0.0
        self.bubbles.remove(b)

    # --- daño ---
    def _check_player_hit(self):
        p = self.player
        if p.invuln > 0:
            return
        for e in self.enemies:
            if e.alive and e.state == "walk" and p.rect.colliderect(e.rect):
                self.lives -= 1
                if self.lives <= 0:
                    self.state = "lost"
                else:
                    p.respawn(self.spawn)
                return
