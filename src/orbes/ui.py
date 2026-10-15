"""Utilidades de interfaz mínimas."""

import pygame

from . import settings as S


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
