"""Dibujo de la animación de presentación (antes del nivel 1): cielo con un sol radiante,
un árbol al fondo, suelo de tierra y el gusano amigo del personaje.

Todo se dibuja con primitivas, como el resto del juego. El fondo fijo (cielo, árbol y
tierra) se dibuja una vez con ``intro_background``; el sol y el gusano se animan con ``t``.
"""

import math

import pygame

from . import settings as S
from .display import opaque_surface
from .ui import transparent_layer

GROUND_Y = 600                       # superficie de la tierra en la pantalla
SUN_POS = (300, 112)
SUN_R = 36
TREE_X = 112                         # tronco del árbol (al fondo, a la izquierda)

# Piedrecitas de la tierra: (x, y, radio)
_PEBBLES = ((22, 640, 4), (70, 700, 3), (128, 662, 5), (176, 740, 4), (232, 690, 3),
            (290, 650, 4), (340, 724, 5), (52, 774, 5), (204, 792, 3), (318, 784, 4),
            (110, 742, 2), (262, 760, 2), (360, 668, 2), (150, 620, 2))


def _lerp(a, b, k):
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def intro_background() -> pygame.Surface:
    """Cielo degradado, árbol y suelo de tierra (sin el sol, que se anima)."""
    surf = opaque_surface((S.LOGICAL_W, S.LOGICAL_H))      # opaca: ver display.opaque_surface
    for y in range(GROUND_Y):
        pygame.draw.line(surf, _lerp(S.SKY_TOP, S.SKY_BOTTOM, y / GROUND_Y),
                         (0, y), (S.LOGICAL_W, y))
    _draw_tree(surf, TREE_X, GROUND_Y)
    _draw_ground(surf)
    return surf


def _draw_tree(surf, x, ground):
    """Árbol frondoso: tronco con raíces, dos ramas y una copa de círculos."""
    trunk = [(x - 16, ground), (x - 10, ground - 70), (x - 9, ground - 150),
             (x + 9, ground - 150), (x + 10, ground - 70), (x + 16, ground)]
    pygame.draw.polygon(surf, S.TREE_TRUNK, trunk)
    for dx in (-24, 24):                                     # raíces
        pygame.draw.polygon(surf, S.TREE_TRUNK, [(x + dx * 0.3, ground - 18),
                                                 (x + dx, ground + 2), (x, ground + 2)])
    pygame.draw.line(surf, S.TREE_TRUNK, (x, ground - 120), (x - 40, ground - 170), 7)
    pygame.draw.line(surf, S.TREE_TRUNK, (x, ground - 135), (x + 36, ground - 180), 6)
    pygame.draw.line(surf, S.DIRT_DARK, (x + 4, ground - 140), (x + 6, ground - 10), 2)
    cy = ground - 205
    leaves = ((0, -30, 52), (-48, 0, 42), (48, 0, 42), (-26, 30, 40), (26, 30, 40),
              (0, 10, 46), (-62, 32, 28), (62, 32, 28))
    for dx, dy, r in leaves:                                 # sombra de la copa
        pygame.draw.circle(surf, S.TREE_LEAF_DARK, (x + dx, cy + dy + 6), r)
    for dx, dy, r in leaves:
        pygame.draw.circle(surf, S.TREE_LEAF, (x + dx, cy + dy), r - 4)
    for dx, dy, r in ((-16, -46, 18), (-56, -14, 13), (30, -18, 14)):   # brillos
        pygame.draw.circle(surf, S.TREE_LEAF_LIGHT, (x + dx, cy + dy), r)
    for dx, dy in ((-30, 10), (34, -6), (8, 38), (-4, -20)):            # manzanas
        pygame.draw.circle(surf, S.ENEMY, (x + dx, cy + dy), 5)


def _draw_ground(surf):
    pygame.draw.rect(surf, S.DIRT, (0, GROUND_Y, S.LOGICAL_W, S.LOGICAL_H - GROUND_Y))
    pygame.draw.rect(surf, S.DIRT_LIGHT, (0, GROUND_Y, S.LOGICAL_W, 8))
    for x in range(0, S.LOGICAL_W, 14):                       # borde irregular
        pygame.draw.circle(surf, S.DIRT_LIGHT, (x + 7, GROUND_Y + 6), 6)
    for i, y in enumerate(range(GROUND_Y + 40, S.LOGICAL_H, 46)):   # vetas
        off = 30 if i % 2 else 0
        for x in range(off, S.LOGICAL_W, 90):
            pygame.draw.line(surf, S.DIRT_DARK, (x, y), (x + 34, y + 3), 2)
    for x, y, r in _PEBBLES:
        pygame.draw.ellipse(surf, S.DIRT_DARK, (x - r, y - r * 0.7, 2 * r, 1.4 * r))
        pygame.draw.ellipse(surf, S.STONE, (x - r + 1, y - r * 0.7, 2 * r - 2, 1.4 * r - 2))


def draw_sun(surf, t):
    """Sol radiante: halo que late y rayos largos y cortos girando despacio."""
    cx, cy = SUN_POS
    pulse = 1 + 0.06 * math.sin(t * 3)
    glow = transparent_layer((SUN_R * 6, SUN_R * 6))
    c = SUN_R * 3
    for r, a in ((SUN_R * 2.6, 40), (SUN_R * 2.0, 60), (SUN_R * 1.5, 90)):
        pygame.draw.circle(glow, (*S.SUN, a), (c, c), r * pulse)
    surf.blit(glow, (cx - c, cy - c))
    for i in range(12):
        a = t * 0.5 + i * math.pi / 6
        long = i % 2 == 0
        r0 = SUN_R + 6
        r1 = SUN_R + (34 if long else 20) * pulse
        w = 0.11 if long else 0.08
        pts = [(cx + math.cos(a - w) * r0, cy + math.sin(a - w) * r0),
               (cx + math.cos(a) * r1, cy + math.sin(a) * r1),
               (cx + math.cos(a + w) * r0, cy + math.sin(a + w) * r0)]
        pygame.draw.polygon(surf, S.SUN, pts)
    pygame.draw.circle(surf, S.SUN, (cx, cy), SUN_R)
    pygame.draw.circle(surf, S.SUN_CORE, (cx - 6, cy - 6), SUN_R * 0.62)


def draw_hole(surf, x, ground, k=1.0):
    """Agujero en la tierra por el que sale el gusano (``k``: lo abierto, 0..1)."""
    if k <= 0:
        return
    w, h = 64 * k, 16 * k
    pygame.draw.ellipse(surf, S.DIRT_DARK, (x - w / 2, ground - h / 2 + 2, w, h))
    pygame.draw.ellipse(surf, S.BLACK, (x - w * 0.38, ground - h * 0.3 + 2, w * 0.76, h * 0.6))


def worm_points(x, ground, t, rise=1.0, height=92):
    """Centros y radios de los segmentos del gusano, de la base (bajo tierra) a la cabeza.
    ``rise`` (0..1): cuánto ha salido. El cuerpo se cimbrea con ``t``."""
    n = 9
    pts = []
    for i in range(n):
        s = i / (n - 1)
        y = ground + 18 - s * (height + 18) * rise
        sway = math.sin(t * 3.2 - s * 2.4) * 9 * s
        lean = -14 * s * s                         # la cabeza se inclina hacia el personaje
        r = 13 + 2 * s
        pts.append((x + sway + lean, y, r))
    return pts


def draw_worm(surf, x, ground, t, rise=1.0, blink=False, happy=False):
    """Gusano amigo saliendo de la tierra en ``x``, mirando a la izquierda."""
    pts = worm_points(x, ground, t, rise)
    clip = surf.get_clip()
    surf.set_clip(pygame.Rect(0, 0, S.LOGICAL_W, ground + 3))     # lo de bajo tierra no se ve
    for cx, cy, r in pts:                                         # contorno
        pygame.draw.circle(surf, S.WORM_DARK, (cx, cy), r + 2)
    for i, (cx, cy, r) in enumerate(pts):
        pygame.draw.circle(surf, S.WORM, (cx, cy), r)
        if 0 < i < len(pts) - 1:                                  # anillos del cuerpo
            pygame.draw.arc(surf, S.WORM_DARK, (cx - r, cy - r * 0.4, 2 * r, r * 1.2),
                            math.pi * 1.1, math.pi * 1.9, 2)
    for cx, cy, r in pts[1:-1]:                                   # brillo del lomo
        pygame.draw.circle(surf, S.SUN_CORE, (cx + r * 0.4, cy - r * 0.2), 2)
    surf.set_clip(clip)

    hx, hy, hr = pts[-1]
    hr += 3
    pygame.draw.circle(surf, S.WORM_DARK, (hx, hy), hr + 2)
    pygame.draw.circle(surf, S.WORM, (hx, hy), hr)
    pygame.draw.circle(surf, S.SUN_CORE, (hx + 5, hy - 8), 4)
    # Ojos mirando a la izquierda
    for ex in (hx - 9, hx + 3):
        ey = hy - 4
        if blink:
            pygame.draw.line(surf, S.BLACK, (ex - 4, ey), (ex + 4, ey), 2)
        else:
            pygame.draw.circle(surf, S.WHITE, (ex, ey), 5)
            pygame.draw.circle(surf, S.BLACK, (ex - 2, ey + 1), 2.5)
    # Mejillas y sonrisa (más grande cuando está contento)
    pygame.draw.circle(surf, S.WORM_CHEEK, (hx - 14, hy + 6), 3)
    pygame.draw.circle(surf, S.WORM_CHEEK, (hx + 8, hy + 6), 3)
    mouth = pygame.Rect(0, 0, 14 if happy else 10, 10 if happy else 6)
    mouth.center = (hx - 4, hy + 6)
    pygame.draw.arc(surf, S.BLACK, mouth, math.pi * 1.05, math.pi * 1.95, 2)
    # Hoja en la cabeza, para darle gracia
    leaf = [(hx + 2, hy - hr + 1), (hx + 14, hy - hr - 12), (hx + 6, hy - hr - 2)]
    pygame.draw.polygon(surf, S.TREE_LEAF, leaf)
    pygame.draw.line(surf, S.TREE_LEAF_DARK, leaf[0], leaf[1], 1)


def draw_heart(surf, center, size, color=(240, 70, 100)):
    """Corazón sencillo (dos círculos y un triángulo)."""
    x, y = center
    r = size * 0.3
    pygame.draw.circle(surf, color, (x - r, y - r * 0.4), r)
    pygame.draw.circle(surf, color, (x + r, y - r * 0.4), r)
    pygame.draw.polygon(surf, color, [(x - 2 * r + 0.5, y - r * 0.1), (x + 2 * r - 0.5, y - r * 0.1),
                                      (x, y + size * 0.55)])


def draw_shadow(surf, x, ground, w):
    layer = transparent_layer((w, 12))
    pygame.draw.ellipse(layer, (0, 0, 0, 70), (0, 0, w, 12))
    surf.blit(layer, (x - w / 2, ground - 5))
