"""Utilidades de interfaz mínimas."""

import pygame

from . import settings as S
from .flags import flag_surface


def draw_text(surf, font, text, color, center=None, topleft=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    if topleft is not None:
        rect.topleft = topleft
    surf.blit(img, rect)
    return rect


class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def hit(self, pos) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, surf, font):
        pygame.draw.rect(surf, S.BUTTON, self.rect, border_radius=14)
        pygame.draw.rect(surf, S.PLATFORM, self.rect, width=2, border_radius=14)
        draw_text(surf, font, self.label, S.WHITE, center=self.rect.center)


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
