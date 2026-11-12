"""Dibujo del jefe final: un muñeco enorme hecho de anillos hinchados ("michelines").

Todo se dibuja con primitivas a partir del estado del jefe (``entities.Boss``), así que las
animaciones salen solas de sus valores:

- ``crouch_k``: agacharse / aplastarse (piernas y torso se comprimen, se abre de piernas).
- ``arm_ext`` + ``side``: manotazo barriendo el suelo hacia la izquierda, la derecha o ambos
  lados; durante ``crouch`` el brazo coge impulso hacia atrás y arriba.
- ``stretch_k`` / ``state == "air"``: salto vertical (se estira y levanta los brazos).
- ``state == "land"``: aterrizaje con polvo y onda en el suelo.
- ``walk_dist``: piernas que se levantan al andar y brazos que se balancean.
- ``hurt_t``: parpadeo rojo al recibir un golpe. ``dying``: tiembla, parpadea y se deshincha.
"""

import math

import pygame

from . import effects
from . import settings as S

PAD_X = S.BOSS_REACH + 40          # margen de la capa para las manos estiradas
PAD_TOP = 50                       # margen para los brazos levantados


def _ring(surf, cx, cy, w, h, white=S.BOSS_WHITE):
    """Un anillo hinchado: contorno, cuerpo blanco, sombra abajo y brillo arriba."""
    w, h = max(4, round(w)), max(3, round(h))
    box = pygame.Rect(0, 0, w, h)
    box.center = (round(cx), round(cy))
    pygame.draw.ellipse(surf, S.BOSS_EDGE, box.inflate(2, 2))
    pygame.draw.ellipse(surf, S.BOSS_SHADE, box)
    top = box.inflate(-max(2, w // 10), -max(2, h // 3))
    top.y = box.y + 1
    pygame.draw.ellipse(surf, white, top)
    if w > 14:                                           # brillo
        hl = pygame.Rect(0, 0, w * 0.35, max(2, h * 0.22))
        hl.center = (box.centerx - w * 0.18, box.y + h * 0.3)
        pygame.draw.ellipse(surf, (255, 255, 255), hl)


def _lerp(a, b, k):
    return a + (b - a) * k


def _bezier(p0, p1, p2, k):
    return tuple((1 - k) ** 2 * a + 2 * (1 - k) * k * b + k * k * c
                 for a, b, c in zip(p0, p1, p2))


def _arm(surf, shoulder, hand, side, sweeping=False):
    """Brazo de anillos del hombro a la mano, con un codo que cae un poco, y manopla."""
    sx, sy = shoulder
    hx, hy = hand
    elbow = ((sx + hx) / 2 + side * 4, (sy + hy) / 2 + 8)
    pts = []
    for k in (0.2, 0.45, 0.7):                           # anillos a lo largo del brazo
        if k < 0.5:
            q = k / 0.5
            pts.append((_lerp(sx, elbow[0], q), _lerp(sy, elbow[1], q)))
        else:
            q = (k - 0.5) / 0.5
            pts.append((_lerp(elbow[0], hx, q), _lerp(elbow[1], hy, q)))
    for i, (x, y) in enumerate(pts):
        size = 20 - i * 2
        _ring(surf, x, y, size, size * 0.85)
    # Manopla con pulgar (el pulgar apunta hacia arriba / hacia delante)
    _ring(surf, hx + side * 6, hy - 6, 10, 9)
    _ring(surf, hx, hy, 22, 20)
    if sweeping:                                         # trazos de velocidad detrás
        for i in range(3):
            y = hy - 6 + i * 6
            x0 = hx - side * (16 + i * 4)
            pygame.draw.line(surf, (235, 238, 255), (x0, y), (x0 - side * (18 - i * 4), y), 2)


def _face(surf, cx, cy, w, facing, angry, crouch):
    """Cara: ojos que miran al jugador, cejas de enfado y boca que enseña los dientes."""
    look = facing * 3
    eye_y = cy - 3
    for dx in (-9, 9):
        ex = cx + dx + look
        pygame.draw.ellipse(surf, (255, 255, 255), (ex - 6, eye_y - 7, 12, 14))
        pygame.draw.ellipse(surf, S.BOSS_EDGE, (ex - 6, eye_y - 7, 12, 14), 1)
        pupil = (210, 20, 30) if angry else (20, 20, 30)
        pygame.draw.circle(surf, pupil, (ex + facing * 2, eye_y + 1), 3)
        # Ceja inclinada hacia el centro (enfadado); más baja al agacharse
        inner = cx + look + (3 if dx > 0 else -3)
        outer = cx + dx + look + (7 if dx > 0 else -7)
        brow_y = eye_y - 10 + crouch * 2
        pygame.draw.line(surf, S.BOSS_EDGE, (outer, brow_y - 3), (inner, brow_y + 2), 3)
    mouth = pygame.Rect(0, 0, 22, 9)
    mouth.center = (cx + look, cy + 9)
    pygame.draw.rect(surf, (90, 20, 35), mouth, border_radius=4)
    for i in range(1, 4):                                # dientes
        x = mouth.x + i * mouth.width // 4
        pygame.draw.line(surf, (255, 255, 255), (x, mouth.y + 1), (x, mouth.y + 3), 2)
    pygame.draw.rect(surf, S.BOSS_EDGE, mouth, 1, border_radius=4)


def draw_boss(surf, boss, t):
    """Dibuja el jefe en ``surf`` (coordenadas del mundo). ``t``: tiempo de la escena."""
    r = boss.rect
    W = r.width
    layer = pygame.Surface((W + 2 * PAD_X, r.height + PAD_TOP + 8), pygame.SRCALPHA)
    layer.fill((0, 0, 0, 0))
    bx = PAD_X + W / 2                                   # centro de los pies en la capa
    by = PAD_TOP + r.height                              # suelo bajo sus pies

    c = boss.crouch_k
    s = boss.stretch_k
    air = boss.state in ("air",)
    walking = boss.state == "walk" and abs(boss.vx) > 1
    phase = boss.walk_dist * 0.12

    # --- piernas (3 anillos cada una) ---
    leg_h = 27 * (1 - 0.45 * c) * (1 + 0.25 * s)
    spread = 17 + 6 * c
    hip_y = by - leg_h
    for side in (-1, 1):
        lift = max(0.0, math.sin(phase) * side) * 6 if walking else 0.0
        if air:
            lift = 4 * s
        lx = bx + side * spread
        foot_y = by - 6 - lift
        _ring(layer, lx + side * 3, foot_y, 32, 12)             # zapato
        for i in (1, 2):
            y = _lerp(foot_y, hip_y, i / 2.6)
            _ring(layer, lx, y, 26 - i, 12)

    # --- torso (anillos de abajo arriba; cada uno pisa al de debajo) ---
    widths = (60, 70, 76, 72, 64)
    gap = 8.2 * (1 - 0.25 * c) * (1 + 0.15 * s)
    breath = math.sin(t * 3) * 1.0 if boss.state == "walk" else 0.0
    ys = [hip_y - 4 - i * gap for i in range(len(widths))]
    shoulder_y = ys[-1] + 3
    torso_top = ys[-1] - 5

    # Brazos: posición de cada mano según el estado
    sides = boss.slap_sides()
    hands = {}
    sweeping = set()
    for side in (-1, 1):
        shoulder = (bx + side * 32, shoulder_y)
        rest = (bx + side * 44, shoulder_y + 24 + (math.sin(phase + side) * 3 if walking else 0))
        hand = rest
        if boss.state in ("air", "prep") or (boss.state == "land" and boss.state_t < 0.12):
            up = (bx + side * 40, shoulder_y - 30)
            k = s if air else min(1.0, boss.state_t / S.BOSS_JUMP_PREP) * 0.4
            hand = (_lerp(rest[0], up[0], max(k, 0.6 if air else k)),
                    _lerp(rest[1], up[1], max(k, 0.6 if air else k)))
        if side in sides and boss.state in ("crouch", "slap", "rise"):
            windup = (bx + side * 26, shoulder_y - 26)          # coge impulso: atrás y arriba
            far = (bx + side * (W / 2 - 8 + S.BOSS_REACH), by - 12)
            if boss.state == "crouch":
                k = min(1.0, boss.state_t / S.BOSS_CROUCH_TIME)
                hand = (_lerp(rest[0], windup[0], k), _lerp(rest[1], windup[1], k))
            elif boss.state == "slap":
                e = boss.arm_ext
                ctrl = (bx + side * (W / 2 + 30), shoulder_y + 6)
                out = boss.state_t < S.BOSS_SLAP_OUT
                hand = _bezier(windup, ctrl, far, e) if out else (
                    _lerp(rest[0], far[0], e), _lerp(rest[1], far[1], e))
                if out and 0.15 < e < 0.95:
                    sweeping.add(side)
            else:                                               # rise: vuelve a su sitio
                hand = rest
        hands[side] = (shoulder, hand)

    # Brazo de detrás (el contrario a donde mira) antes del cuerpo
    back = -boss.facing
    _arm(layer, *hands[back], back, back in sweeping)
    for i, (w, y) in enumerate(zip(widths, ys)):
        _ring(layer, bx, y + (breath if i == len(widths) - 1 else 0), w * (1 + 0.06 * c), 13)
    # --- cuello y cabeza ---
    neck_y = torso_top - 2
    _ring(layer, bx, neck_y, 36, 9)
    head_cy = neck_y - 14 + c * 2
    head = pygame.Rect(0, 0, 42, 31)
    head.center = (round(bx), round(head_cy))
    pygame.draw.ellipse(layer, S.BOSS_EDGE, head.inflate(2, 2))
    pygame.draw.ellipse(layer, S.BOSS_WHITE, head)
    shade = head.inflate(-6, -18)
    shade.bottom = head.bottom - 1
    pygame.draw.ellipse(layer, S.BOSS_SHADE, shade, 2)
    pygame.draw.ellipse(layer, (255, 255, 255),
                        (head.x + 8, head.y + 4, 12, 6))       # brillo
    _face(layer, bx, head_cy, head.width, boss.facing, boss.angry, c)
    # Brazo de delante, por encima del cuerpo
    _arm(layer, *hands[boss.facing], boss.facing, boss.facing in sweeping)

    # --- golpe / derrota ---
    flash = boss.hurt_t > 0 or (boss.dying and int(t * 14) % 2 == 0)
    if flash:
        layer.fill((255, 140, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
    dx = 0
    if boss.dying:
        k = min(1.0, boss.state_t / S.BOSS_DEATH_TIME)
        dx = round(math.sin(t * 60) * 3 * (0.4 + k))
        squash = 1 - 0.35 * k                                    # se deshincha
        lw, lh = layer.get_size()
        new_h = max(1, round(lh * squash))
        layer = pygame.transform.smoothscale(layer, (round(lw * (1 + 0.12 * k)), new_h))
        top = r.bottom + 8 - new_h
        surf.blit(layer, (r.centerx - layer.get_width() / 2 + dx, top))
        for i in range(3):                                       # humillo
            ang = t * 2 + i * 2.1
            effects.blob(surf, (150, 150, 160), 90 * k, (r.centerx + math.cos(ang) * 30,
                                                          r.top + 20 - k * 20 * i), 14 + 8 * k)
    else:
        surf.blit(layer, (r.centerx - bx + dx, r.bottom - by))

    if boss.state == "land":                                     # polvo y onda en el suelo
        k = min(1.0, boss.state_t / S.BOSS_LAND_TIME)
        for side in (-1, 1):
            for i in range(3):
                x = r.centerx + side * (30 + 50 * k + i * 14)
                effects.blob(surf, (175, 165, 150), 150 * (1 - k), (x, r.bottom - 6 - i * 3),
                             9 + 6 * k)
        wave = pygame.Rect(0, 0, 2 * S.BOSS_SHOCK_RANGE * (0.3 + 0.7 * k), 14)
        wave.center = (r.centerx, r.bottom)
        ring = pygame.Surface(wave.size, pygame.SRCALPHA)
        ring.fill((0, 0, 0, 0))
        pygame.draw.ellipse(ring, (255, 240, 210, round(170 * (1 - k))), ring.get_rect(), 2)
        surf.blit(ring, wave)


def draw_boss_bar(surf, boss, font, label, y):
    """Barra de vida del jefe (centrada, bajo el marcador)."""
    w, h = 220, 10
    x = (surf.get_width() - w) // 2
    text = font.render(label, True, S.WHITE)
    surf.blit(text, (x - text.get_width() - 8, y + h // 2 - text.get_height() // 2))
    pygame.draw.rect(surf, (20, 20, 36), (x - 2, y - 2, w + 4, h + 4), border_radius=4)
    k = boss.hp / boss.max_hp if boss.max_hp else 0
    fill = (255, 255, 255) if boss.hurt_t > 0 else (S.ENEMY_ANGRY if boss.angry else S.HEART)
    if k > 0:
        pygame.draw.rect(surf, fill, (x, y, round(w * k), h), border_radius=3)
    pygame.draw.rect(surf, S.WHITE, (x - 2, y - 2, w + 4, h + 4), 1, border_radius=4)
