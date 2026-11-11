"""Reglas del juego sin dependencia de ventana ni de dibujo."""

import logging
import math
import random

from pygame import Rect

from . import settings as S
from .entities import ENEMY_TYPES, Bomb, Bubble, Coin, Ghost, Medkit, Player, Star
from . import levels
from .levels import parse_level

log = logging.getLogger(__name__)

# Zona interior de un nivel de 16 filas (dentro de los bordes). Cada mundo tiene la suya
# en ``World.interior``, que depende de la altura del nivel.
INTERIOR = Rect(S.BORDER, S.BORDER, S.FIELD_W - 2 * S.BORDER, S.FIELD_H - 2 * S.BORDER)

# Pasos del tutorial, en orden. Cada uno se completa con el evento del mismo nombre;
# el texto de ayuda es la clave de traducción "tutorial.<paso>".
TUTORIAL_STEPS = ("move", "jump", "drop", "bubble", "trap", "pop", "clear", "star")


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
        self.hearts_gained = 0.0     # corazones ganados al superar el nivel
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
        self.bricks = data.bricks
        self.oneway = data.oneway
        self.height = data.height                 # alto del mundo (px)
        self.level_rows = data.rows
        self.floor_y = data.height - S.BORDER     # superficie del suelo
        self.interior = Rect(S.BORDER, S.BORDER, S.FIELD_W - 2 * S.BORDER,
                             data.height - 2 * S.BORDER)
        self.spawn = data.player_spawn
        self.player = Player(*self.spawn)
        steps = min(max(0, self.number - 1), S.ENEMY_SPEED_MAX_STEPS)
        speed = S.ENEMY_BASE_SPEED + S.ENEMY_SPEED_STEP * steps
        speed *= self.rules["enemy_speed"]
        self.enemies = [ENEMY_TYPES[kind](x, y, speed, self.rng)
                        for x, y, kind in data.enemy_spawns]
        self._assign_zones()
        for e in self.enemies:
            e.cooldown_factor = self.rules["cooldown"]
            e.attack_delay = self.rules["attack_delay"]
        self.bubbles: list[Bubble] = []
        self.star = Star(*data.star_pos) if data.star_pos else None
        self.medkits = [Medkit(x, y) for x, y in data.medkits]
        self.coins = [Coin(x, y) for x, y in data.coins]
        self.bombs = [Bomb(x, y) for x, y in data.bombs]
        self.explosions: list = []   # animaciones de explosión: [x, y, tiempo]
        self.popups: list = []       # textos flotantes ("+100"): [x, y, tiempo, texto, color]
        self.camera_y = 0.0
        self.snap_camera()

    # --- zonas de enemigos ---
    @property
    def zone_count(self) -> int:
        """Número de zonas: 1 en niveles de una pantalla; en los altos, una cada ~ZONE_ROWS."""
        rows = self.level_rows
        return 1 if rows <= S.ROWS else max(1, rows // S.ZONE_ROWS)

    def zone_bounds(self, index):
        """(y de arriba, y de abajo) de la zona `index`; la última llega hasta el suelo."""
        rows, n = self.level_rows, self.zone_count
        top_row, bottom_row = index * rows // n, (index + 1) * rows // n
        top = S.BORDER + top_row * S.TILE
        bottom = self.floor_y if index == n - 1 else S.BORDER + bottom_row * S.TILE
        return top, bottom

    def zone_of_row(self, row) -> int:
        return min(row * self.zone_count // self.level_rows, self.zone_count - 1)

    def _assign_zones(self):
        """Cada enemigo se queda en la zona de la plataforma donde empieza (solo en niveles
        con varias zonas)."""
        if self.zone_count == 1:
            return
        for e in self.enemies:
            spawn_row = (e.spawn[1] - 8 - S.BORDER) // S.TILE
            e.zone = self.zone_bounds(self.zone_of_row(spawn_row + 1))   # fila de su plataforma

    # --- cámara (scroll vertical) ---
    @property
    def scrolls(self) -> bool:
        """El nivel es más alto que la pantalla."""
        return self.height > S.FIELD_H

    def _camera_target(self) -> float:
        target = self.player.rect.centery - S.FIELD_H * S.CAMERA_ANCHOR
        return min(max(target, 0.0), float(self.height - S.FIELD_H))  # sin salirse del nivel

    def snap_camera(self):
        """Coloca la cámara directamente sobre el jugador (al empezar o al reaparecer)."""
        self.camera_y = self._camera_target()

    def _update_camera(self, dt):
        target = self._camera_target()
        self.camera_y += (target - self.camera_y) * min(1.0, dt * S.CAMERA_SMOOTH)
        self.camera_y = min(max(self.camera_y, 0.0), float(self.height - S.FIELD_H))

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
        self._update_popups(dt)
        self._update_explosions(dt)
        self._update_camera(dt)
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
        if p.jumps == 2:                  # el paso del salto pide el salto doble
            self._tutorial_event("jump")
        if p.just_dropped:
            self._tutorial_event("drop")
        if "bubble" in just and p.shoot_cd <= 0:
            bomb = self._bomb_under_player()
            if bomb is not None:            # encima de una bomba: la acción la enciende
                bomb.light()
                p.shoot_cd = S.SHOOT_COOLDOWN
            else:
                self._shoot()
                self._tutorial_event("bubble")
        # Sin objetivo los enemigos nunca inician un ataque (tutorial)
        target = self.player.rect if self.level.enemies_attack else None
        predicted = self._predicted_player() if target and self.rules["preempt"] else None
        self._dodge_bubbles()
        for e in self.enemies:
            if e.alive:
                e.update(dt, self.solids, self.oneway, target, predicted)
        self._update_bubbles(dt)
        self._update_bombs(dt)
        self._rescue_escaped()
        self._check_medkits()
        self._check_coins()
        self._check_player_hit()
        if self.enemies_left == 0:
            self._tutorial_event("clear")
        if self.state == "playing":
            self._check_star()

    def _predicted_player(self):
        """Dónde estará el jugador dentro de PREEMPT_LOOKAHEAD s si sigue igual (para los
        ataques preventivos): avanza con su velocidad y, si está en el aire, con la gravedad."""
        p = self.player
        t = S.PREEMPT_LOOKAHEAD
        dx = p.vx * t
        dy = 0.0 if p.on_ground or p.coyote > 0 else p.vy * t + 0.5 * S.GRAVITY * t * t
        r = p.rect.move(round(dx), round(dy))
        return r.clamp(self.interior)

    # --- red de seguridad ---
    def _rescue_escaped(self):
        """Devuelve al campo a quien se haya salido de él, para que el nivel nunca se bloquee
        (un enemigo vivo fuera de la pantalla haría imposible terminarlo)."""
        for e in self.enemies:
            if e.alive and e.state == "walk" and not self.interior.colliderect(e.rect):
                log.warning("Enemigo %s fuera del campo en %s; vuelve a su inicio",
                            e.kind, e.rect.topleft)
                e.place(*e.spawn)
                e.vx = e.vy = 0.0
                e.attack = None
        p = self.player
        if not self.interior.colliderect(p.rect):
            log.warning("Jugador fuera del campo en %s; vuelve al inicio", p.rect.topleft)
            p.respawn(self.spawn)
            self.snap_camera()

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
        # Superar un nivel da un corazón (sin pasar del máximo). En el tutorial no: al
        # terminarlo, el nivel 1 empieza con la vida inicial.
        before = self.lives
        if not self.tutorial:
            self.lives = min(self.max_lives, self.lives + S.LEVEL_HEAL)
        self.hearts_gained = self.lives - before
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
                bomb = next((m for m in self.bombs
                             if not m.lit and b.rect.colliderect(m.rect)), None)
                if bomb is not None:        # la burbuja choca contra la bomba: la enciende
                    bomb.light()
                    self.bubbles.remove(b)
                    continue
                for e in self.enemies:
                    if (e.alive and e.state == "walk" and not e.crouching   # agachado: pasa
                            and b.rect.colliderect(e.rect)):
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

    def _kill_enemy(self, e):
        """Elimina un enemigo: fantasma que sube, puntos y "+100" en su color."""
        e.alive = False
        self.ghosts.append(Ghost(e))
        self.score += S.POINTS_ENEMY
        self.popup(e.rect.centerx, e.rect.top, S.POINTS_ENEMY, S.enemy_color(e.kind, e.angry))

    def _pop(self, b):
        if b.captured is not None:
            self._kill_enemy(b.captured)
            self._tutorial_event("pop")
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
            if attack is not None and p.rect.colliderect(attack):
                self.hit_player(S.DAMAGE_ATTACK)              # lengua o láser
                return
            if p.rect.colliderect(e.rect):
                self.hit_player(S.DAMAGE_TOUCH, source=e)     # contacto
                return

    @property
    def max_lives(self) -> float:
        """Máximo de corazones de la dificultad (en difícil, más que los iniciales)."""
        return self.rules.get("max_lives", self.rules["lives"])

    def _check_medkits(self):
        """Coger un botiquín recupera un corazón (sin pasar del máximo). Con la vida al
        completo no se coge: se queda donde está para más adelante."""
        p = self.player
        for m in self.medkits:
            if m.taken or not p.rect.colliderect(m.rect):
                continue
            if self.lives >= self.max_lives:
                continue
            self.lives = min(self.max_lives, self.lives + S.MEDKIT_HEAL)
            m.taken = True
        self.medkits = [m for m in self.medkits if not m.taken]

    def _check_coins(self):
        """Coger una moneda da POINTS_COIN puntos."""
        p = self.player
        for c in self.coins:
            if not c.taken and p.rect.colliderect(c.rect):
                c.taken = True
                self.score += S.POINTS_COIN
                self.popup(c.rect.centerx, c.rect.top, S.POINTS_COIN, S.GOLD)
        self.coins = [c for c in self.coins if not c.taken]

    def popup(self, x, y, points, color):
        """Texto flotante con los puntos ganados (sube y se desvanece)."""
        self.popups.append([x, y, 0.0, f"+{points}", color])

    # --- enemigo naranja: se agacha para esquivar burbujas ---
    def _dodge_bubbles(self):
        """Cada enemigo que sabe agacharse decide UNA vez por burbuja (no en cada fotograma)
        si se agacha cuando la ve venir hacia él, a su altura y cerca."""
        for b in self.bubbles:
            if b.state != "shot" or b.captured is not None:
                continue
            for e in self.enemies:
                if not hasattr(e, "try_dodge") or not e.alive or id(e) in b.dodge_seen:
                    continue
                dx = e.rect.centerx - b.rect.centerx
                coming = dx * b.vx > 0                          # viene hacia él
                level = b.rect.top < e.rect.bottom and b.rect.bottom > e.rect.top
                if coming and level and abs(dx) <= S.DODGE_RANGE:
                    if e.try_dodge(self.rng) is not None:   # ya ha decidido con esta burbuja
                        b.dodge_seen.add(id(e))

    # --- bombas ---
    def _bomb_under_player(self):
        """Bomba apagada en la posición del jugador (para encenderla con la acción)."""
        p = self.player
        return next((m for m in self.bombs if not m.lit and p.rect.colliderect(m.rect)), None)

    def _update_bombs(self, dt):
        for m in list(self.bombs):
            if m.lit:
                m.timer -= dt
                if m.timer <= 0:
                    self.explode(m)

    def explode(self, bomb):
        """Explota: elimina a los enemigos a menos de BOMB_RADIUS en cualquier dirección
        (también los atrapados en burbujas) y enciende las bombas cercanas."""
        if bomb not in self.bombs:
            return
        self.bombs.remove(bomb)
        cx, cy = bomb.rect.center
        self.explosions.append([cx, cy, 0.0])
        r2 = S.BOMB_RADIUS ** 2

        def near(rect):
            return (rect.centerx - cx) ** 2 + (rect.centery - cy) ** 2 <= r2

        killed = []
        for b in list(self.bubbles):                   # enemigos atrapados en burbujas
            if b.captured is not None and near(b.rect):
                killed.append(b.captured.kind)
                self._kill_enemy(b.captured)
                self.bubbles.remove(b)
        for e in self.enemies:
            if e.alive and e.state == "walk" and near(e.rect):
                killed.append(e.kind)
                self._kill_enemy(e)
        chained = 0
        for other in self.bombs:                       # reacción en cadena
            if near(other.rect) and other.light():
                chained += 1
        col, row = ((v - S.BORDER) // S.TILE for v in bomb.cell)   # casilla del mapa
        log.info("Bomba explotada en el nivel %s, casilla (columna %d, fila %d): "
                 "%d enemigos eliminados (%d rojos, %d azules), %d bombas encendidas en "
                 "cadena, quedan %d enemigos", self.number, col, row, len(killed),
                 killed.count("tongue"), killed.count("laser"), chained, self.enemies_left)

    def _update_explosions(self, dt):
        for ex in self.explosions:
            ex[2] += dt
        # Se mantiene mientras dure el humo (dura más que el fuego)
        life = max(S.EXPLOSION_TIME, S.SMOKE_TIME)
        self.explosions = [ex for ex in self.explosions if ex[2] < life]

    def _update_popups(self, dt):
        for pop in self.popups:
            pop[2] += dt
            pop[1] -= 30 * dt                     # suben
        self.popups = [pop for pop in self.popups if pop[2] < S.POPUP_TIME]

    def hit_player(self, damage, source=None):
        """Resta `damage` corazones. Muere si se ha vaciado algún corazón entero (los ataques
        siempre; el contacto solo si completa un corazón); si no, queda herido y sigue."""
        before = self.lives
        self.lives = max(0.0, round((self.lives - damage) * 2) / 2)   # en medios corazones
        emptied = math.ceil(before) > math.ceil(self.lives)          # se vació un corazón
        if emptied or self.lives <= 0 or damage >= S.DAMAGE_ATTACK:
            self._die()
            return
        self._hurt(source)

    def _hurt(self, source):
        """Herido sin morir: un empujón para separarse del enemigo y un rato invulnerable."""
        p = self.player
        p.invuln = S.HURT_INVULN
        away = 1 if source is None or p.rect.centerx >= source.rect.centerx else -1
        p.knockback = (away * S.KNOCKBACK_SPEED, S.KNOCKBACK_TIME)
        p.vy = min(p.vy, -180.0)                  # saltito

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
        if self.death_t >= self.death_duration:
            self.finish_dying()

    @property
    def final_death(self) -> bool:
        """Muerte sin vidas: termina con la tumba y el fin de la partida."""
        return self.player.dead and self.lives <= 0

    @property
    def death_duration(self) -> float:
        """Tiempo desde que cae al suelo hasta reaparecer o terminar la partida."""
        if not self.final_death:
            return S.DEATH_TIME
        return S.DEATH_TIP_TIME + S.GRAVE_LIE + S.GRAVE_SINK + S.GRAVE_RISE + S.GRAVE_HOLD

    @property
    def grave_progress(self) -> tuple[float, float]:
        """(hundimiento, lápida), cada uno de 0 a 1, en la muerte final."""
        if not (self.final_death and self.player.landed_dead):
            return 0.0, 0.0
        start = S.DEATH_TIP_TIME + S.GRAVE_LIE
        sink = min(1.0, max(0.0, (self.death_t - start) / S.GRAVE_SINK))
        rise_start = start + S.GRAVE_SINK * S.GRAVE_RISE_START
        rise = min(1.0, max(0.0, (self.death_t - rise_start) / S.GRAVE_RISE))
        return sink, rise

    def finish_dying(self):
        """Termina la animación: reaparece si quedan vidas; si no, fin de la partida."""
        if self.state != "dying":
            return
        if self.lives <= 0:
            self.state = "lost"
            return
        self.player.respawn(self.spawn)
        self.state = "playing"
        self.snap_camera()           # reaparece abajo del todo: la cámara salta con él

    def _update_ghosts(self, dt):
        for g in self.ghosts:
            g.update(dt)
        self.ghosts = [g for g in self.ghosts if not g.gone(self.camera_y)]
