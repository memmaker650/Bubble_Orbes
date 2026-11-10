"""Superficie lógica fija escalada a la ventana (con barras) y conversión de coordenadas."""

import sys

import pygame

from . import settings as S

FINGER_EVENTS = (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION)

# Formato opaco (sin canal de transparencia) para las superficies de fondo.
_OPAQUE_MASKS = (0xFF0000, 0x00FF00, 0x0000FF, 0)


def opaque_surface(size):
    """Superficie SIN canal de transparencia.

    Las superficies de fondo (la imagen lógica del juego y la del nivel) deben ser opacas:
    si heredan el formato de la ventana (que en macOS tiene canal alfa), al pegar encima
    capas semitransparentes (fantasmas, textos "+100", burbujas...) la transparencia puede
    colarse en el fondo y, al presentar el fotograma sobre la ventana borrada a negro, verse
    como cuadros negros."""
    return pygame.Surface(size, 0, 32, _OPAQUE_MASKS)


class Display:
    def __init__(self):
        if sys.platform == "ios":
            size = (0, 0)  # pantalla completa nativa
        else:
            size = (S.LOGICAL_W, S.LOGICAL_H)
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.surface = opaque_surface((S.LOGICAL_W, S.LOGICAL_H))
        self.scale = 1.0
        self.offset = (0.0, 0.0)
        self._layout()

    def _layout(self):
        ww, wh = self.window.get_size()
        self.scale = min(ww / S.LOGICAL_W, wh / S.LOGICAL_H)
        self.offset = (
            (ww - S.LOGICAL_W * self.scale) / 2,
            (wh - S.LOGICAL_H * self.scale) / 2,
        )

    def present(self):
        self._layout()
        size = (max(1, int(S.LOGICAL_W * self.scale)),
                max(1, int(S.LOGICAL_H * self.scale)))
        self.window.fill(S.BLACK)
        self.window.blit(pygame.transform.smoothscale(self.surface, size), self.offset)
        pygame.display.flip()

    def to_logical(self, px, py):
        return ((px - self.offset[0]) / self.scale, (py - self.offset[1]) / self.scale)

    def event_pos(self, event):
        """Posición lógica de un evento de ratón o de dedo (el dedo viene normalizado 0..1)."""
        if event.type in FINGER_EVENTS:
            ww, wh = self.window.get_size()
            return self.to_logical(event.x * ww, event.y * wh)
        return self.to_logical(*event.pos)
