"""Entrada unificada: teclado (macOS) + botones táctiles (iOS) + ratón sobre los botones."""

import pygame
from pygame import Rect

from . import settings as S

_Y = S.FIELD_H + 16
BUTTONS = {
    "left": Rect(10, _Y, 84, 90),
    "right": Rect(100, _Y, 84, 90),
    "jump": Rect(196, _Y, 76, 90),
    "bubble": Rect(278, _Y, 72, 90),
}

KEYS = {
    "left": (pygame.K_LEFT, pygame.K_a),
    "right": (pygame.K_RIGHT, pygame.K_d),
    "jump": (pygame.K_UP, pygame.K_w, pygame.K_SPACE),
    "bubble": (pygame.K_z, pygame.K_x, pygame.K_LSHIFT),
}


def _synthetic_mouse(event) -> bool:
    """SDL genera ratón falso a partir de toques; lo ignoramos para no duplicar."""
    return getattr(event, "touch", False)


def tap_position(event, display):
    """Posición lógica si el evento es un toque/clic de 'pulsar'; si no, None."""
    if event.type == pygame.FINGERDOWN:
        return display.event_pos(event)
    if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            and not _synthetic_mouse(event)):
        return display.event_pos(event)
    return None


def is_confirm(event, display) -> bool:
    if tap_position(event, display) is not None:
        return True
    return event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE)


class Controls:
    def __init__(self):
        self.touch: dict = {}      # finger_id -> acción
        self.mouse = None

    @staticmethod
    def _hit(pos):
        for name, rect in BUTTONS.items():
            if rect.collidepoint(pos):
                return name
        return None

    def handle_event(self, event, display):
        t = event.type
        if t in (pygame.FINGERDOWN, pygame.FINGERMOTION):
            action = self._hit(display.event_pos(event))
            if action:
                self.touch[event.finger_id] = action
            else:
                self.touch.pop(event.finger_id, None)
        elif t == pygame.FINGERUP:
            self.touch.pop(event.finger_id, None)
        elif t == pygame.MOUSEBUTTONDOWN and event.button == 1 and not _synthetic_mouse(event):
            self.mouse = self._hit(display.event_pos(event))
        elif t == pygame.MOUSEBUTTONUP and not _synthetic_mouse(event):
            self.mouse = None

    def actions(self) -> set:
        keys = pygame.key.get_pressed()
        result = {name for name, ks in KEYS.items() if any(keys[k] for k in ks)}
        result.update(self.touch.values())
        if self.mouse:
            result.add(self.mouse)
        return result

    def draw(self, surf, active):
        for name, rect in BUTTONS.items():
            on = name in active
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (*S.BUTTON, 230 if on else 130),
                             layer.get_rect(), border_radius=14)
            w, h = rect.size
            col = S.WHITE
            if name == "left":
                pygame.draw.polygon(layer, col, [(w * .65, h * .25), (w * .3, h * .5), (w * .65, h * .75)])
            elif name == "right":
                pygame.draw.polygon(layer, col, [(w * .35, h * .25), (w * .7, h * .5), (w * .35, h * .75)])
            elif name == "jump":
                pygame.draw.polygon(layer, col, [(w * .25, h * .65), (w * .5, h * .3), (w * .75, h * .65)])
            else:
                pygame.draw.circle(layer, col, (w // 2, h // 2), 18, 4)
            surf.blit(layer, rect.topleft)
