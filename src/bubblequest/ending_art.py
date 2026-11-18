"""Dibujo de la animación final (tras el nivel 30): una mazmorra de piedra con una ventana
por la que se ve la luna, antorchas, el gusano encerrado en una cárcel y el púlpito con los
cinco huecos de las gemas.

El fondo fijo se dibuja una vez con ``ending_background``; lo que se anima (antorchas,
gusano, barrotes, gemas y brillos) se dibuja cada fotograma con las funciones de abajo.
"""

import math

import pygame

from . import settings as S
from .display import opaque_surface
from .ui import draw_gem, gem_points, transparent_layer

FLOOR_Y = 600                                    # suelo de la mazmorra
WINDOW = pygame.Rect(36, 120, 132, 170)          # hueco de la ventana (con arco arriba)
MOON_POS = (112, 186)
MOON_R = 30
TORCHES = (236, 360)                             # x de las antorchas (altura TORCH_Y)
TORCH_Y = 250
CAGE = pygame.Rect(256, 404, 116, FLOOR_Y - 404)  # cárcel del gusano
WORM_X = 322
PULPIT_X = 146                                  # centro del púlpito
PULPIT_TOP = 470                                 # y de la tapa (donde van las gemas)
SLOT_SIZE = 20
SLOT_GAP = 26
GEM_ORDER = tuple(S.GEM_LEVELS.values())         # rubí, esmeralda, amarilla, aguamarina, blanca

# Estrellas del cielo de la ventana: (x, y, radio)
_STARS = ((50, 150, 1), (74, 222, 1), (148, 140, 2), (60, 260, 1), (156, 244, 1),
          (92, 132, 1), (140, 274, 1), (46, 196, 2), (160, 190, 1))


def slot_centers():
    """Centros de los cinco huecos de la tapa del púlpito, de izquierda a derecha."""
    y = PULPIT_TOP + 16
    return [(PULPIT_X + (i - 2) * SLOT_GAP, y) for i in range(len(GEM_ORDER))]


def ending_background() -> pygame.Surface:
    """Muro y suelo de piedra, la ventana con la luna y la cárcel vacía (sin el gusano)."""
    surf = opaque_surface((S.LOGICAL_W, S.LOGICAL_H))   # opaca: ver display.opaque_surface
    surf.fill(S.DUNGEON_WALL)
    _draw_wall(surf)
    _draw_window(surf)
    _draw_floor(surf)
    _draw_chains(surf)
    for x in TORCHES:
        _draw_torch_holder(surf, x, TORCH_Y)
    _draw_pulpit(surf)
    return surf


def _draw_wall(surf):
    """Sillares del muro en hileras alternas, con algún bloque más oscuro."""
    row_h, block_w = 26, 48
    for i, y in enumerate(range(0, FLOOR_Y, row_h)):
        offset = 0 if i % 2 else block_w // 2
        for j, x in enumerate(range(-offset, S.LOGICAL_W, block_w)):
            if (i * 7 + j * 3) % 5 == 0:
                pygame.draw.rect(surf, S.DUNGEON_WALL_DARK, (x + 2, y + 2, block_w - 4, row_h - 4))
            pygame.draw.rect(surf, S.DUNGEON_WALL_DARK, (x, y, block_w, row_h), 2)


def _draw_window(surf):
    """Ventana con arco: cielo nocturno con estrellas y la luna, marco de piedra y barrotes."""
    w = WINDOW
    arch = w.width // 2
    sky = transparent_layer(w.size)
    pygame.draw.rect(sky, S.NIGHT_SKY, (0, arch, w.width, w.height - arch))
    pygame.draw.circle(sky, S.NIGHT_SKY, (arch, arch), arch)
    surf.blit(sky, w.topleft)
    for x, y, r in _STARS:
        pygame.draw.circle(surf, S.WHITE, (x, y), r)
    # Luna llena con halo y cráteres
    mx, my = MOON_POS
    glow = transparent_layer((MOON_R * 4, MOON_R * 4))
    for r, a in ((MOON_R * 1.9, 30), (MOON_R * 1.45, 55)):
        pygame.draw.circle(glow, (*S.MOON, a), (MOON_R * 2, MOON_R * 2), r)
    surf.blit(glow, (mx - MOON_R * 2, my - MOON_R * 2))
    pygame.draw.circle(surf, S.MOON, MOON_POS, MOON_R)
    for dx, dy, r in ((-9, -8, 7), (10, 6, 5), (-4, 13, 4), (12, -12, 3)):
        pygame.draw.circle(surf, S.MOON_SHADE, (mx + dx, my + dy), r)
    # Marco de piedra (con dovelas en el arco) y alféizar
    pygame.draw.circle(surf, S.STONE, (w.x + arch, w.y + arch), arch + 8, 8,
                       draw_top_left=True, draw_top_right=True)
    pygame.draw.rect(surf, S.STONE, (w.x - 8, w.y + arch, 8, w.height - arch))
    pygame.draw.rect(surf, S.STONE, (w.right, w.y + arch, 8, w.height - arch))
    for k in range(1, 6):
        a = math.pi * k / 6
        cx, cy = w.x + arch, w.y + arch
        pygame.draw.line(surf, S.STONE_DARK, (cx + math.cos(a) * arch, cy - math.sin(a) * arch),
                         (cx + math.cos(a) * (arch + 8), cy - math.sin(a) * (arch + 8)), 2)
    pygame.draw.rect(surf, S.STONE, (w.x - 14, w.bottom, w.width + 28, 10))
    pygame.draw.rect(surf, S.STONE_DARK, (w.x - 14, w.bottom + 8, w.width + 28, 3))
    # Barrotes
    for x in range(w.x + 22, w.right - 10, 30):
        top = w.y + arch - math.sqrt(max(0, arch ** 2 - (x - w.x - arch) ** 2))
        pygame.draw.line(surf, S.IRON, (x, top), (x, w.bottom), 4)
    pygame.draw.line(surf, S.IRON, (w.x, w.y + 110), (w.right, w.y + 110), 4)


