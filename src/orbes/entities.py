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
    """Enemigo base: camina, salta al azar y ataca si ve al jugador delante y a su altura.

    Las subclases definen el ataque con ``_start_attack``, ``_attack_step`` y ``attack_rect``.
    """

    kind = "base"
    SIGHT = 0             # alcance de visión en píxeles
    EYE_Y = 12            # altura de los ojos dentro del cuerpo

    def __init__(self, x, y, speed, rng):
        super().__init__(x + 6, y + 8, 28, 32)
        self.speed = speed
        self.rng = rng
        self.direction = rng.choice((-1, 1))
        self.state = "walk"      # "walk" | "trapped"
        self.alive = True
        self.angry = False
        self.jump_cd = rng.uniform(1.0, 3.0)
        self.attack = None       # None o fase del ataque en curso
        self.attack_t = 0.0      # tiempo en la fase actual
        self.cooldown = rng.uniform(0.5, 1.5)
        self.cooldown_factor = 1.0   # lo ajusta la dificultad

    @property
    def attacking(self) -> bool:
        return self.attack is not None

    def trap(self):
        self.state = "trapped"
        self.vx = self.vy = 0.0
        self.attack = None

    def release(self):
        """Se escapa de la burbuja: vuelve a caminar, enfadado."""
        self.state = "walk"
        self.angry = True
        self.vy = 0.0

    def sees(self, target) -> bool:
        """El objetivo está delante, a la altura de los ojos y dentro del alcance."""
        eye_y = self.rect.y + self.EYE_Y
        if not (target.top - 6 <= eye_y <= target.bottom + 6):
            return False
        dx = target.centerx - self.rect.centerx
        return dx * self.direction > 0 and abs(dx) <= self.SIGHT

    def update(self, dt, solids, oneway, target=None):
        if self.state != "walk":
            return
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.attack is None and self.cooldown <= 0 and self.coyote > 0 \
                and target is not None and self.sees(target):
            self.attack_t = 0.0
            self._start_attack(solids)
        if self.attack is not None:
            self.vx = 0.0  # quieto mientras ataca
            self.attack_t += dt
            self._attack_step(solids)
            self.physics(dt, solids, oneway)
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

    def _start_attack(self, solids):
        pass

    def _attack_step(self, solids):
        pass

    def attack_rect(self):
        """Zona que hace daño al jugador ahora mismo, o None."""
        return None

    def _end_attack(self, cooldown):
        self.attack = None
        self.cooldown = cooldown * self.cooldown_factor


class TongueEnemy(Enemy):
    """Rojo: saca una lengua larga hacia delante (sale, aguanta y se recoge)."""

    kind = "tongue"
    SIGHT = S.TONGUE_RANGE + 14
    MOUTH_Y = 22

    def _start_attack(self, solids):
        self.attack = "tongue"

    def _attack_step(self, solids):
        if self.attack_t >= S.TONGUE_OUT + S.TONGUE_HOLD + S.TONGUE_IN:
            self._end_attack(S.TONGUE_COOLDOWN)

    @property
    def tongue_length(self) -> float:
        if self.attack != "tongue":
            return 0.0
        t = self.attack_t
        if t < S.TONGUE_OUT:
            k = t / S.TONGUE_OUT
        elif t < S.TONGUE_OUT + S.TONGUE_HOLD:
            k = 1.0
        else:
            k = max(0.0, 1.0 - (t - S.TONGUE_OUT - S.TONGUE_HOLD) / S.TONGUE_IN)
        return S.TONGUE_RANGE * k

    def mouth(self):
        x = self.rect.right if self.direction > 0 else self.rect.left
        return x, self.rect.y + self.MOUTH_Y

    def attack_rect(self):
        length = int(self.tongue_length)
        if length <= 0:
            return None
        mx, my = self.mouth()
        x = mx if self.direction > 0 else mx - length
        return Rect(x, my - 5, length, 10)


class LaserEnemy(Enemy):
    """Azul: lanza un rayo láser por los ojos durante 1 s y luego recarga 4 s."""

    kind = "laser"
    SIGHT = S.FIELD_W

    def __init__(self, x, y, speed, rng):
        super().__init__(x, y, speed, rng)
        self.beam_end = 0

    @property
    def charged(self) -> bool:
        return self.cooldown <= 0

    @property
    def charge(self) -> float:
        """0 = recién disparado, 1 = energía completa."""
        return 1.0 - self.cooldown / (S.LASER_RECHARGE * self.cooldown_factor)

    def _start_attack(self, solids):
        self.attack = "windup" if S.LASER_WINDUP > 0 else "fire"
        self._aim(solids)

    def _attack_step(self, solids):
        if self.attack == "windup" and self.attack_t >= S.LASER_WINDUP:
            self.attack, self.attack_t = "fire", 0.0
        elif self.attack == "fire":
            self._aim(solids)
            if self.attack_t >= S.LASER_DURATION:
                self._end_attack(S.LASER_RECHARGE)

    def eyes(self):
        x = self.rect.right if self.direction > 0 else self.rect.left
        return x, self.rect.y + self.EYE_Y

    def _aim(self, solids):
        """El rayo llega hasta el primer muro en la dirección en la que mira."""
        ex, ey = self.eyes()
        if self.direction > 0:
            end = min((s.left for s in solids
                       if s.top <= ey <= s.bottom and s.left >= ex), default=S.FIELD_W)
        else:
            end = max((s.right for s in solids
                       if s.top <= ey <= s.bottom and s.right <= ex), default=0)
        self.beam_end = end

    def attack_rect(self):
        if self.attack != "fire":
            return None
        ex, ey = self.eyes()
        left, right = sorted((ex, self.beam_end))
        return Rect(left, ey - 4, right - left, 8)


ENEMY_TYPES = {"E": TongueEnemy, "B": LaserEnemy}


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
