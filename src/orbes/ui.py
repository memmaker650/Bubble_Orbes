"""Utilidades de interfaz mínimas."""

import math

import pygame

from . import settings as S
from .flags import flag_surface


def draw_text(surf, font, text, color, center=None, topleft=None, midleft=None, midright=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    if topleft is not None:
        rect.topleft = topleft
    if midleft is not None:
        rect.midleft = midleft
    if midright is not None:
        rect.midright = midright
    surf.blit(img, rect)
    return rect


_heart_cache: dict = {}


def heart_points(center, size):
    """Polígono de un corazón de `size` px de ancho centrado en `center` (curva clásica)."""
    key = size
    unit = _heart_cache.get(key)
    if unit is None:
        unit = []
        for i in range(40):
            t = 2 * math.pi * i / 40
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            unit.append((x * size / 34, (y + 2) * size / 34))
        _heart_cache[key] = unit
    cx, cy = center
    return [(cx + x, cy + y) for x, y in unit]


def draw_heart(surf, center, size, filled):
    """Corazón: `filled` = 1 (entero), 0.5 (medio: mitad izquierda) o 0 (solo el borde).
    Se aceptan también True/False."""
    fill = float(filled)
    pts = heart_points(center, size)
    if fill >= 1:
        pygame.draw.polygon(surf, S.HEART, pts)
        pygame.draw.polygon(surf, (255, 150, 160), pts, 1)   # brillo en el contorno
        return
    pygame.draw.polygon(surf, S.HEART_EMPTY, pts, 2)
    if fill > 0:
        old = surf.get_clip()
        left = pygame.Rect(center[0] - size, center[1] - size, size * fill * 2, size * 2)
        surf.set_clip(left.clip(old) if old else left)
        pygame.draw.polygon(surf, S.HEART, pts)
        surf.set_clip(old)


def draw_hearts(surf, lives, total, right, center_y, size=14, gap=4):
    """Fila de `total` corazones alineada a la derecha. `lives` puede tener medios
    (p. ej. 2.5 = dos enteros, uno a medias y el resto vacíos)."""
    total = max(total, math.ceil(lives))
    for i in range(total):
        x = right - size / 2 - (total - 1 - i) * (size + gap)
        fill = min(1.0, max(0.0, lives - i))
        draw_heart(surf, (x, center_y), size, filled=fill)


_fonts: dict = {}


def fit_font(font, text, max_width):
    """La misma fuente o una más pequeña (fuente por defecto) para que el texto quepa."""
    if font.size(text)[0] <= max_width:
        return font
    best = None
    for size in range(60, 10, -2):  # la más grande que quepa sin superar a la original
        smaller = _fonts.get(size)
        if smaller is None:
            smaller = _fonts[size] = pygame.font.Font(None, size)
        best = smaller
        if smaller.get_height() <= font.get_height() and smaller.size(text)[0] <= max_width:
            return smaller
    return best


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def hit(self, pos) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, surf, font):
        pygame.draw.rect(surf, S.BUTTON, self.rect, border_radius=14)
        pygame.draw.rect(surf, S.PLATFORM, self.rect, width=2, border_radius=14)
        draw_text(surf, fit_font(font, self.label, self.rect.width - 20), self.label, S.WHITE,
                  center=self.rect.center)


def wrap_text(font, text, max_width):
    """Parte un texto en líneas que caben en max_width píxeles."""
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if line and font.size(test)[0] > max_width:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def draw_message_box(surf, rows, center, width=300, padding=18, gap=8, accent=S.PLATFORM):
    """Ventana de mensaje centrada. rows = [(font, texto, color), ...]; los textos largos se parten."""
    lines = []
    for font, text, color in rows:
        for part in wrap_text(font, text, width - 2 * padding):
            lines.append((font, part, color))
    height = 2 * padding + sum(f.get_height() for f, _, _ in lines) + gap * (len(lines) - 1)
    box = pygame.Rect(0, 0, width, height)
    box.center = center
    pygame.draw.rect(surf, S.PANEL, box, border_radius=16)
    pygame.draw.rect(surf, accent, box, width=3, border_radius=16)
    y = box.top + padding
    for font, text, color in lines:
        h = font.get_height()
        draw_text(surf, font, text, color, center=(box.centerx, y + h // 2))
        y += h + gap
    return box


class FlagButton:
    """Botón con la bandera del idioma activo."""

    def __init__(self, rect, flag):
        self.rect = pygame.Rect(rect)
        self.flag = flag

    def hit(self, pos) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, surf):
        inner = self.rect.inflate(-8, -8)
        pygame.draw.rect(surf, S.BUTTON, self.rect, border_radius=8)
        surf.blit(flag_surface(self.flag, inner.size), inner)
        pygame.draw.rect(surf, S.PLATFORM, self.rect, width=2, border_radius=8)