def _draw_floor(surf):
    pygame.draw.rect(surf, S.DUNGEON_FLOOR, (0, FLOOR_Y, S.LOGICAL_W, S.LOGICAL_H - FLOOR_Y))
    pygame.draw.rect(surf, S.DUNGEON_FLOOR_DARK, (0, FLOOR_Y, S.LOGICAL_W, 5))
    for i, y in enumerate(range(FLOOR_Y + 5, S.LOGICAL_H, 42)):   # losas
        pygame.draw.line(surf, S.DUNGEON_FLOOR_DARK, (0, y), (S.LOGICAL_W, y), 2)
        off = 0 if i % 2 else 40
        for x in range(off, S.LOGICAL_W, 80):
            pygame.draw.line(surf, S.DUNGEON_FLOOR_DARK, (x, y), (x, y + 42), 2)


def _draw_chains(surf):
    """Grilletes colgando del muro, a la izquierda."""
    for x in (20, 210):
        for i in range(6):
            y = 330 + i * 12
            pygame.draw.ellipse(surf, S.IRON, (x - 4, y, 8, 14), 2)
        pygame.draw.circle(surf, S.IRON, (x, 330 + 6 * 12 + 6), 7, 3)
        pygame.draw.circle(surf, S.IRON_LIGHT, (x, 328), 3)


def _draw_torch_holder(surf, x, y):
    pygame.draw.polygon(surf, S.KNIFE_HANDLE, [(x - 6, y), (x + 6, y), (x + 3, y + 34),
                                                (x - 3, y + 34)])
    pygame.draw.rect(surf, S.IRON, (x - 9, y + 10, 18, 5))
    pygame.draw.rect(surf, S.IRON, (x - 3, y + 15, 6, 16))


def draw_torches(surf, t):
    """Llamas de las antorchas, que tiemblan, con su halo de luz."""
    for i, x in enumerate(TORCHES):
        flick = math.sin(t * 13 + i * 2.1) * 0.5 + math.sin(t * 7.3 + i) * 0.5
        glow = transparent_layer((140, 140))
        pygame.draw.circle(glow, (*S.TORCH_FLAME, 26), (70, 70), 62 + flick * 4)
        pygame.draw.circle(glow, (*S.TORCH_FLAME, 40), (70, 70), 36 + flick * 3)
        surf.blit(glow, (x - 70, TORCH_Y - 82))
        h = 26 + flick * 4
        base = TORCH_Y + 2
        outer = [(x - 9, base), (x - 6, base - h * 0.5), (x + flick * 3, base - h),
                 (x + 6, base - h * 0.5), (x + 9, base)]
        pygame.draw.polygon(surf, S.TORCH_FLAME, outer)
        inner = [(x - 4, base), (x + flick * 2, base - h * 0.6), (x + 4, base)]
        pygame.draw.polygon(surf, S.GOLD_SHINE, inner)


def _draw_pulpit(surf):
    """Púlpito de piedra: base, columna y una tapa inclinada con los cinco huecos."""
    x, top = PULPIT_X, PULPIT_TOP
    pygame.draw.rect(surf, S.PULPIT_DARK, (x - 52, FLOOR_Y - 16, 104, 16), border_radius=3)
    pygame.draw.rect(surf, S.PULPIT, (x - 44, FLOOR_Y - 26, 88, 12), border_radius=3)
    pygame.draw.rect(surf, S.PULPIT, (x - 26, top + 36, 52, FLOOR_Y - 26 - top - 36))
    pygame.draw.rect(surf, S.PULPIT_DARK, (x + 12, top + 36, 14, FLOOR_Y - 26 - top - 36))
    for y in range(top + 52, FLOOR_Y - 30, 22):                       # estrías
        pygame.draw.line(surf, S.PULPIT_DARK, (x - 26, y), (x + 26, y), 2)
    lid = [(x - 76, top + 4), (x + 76, top + 4), (x + 84, top + 36), (x - 84, top + 36)]
    pygame.draw.polygon(surf, S.PULPIT, lid)
    pygame.draw.polygon(surf, S.PULPIT_LIGHT, [(x - 76, top + 4), (x + 76, top + 4),
                                               (x + 77, top + 8), (x - 77, top + 8)])
    pygame.draw.polygon(surf, S.PULPIT_DARK, lid, 2)
    pygame.draw.rect(surf, S.PULPIT_DARK, (x - 84, top + 36, 168, 6))
    for c in slot_centers():                                            # huecos
        pts, _ = gem_points(c, SLOT_SIZE + 4)
        pygame.draw.polygon(surf, S.DUNGEON_WALL_DARK, pts)
        pygame.draw.polygon(surf, S.PULPIT_LIGHT, pts, 1)


