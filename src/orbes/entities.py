"""Entidades del juego. Lógica pura (solo pygame.Rect): se puede testear sin ventana."""

import math

from pygame import Rect

from . import settings as S


class Body:
    """Caja con gravedad y colisiones contra muros y plataformas de un solo sentido."""

    def __init__(self, x, y, w, h):
        self.rect = Rect(x, y, w, h)
        self.fx = float(x)
        self.fy = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.coyote = 0.0  # pequeño margen para saltar justo tras pisar suelo

    def place(self, x, y):
        self.rect.topleft = (int(x), int(y))
        self.fx, self.fy = float(self.rect.x), float(self.rect.y)

    def center_on(self, pos):
        self.rect.center = pos
        self.fx, self.fy = float(self.rect.x), float(self.rect.y)

    def physics(self, dt, solids, oneway) -> bool:
        """Mueve el cuerpo. Devuelve True si chocó lateralmente con un muro."""
        blocked = False

        # Horizontal
        self.fx += self.vx * dt
        self.rect.x = round(self.fx)
        for s in solids:
            if self.rect.colliderect(s):
                if self.vx > 0:
                    self.rect.right = s.left
                elif self.vx < 0:
                    self.rect.left = s.right
                blocked = True
        self.fx = float(self.rect.x)

        # Vertical
        prev_bottom = self.rect.bottom
        self.vy = min(self.vy + S.GRAVITY * dt, S.MAX_FALL)
        falling = self.vy > 0
        self.fy += self.vy * dt
        self.rect.y = round(self.fy)
        self.on_ground = False
        for s in solids:
            if self.rect.colliderect(s):
                if self.vy > 0:
                    self.rect.bottom = s.top
                    self.on_ground = True
                elif self.vy < 0:
                    self.rect.top = s.bottom
                self.vy = 0.0
                self.fy = float(self.rect.y)
        if falling:
            for p in oneway:
                if self.rect.colliderect(p) and prev_bottom <= p.top:
                    self.rect.bottom = p.top
                    self.on_ground = True
                    self.vy = 0.0
                    self.fy = float(self.rect.y)

        if self.on_ground:
            self.coyote = S.COYOTE_TIME
        else:
            self.coyote = max(0.0, self.coyote - dt)
        return blocked


class Player(Body):
    def __init__(self, x, y):
        super().__init__(x + 6, y + 8, 28, 32)  # centrado en su celda de 40x40
        self.facing = 1
        self.shoot_cd = 0.0
        self.invuln = 0.0

    def respawn(self, spawn):
        self.place(spawn[0] + 6, spawn[1] + 8)
        self.vx = self.vy = 0.0
        self.invuln = S.INVULN_TIME

    def update(self, dt, pressed, just, solids, oneway):
        dirx = ("right" in pressed) - ("left" in pressed)
        self.vx = dirx * S.PLAYER_SPEED
        if dirx:
            self.facing = dirx
        if "jump" in just and self.coyote > 0:
            self.vy = -S.JUMP_V
            self.coyote = 0.0
        self.physics(dt, solids, oneway)
        self.shoot_cd = max(0.0, self.shoot_cd - dt)
        self.invuln = max(0.0, self.invuln - dt)


class Enemy(Body):
    def __init__(self, x, y, speed, rng):
        super().__init__(x + 6, y + 8, 28, 32)
        self.speed = speed
        self.rng = rng
        self.direction = rng.choice((-1, 1))
        self.state = "walk"      # "walk" | "trapped"
        self.alive = True
        self.angry = False
        self.jump_cd = rng.uniform(1.0, 3.0)

    def update(self, dt, solids, oneway):
        if self.state != "walk":
            return
        speed = self.speed * (S.ENEMY_ANGRY_FACTOR if self.angry else 1.0)
        self.vx = self.direction * speed
        self.jump_cd -= dt
        if self.jump_cd <= 0 and self.coyote > 0:
            self.vy = -S.JUMP_V
            self.coyote = 0.0
            self.jump_cd = self.rng.uniform(1.5, 4.0)
        if self.physics(dt, solids, oneway):
            self.direction *= -1


class Bubble:
    def __init__(self, cx, cy, direction):
        s = S.BUBBLE_SIZE
        self.rect = Rect(0, 0, s, s)
        self.rect.center = (cx, cy)
        self.fx, self.fy = float(self.rect.x), float(self.rect.y)
        self.vx = direction * S.BUBBLE_SPEED
        self.state = "shot"      # "shot" (horizontal) -> "float" (sube)
        self.timer = S.BUBBLE_SHOT_TIME
        self.life = S.BUBBLE_EMPTY_LIFE
        self.age = 0.0
        self.captured = None     # Enemy atrapado, si hay

    @property
    def armed(self) -> bool:
        return self.age >= S.BUBBLE_ARM_TIME

    def _to_float(self):
        self.state = "float"
        self.vx = 0.0

    def update(self, dt, solids):
        self.age += dt
        if self.state == "shot":
            step = self.vx * dt
            self.fx += step
            self.rect.x = round(self.fx)
            if any(self.rect.colliderect(s) for s in solids):
                self.fx -= step
                self.rect.x = round(self.fx)
                self._to_float()
            self.timer -= dt
            if self.timer <= 0:
                self._to_float()
        else:
            self.fy = max(float(S.TILE), self.fy - S.BUBBLE_RISE * dt)
            self.fx += math.sin(self.age * 3.0) * 18.0 * dt
            self.fx = min(max(self.fx, float(S.TILE)),
                          float(S.FIELD_W - S.TILE - S.BUBBLE_SIZE))
            self.rect.topleft = (round(self.fx), round(self.fy))
            self.life -= dt
        if self.captured is not None:
            self.captured.center_on(self.rect.center)


class Star:
    """Estrella de 5 puntas: al tocarla con todos los enemigos muertos se vuelve azul."""

    def __init__(self, x, y):
        s = S.STAR_SIZE
        self.rect = Rect(0, 0, s, s)
        self.rect.center = (x + S.TILE // 2, y + S.TILE // 2)
        self.lit = False         # False = amarilla, True = azul (nivel terminado)

    def points(self, scale=1.0):
        """Vértices del polígono de la estrella (10 puntos alternando radio exterior/interior)."""
        cx, cy = self.rect.center
        outer = self.rect.width / 2 * scale
        inner = outer * 0.45
        pts = []
        for i in range(10):
            r = outer if i % 2 == 0 else inner
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts
