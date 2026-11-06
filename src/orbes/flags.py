"""Banderas dibujadas con formas básicas (sin imágenes externas) y caché por tamaño."""

import logging

import pygame

log = logging.getLogger(__name__)

_cache: dict = {}

UK_BLUE = (1, 33, 105)
UK_RED = (200, 16, 46)
ES_RED = (170, 21, 27)
ES_YELLOW = (241, 191, 0)
FR_BLUE = (0, 35, 149)
FR_RED = (237, 41, 57)
WHITE = (255, 255, 255)


def _spain(surf, w, h):
    surf.fill(ES_RED)
    pygame.draw.rect(surf, ES_YELLOW, (0, h // 4, w, h - 2 * (h // 4)))


def _france(surf, w, h):
    third = w / 3
    pygame.draw.rect(surf, FR_BLUE, (0, 0, round(third), h))
    pygame.draw.rect(surf, WHITE, (round(third), 0, round(third), h))
    pygame.draw.rect(surf, FR_RED, (round(2 * third), 0, w - round(2 * third), h))


def _uk(surf, w, h):
    surf.fill(UK_BLUE)
    diag = max(3, h // 5)
    pygame.draw.line(surf, WHITE, (0, 0), (w, h), diag)
    pygame.draw.line(surf, WHITE, (0, h), (w, 0), diag)
    pygame.draw.line(surf, UK_RED, (0, 0), (w, h), max(1, diag // 3))
    pygame.draw.line(surf, UK_RED, (0, h), (w, 0), max(1, diag // 3))
    cross = max(4, h // 3)
    pygame.draw.rect(surf, WHITE, (0, (h - cross) // 2, w, cross))
    pygame.draw.rect(surf, WHITE, ((w - cross) // 2, 0, cross, h))
    red = max(2, cross * 3 // 5)
    pygame.draw.rect(surf, UK_RED, (0, (h - red) // 2, w, red))
    pygame.draw.rect(surf, UK_RED, ((w - red) // 2, 0, red, h))


_PAINTERS = {"es": _spain, "uk": _uk, "fr": _france}


def flag_surface(flag: str, size: tuple[int, int]):
    """Superficie con la bandera ``flag`` ('es', 'uk', 'fr') del tamaño indicado."""
    key = (flag, size)
    surf = _cache.get(key)
    if surf is not None:
        return surf
    surf = pygame.Surface(size)
    painter = _PAINTERS.get(flag)
    if painter is None:
        log.warning("Bandera desconocida %r; se dibuja un recuadro gris", flag)
        surf.fill((90, 90, 90))
    else:
        painter(surf, *size)
    _cache[key] = surf
    return surf