def draw_slot_glow(surf, center, k):
    """Brillo de un hueco al encajar su gema (``k``: 1 al encajar, se apaga hasta 0)."""
    if k <= 0:
        return
    layer = transparent_layer((60, 60))
    pygame.draw.circle(layer, (255, 255, 230, round(110 * k)), (30, 30), 12 + 16 * (1 - k))
    surf.blit(layer, (center[0] - 30, center[1] - 30))


def draw_pulpit_light(surf, t, k):
    """Columna de luz sobre el púlpito cuando ya están las cinco gemas (``k``: 0..1)."""
    if k <= 0:
        return
    layer = transparent_layer((S.LOGICAL_W, FLOOR_Y))
    x, top = PULPIT_X, PULPIT_TOP
    a = round((70 + 20 * math.sin(t * 4)) * k)
    pygame.draw.polygon(layer, (255, 250, 210, a), [(x - 70, top + 4), (x + 70, top + 4),
                                                    (x + 30, 0), (x - 30, 0)])
    surf.blit(layer, (0, 0))


def draw_cage_bars(surf, open_k=0.0, lock_k=0.0):
    """Barrotes y cerradura de la cárcel (por delante del gusano).

    ``lock_k`` (0..1): el candado se abre y cae al suelo. ``open_k`` (0..1): la reja sube
    como un rastrillo y se esconde tras el travesaño de arriba."""
    c = CAGE
    off = round(open_k * (c.height - 8))
    clip = surf.get_clip()
    surf.set_clip(pygame.Rect(0, c.y - 10, S.LOGICAL_W, c.height + 10))
    for x in range(c.x + 19, c.right - 18, 19):                 # reja (sube al abrirse)
        pygame.draw.line(surf, S.IRON, (x, c.y - off), (x, c.bottom - 8 - off), 5)
        pygame.draw.line(surf, S.IRON_LIGHT, (x - 1, c.y - off), (x - 1, c.bottom - 8 - off), 1)
    pygame.draw.line(surf, S.IRON, (c.x, c.y + 70 - off), (c.right, c.y + 70 - off), 4)
    surf.set_clip(clip)
    for x in (c.x, c.right):                                    # postes fijos de los lados
        pygame.draw.line(surf, S.IRON, (x, c.y), (x, c.bottom), 7)
        pygame.draw.line(surf, S.IRON_LIGHT, (x - 2, c.y), (x - 2, c.bottom), 1)
    pygame.draw.rect(surf, S.IRON, (c.x - 4, c.y - 10, c.width + 8, 12), border_radius=3)
    pygame.draw.rect(surf, S.IRON_LIGHT, (c.x - 4, c.y - 10, c.width + 8, 3))
    pygame.draw.rect(surf, S.IRON, (c.x - 4, c.bottom - 8, c.width + 8, 8))
    if lock_k < 1:                     # cerrado o cayendo: delante de la reja
        draw_lock(surf, lock_k)


def draw_lock(surf, k):
    """Candado: con ``k`` > 0 se le abre el arco y cae hasta el suelo. Ya en el suelo
    (``k`` = 1) se dibuja aparte, detrás de los personajes."""
    c = CAGE
    lock = pygame.Rect(0, 0, 18, 20)
    fall = max(0.0, (k - 0.3) / 0.7)
    top0, top1 = c.y + 80, FLOOR_Y - 20
    lock.midtop = (c.x + 2 - 10 * fall, round(top0 + (top1 - top0) * fall * fall))
    shackle_up = 5 if k > 0 else 0                     # el arco salta al abrirse
    pygame.draw.circle(surf, S.GOLD_DARK, (lock.centerx + (3 if k > 0 else 0),
                                           lock.y + 1 - shackle_up), 7, 3)
    pygame.draw.rect(surf, S.GOLD, lock, border_radius=3)
    pygame.draw.circle(surf, S.BLACK, (lock.centerx, lock.centery - 1), 3)
    pygame.draw.line(surf, S.BLACK, (lock.centerx, lock.centery), (lock.centerx, lock.bottom - 4), 2)


def draw_flying_gem(surf, start, end, k, kind):
    """Gema volando en arco de ``start`` a ``end`` (``k``: 0..1), girando un poco."""
    x = start[0] + (end[0] - start[0]) * k
    y = start[1] + (end[1] - start[1]) * k - math.sin(math.pi * k) * 70
    draw_gem(surf, (x, y), SLOT_SIZE + 2 * math.sin(math.pi * k), kind, sparkle=1 - k)
