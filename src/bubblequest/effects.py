"""Efectos de partículas suaves: la explosión de la bomba y su humo.

En lugar de polígonos y círculos de borde duro se usan "manchas" con el borde difuminado
(un degradado radial precalculado que se escala y se tiñe) y brillos que se suman a lo que
hay debajo (mezcla aditiva), lo que da un aspecto de fuego más realista.

Todo es determinista para cada explosión (``seed``): la misma explosión se dibuja igual en
cada fotograma, sin parpadeos, y dos explosiones distintas no son idénticas.
"""

import math

import pygame

from . import settings as S

_BASE = 128                 # tamaño del degradado de referencia (se escala a lo necesario)
_STEP = 6                   # los diámetros se redondean a múltiplos de esto (para la caché)
_CACHE_MAX = 160

_soft_base = None
_glow_base = None
_cache: dict = {}


def _radial(alpha_profile, glow):
    """Degradado radial de _BASE px. ``glow``: RGB opaco (negro fuera) para sumar; si no,
    blanco con transparencia por píxel."""
    if glow:
        img = pygame.Surface((_BASE, _BASE))
        img.fill((0, 0, 0))
    else:
        img = pygame.Surface((_BASE, _BASE), pygame.SRCALPHA)
        img.fill((255, 255, 255, 0))
    c = _BASE // 2
    for r in range(c, 0, -1):            # de fuera hacia dentro: cada círculo pisa al anterior
        a = round(255 * alpha_profile(r / c))
        color = (a, a, a) if glow else (255, 255, 255, a)
        pygame.draw.circle(img, color, (c, c), r)
    return img


def _soft_profile(d):
    """Mancha: casi opaca en el centro, borde que se difumina."""
    if d <= 0.45:
        return 1.0
    t = (d - 0.45) / 0.55
    return (1 - t * t * (3 - 2 * t)) ** 1.3


def _glow_profile(d):
    """Brillo: caída suave tipo gaussiana."""
    return math.exp(-4.0 * d * d) * (1 - d) ** 0.5


def _sprite(kind, diameter):
    global _soft_base, _glow_base
    d = max(_STEP, int(round(diameter / _STEP)) * _STEP)
    key = (kind, d)
    img = _cache.get(key)
    if img is None:
        if kind == "glow":
            if _glow_base is None:
                _glow_base = _radial(_glow_profile, glow=True)
            base = _glow_base
        else:
            if _soft_base is None:
                _soft_base = _radial(_soft_profile, glow=False)
            base = _soft_base
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        img = _cache[key] = pygame.transform.smoothscale(base, (d, d))
    return img


def blob(surf, color, alpha, center, radius):
    """Mancha de borde difuminado (mezcla normal)."""
    if radius < 1 or alpha < 2:
        return
    img = _sprite("soft", radius * 2).copy()
    img.fill((*color, max(0, min(255, round(alpha)))), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))))


def glow(surf, color, intensity, center, radius):
    """Brillo que se suma a lo de debajo (aclara, nunca oscurece)."""
    intensity = max(0.0, min(1.0, intensity))
    if radius < 1 or intensity <= 0.01:
        return
    img = _sprite("glow", radius * 2).copy()
    img.fill(tuple(round(ch * intensity) for ch in color), special_flags=pygame.BLEND_RGB_MULT)
    surf.blit(img, img.get_rect(center=(round(center[0]), round(center[1]))),
              special_flags=pygame.BLEND_RGB_ADD)


def _hash(i, seed):
    """Número pseudoaleatorio fijo en [0, 1) para la partícula ``i`` de la explosión."""
    v = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
    return v - math.floor(v)


# Color del fuego según su "temperatura": blanco -> amarillo -> naranja -> rojo -> hollín
_FIRE_RAMP = ((0.00, (55, 42, 38)),
              (0.22, (140, 38, 18)),
              (0.45, (228, 92, 22)),
              (0.70, (255, 180, 55)),
              (0.88, (255, 232, 140)),
              (1.00, (255, 252, 235)))


def fire_color(temp):
    temp = max(0.0, min(1.0, temp))
    for (t0, c0), (t1, c1) in zip(_FIRE_RAMP, _FIRE_RAMP[1:]):
        if temp <= t1:
            k = (temp - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
    return _FIRE_RAMP[-1][1]


def seed_for(x, y):
    """Semilla de una explosión a partir de su posición (no cambia mientras dura)."""
    return (round(x) * 73856093 ^ round(y) * 19349663) % 1000 / 10.0


def draw_explosion(surf, x, y, age, seed=0.0):
    """Fogonazo, bola de fuego que se enfría, onda expansiva, chispas y cascotes."""
    life = S.EXPLOSION_TIME
    k = age / life
    if k >= 1:
        return
    R = S.BOMB_RADIUS
    grow = 1 - (1 - min(1.0, k / 0.3)) ** 3              # crece muy rápido y frena
    fade_out = min(1.0, (1 - k) / 0.35)                  # se apaga en el último tercio

    # Onda expansiva: anillo fino y difuso que llega hasta el alcance de la bomba
    if k < 0.45:
        q = k / 0.45
        ring_r = R * (0.25 + 0.85 * (1 - (1 - q) ** 2))
        size = round(ring_r * 2 + 16)
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        layer.fill((0, 0, 0, 0))
        c = size // 2
        base_a = 110 * (1 - q) ** 1.5
        for w, a in ((9, 0.25), (5, 0.5), (2, 1.0)):     # de ancho y tenue a fino y claro
            pygame.draw.circle(layer, (255, 236, 205, round(base_a * a)), (c, c),
                               round(ring_r), w)
        surf.blit(layer, (x - c, y - c))

    # Bola de fuego: bocanadas que salen del centro, se hinchan, suben y se enfrían.
    puffs = []
    for i in range(18):
        h1, h2, h3, h4 = (_hash(i * 4 + j, seed) for j in range(4))
        ang = i * 2.39996 + h1 * 0.8
        reach = 0.12 + 0.58 * h2                          # cuánto se aleja del centro
        dist = R * reach * grow * (1 + 0.15 * k)
        px = x + math.cos(ang) * dist
        py = y + math.sin(ang) * dist * 0.85 - R * 0.22 * k * k   # el aire caliente sube
        radius = R * (0.2 + 0.16 * h3) * (0.35 + 0.65 * grow) * (1 + 0.35 * k)
        temp = 1.15 - 1.55 * k - 0.55 * reach + 0.15 * h4
        puffs.append((temp, px, py, radius))
    puffs.sort()                                          # las frías detrás, las calientes delante
    for temp, px, py, radius in puffs:
        alpha = 235 * fade_out * (0.55 + 0.45 * max(0.0, min(1.0, temp + 0.4)))
        blob(surf, fire_color(temp), alpha, (px, py), radius)

    # Núcleo incandescente y fogonazo inicial (brillo aditivo)
    core_t = max(0.0, 1.0 - 1.3 * k)
    glow(surf, fire_color(0.55 + 0.45 * core_t), 0.9 * core_t ** 1.2, (x, y - R * 0.1 * k),
         R * (0.35 + 0.45 * grow))
    if k < 0.3:
        flash = (1 - k / 0.3) ** 1.6
        glow(surf, (255, 245, 220), flash, (x, y), R * (0.9 + 0.6 * grow))

    # Chispas: salen disparadas, caen por la gravedad y dejan una estela que se enfría
    for i in range(22):
        h1, h2, h3 = (_hash(100 + i * 3 + j, seed) for j in range(3))
        spark_life = life * (0.45 + 0.5 * h3)
        if age >= spark_life:
            continue
        ang = i * 2 * math.pi / 22 + h1 * 0.4
        speed = R * (1.6 + 1.4 * h2)

        def pos(tt):
            drag = (1 - math.exp(-3.5 * tt)) / 3.5        # frenan con el aire
            return (x + math.cos(ang) * speed * drag,
                    y + math.sin(ang) * speed * drag + 260 * tt * tt)

        sk = age / spark_life
        head, tail = pos(age), pos(max(0.0, age - 0.045))
        color = fire_color(1.0 - 0.75 * sk)
        pygame.draw.line(surf, color, tail, head, 2 if sk < 0.5 else 1)
        if sk < 0.6:
            glow(surf, color, 0.5 * (1 - sk), head, 6)

    # Cascotes: trozos oscuros irregulares que giran y caen
    for i in range(8):
        h1, h2, h3 = (_hash(200 + i * 3 + j, seed) for j in range(3))
        ang = -math.pi / 2 + (h1 - 0.5) * math.pi * 1.6  # sobre todo hacia arriba
        speed = R * (1.2 + 1.0 * h2)
        tt = age
        if k < 0.12:                                       # aún dentro del fogonazo
            continue
        start = R * 0.3                                    # salen del borde de la bola de fuego
        cx = x + math.cos(ang) * (start + speed * tt)
        cy = y + math.sin(ang) * (start + speed * tt) + 520 * tt * tt
        size = (2.5 + 2.5 * h3) * min(1.0, (1 - k) / 0.25)   # se encogen al final
        rot = tt * (8 + 10 * h3) * (1 if i % 2 else -1)
        pts = [(cx + math.cos(rot + a) * size * (0.7 + 0.3 * _hash(300 + i * 5 + n, seed)),
                cy + math.sin(rot + a) * size * (0.7 + 0.3 * _hash(300 + i * 5 + n, seed)))
               for n, a in enumerate((0.0, 1.4, 2.6, 3.9, 5.1))]
        pygame.draw.polygon(surf, (38, 32, 30), pts)
        if k < 0.5:                                        # aún al rojo por un lado
            pygame.draw.line(surf, fire_color(0.4 - 0.6 * k), pts[0], pts[1], 1)


def draw_smoke(surf, x, y, age, seed=0.0):
    """Humo: bocanadas grises difuminadas que salen mientras el fuego se apaga, se hinchan,
    suben despacio y se desvanecen."""
    start = S.EXPLOSION_TIME * 0.35
    if age < start:
        return
    k = (age - start) / (S.SMOKE_TIME - start)           # 0 -> 1 durante la vida del humo
    if k >= 1:
        return
    R = S.BOMB_RADIUS
    ease = 1 - (1 - k) ** 2                               # sale rápido y frena
    for i in range(S.SMOKE_PUFFS + 5):
        h1, h2, h3, h4 = (_hash(400 + i * 4 + j, seed) for j in range(4))
        ang = i * 2.39996 + h1
        spread = R * (0.15 + 0.4 * h2)
        px = x + math.cos(ang) * spread * (0.45 + 0.55 * ease) + 10 * math.sin(k * 3 + i)
        py = (y + math.sin(ang) * spread * 0.55 * (0.45 + 0.55 * ease)
              - R * (0.3 + 0.2 * h3) * k)                 # sube
        radius = R * (0.14 + 0.1 * h4) * (1 + 1.1 * ease)
        alpha = 150 * min(1.0, k / 0.15) * (1 - k) ** 1.5
        gray = round(70 + 45 * h3 + 25 * k)               # se aclara al disiparse
        blob(surf, (gray, gray, gray + 6), alpha, (px, py), radius)
