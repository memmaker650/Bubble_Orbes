"""Genera los iconos de la app para todas las plataformas de Briefcase.

El icono es el personaje del juego (el orbe verde) de perfil, con una burbuja formándose en su
boca, dibujado con la misma paleta que el juego. Se dibuja a 2048 px y se reduce con suavizado.

Uso (desde la raíz del proyecto):
    python tools/make_icons.py

Escribe en src/orbes/resources/:
    icon-<tamaño>.png           iOS (20 ... 1024), pantallas de arranque (640, 1280, 1920)
                                y Linux (16 ... 512)
    icon-round-<tamaño>.png     Android, icono redondo  (48, 72, 96, 144, 192)
    icon-square-<tamaño>.png    Android, icono cuadrado (48, 72, 96, 144, 192)
    icon.icns                   macOS (cuadrado redondeado con margen, guía de Apple)
    icon.ico                    Windows
    icon.png                    512 px: vista previa e icono de ventana (Windows, Linux)
    icon-macos.png              512 px con la forma de macOS: icono del Dock sin empaquetar
"""

import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from orbes import settings as S  # noqa: E402

OUT = ROOT / "src" / "orbes" / "resources"
IOS_SIZES = (20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 640, 1024, 1280, 1920)
LINUX_SIZES = (16, 32, 64, 128, 256, 512)
ANDROID_SIZES = (48, 72, 96, 144, 192)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
CANVAS = 2048                     # se dibuja grande y se reduce con suavizado

OUTLINE = (12, 40, 26)
MOUTH = (40, 20, 30)


def P(x, y):
    """Coordenadas de diseño (lienzo de 1024) a píxeles del lienzo real."""
    k = CANVAS / 1024
    return (round(x * k), round(y * k))


def L(v):
    return round(v * CANVAS / 1024)


def shade(color, k):
    return tuple(max(0, min(255, round(c * k))) for c in color)


def background(surf):
    """Degradado con el azul del juego, burbujitas de fondo y una plataforma abajo."""
    top, bottom = (44, 50, 104), (14, 16, 36)
    h = surf.get_height()
    for y in range(h):
        t = y / (h - 1)
        pygame.draw.line(surf, tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)),
                         (0, y), (surf.get_width(), y))
    deco = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for (x, y, r) in ((120, 170, 46), (250, 95, 26), (880, 150, 38), (930, 330, 20),
                      (90, 420, 18)):
        pygame.draw.circle(deco, (*S.BUBBLE, 40), P(x, y), L(r))
        pygame.draw.circle(deco, (*S.BUBBLE, 110), P(x, y), L(r), L(5))
    surf.blit(deco, (0, 0))
    # Plataforma (como las del juego)
    plat = pygame.Rect(*P(-40, 860), L(1104), L(70))
    pygame.draw.rect(surf, S.PLATFORM, plat, border_radius=L(30))
    pygame.draw.rect(surf, shade(S.PLATFORM, 0.7), plat, L(6), border_radius=L(30))


def character(surf):
    """El orbe verde de perfil, mirando a la derecha, con la boca abierta."""
    body = pygame.Rect(*P(150, 330), L(450), L(530))
    radius = L(120)
    # Sombra en la plataforma
    shadow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 70), (*P(150, 840), L(470), L(50)))
    surf.blit(shadow, (0, 0))
    # Cuerpo con contorno y volumen (más oscuro abajo y a la izquierda)
    pygame.draw.rect(surf, OUTLINE, body.inflate(L(22), L(22)), border_radius=radius + L(11))
    pygame.draw.rect(surf, shade(S.PLAYER, 0.72), body, border_radius=radius)
    lit = body.inflate(-L(40), -L(50)).move(L(16), -L(18))
    pygame.draw.rect(surf, S.PLAYER, lit, border_radius=radius - L(15))
    shine = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.ellipse(shine, (255, 255, 255, 70), (*P(215, 375), L(150), L(90)))
    surf.blit(shine, (0, 0))
    # Ojo (como en el juego: blanco con la pupila mirando hacia delante)
    eye = P(470, 480)
    pygame.draw.circle(surf, OUTLINE, eye, L(80))
    pygame.draw.circle(surf, S.WHITE, eye, L(70))
    pygame.draw.circle(surf, S.BLACK, P(497, 488), L(33))
    pygame.draw.circle(surf, S.WHITE, P(507, 474), L(10))
    # Boca abierta en el borde derecho, de donde sale la burbuja
    mouth = [P(600, 610), P(520, 655), P(600, 700)]
    pygame.draw.polygon(surf, MOUTH, mouth)
    pygame.draw.lines(surf, OUTLINE, False, mouth, L(12))


def bubble(surf):
    """Burbuja formándose en la boca (su borde entra en la boca), translúcida y con brillos,
    y burbujitas alrededor."""
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    cx, cy, r = 735, 650, 150
    # Relleno con un ligero degradado: más claro arriba a la izquierda
    edge, centre = (95, 170, 250), (185, 228, 255)          # azul saturado -> casi blanco
    for i in range(r, 0, -6):
        k = i / r                                            # 1 en el borde, 0 en el centro
        alpha = round(150 + 40 * (1 - k))
        color = tuple(round(e + (c - e) * (1 - k)) for e, c in zip(edge, centre))
        pygame.draw.circle(layer, (*color, alpha), P(cx - (1 - k) * 35, cy - (1 - k) * 35), L(i))
    pygame.draw.circle(layer, (*S.BUBBLE, 245), P(cx, cy), L(r), L(16))
    pygame.draw.circle(layer, (255, 255, 255, 70), P(cx, cy), L(r - 22), L(5))
    # Brillos
    pygame.draw.arc(layer, (255, 255, 255, 230), (*P(cx - 118, cy - 118), L(150), L(150)),
                    1.75, 2.95, L(16))
    pygame.draw.circle(layer, (255, 255, 255, 240), P(cx + 62, cy - 92), L(16))
    # Burbujitas que acompañan
    for (x, y, rr) in ((905, 470, 42), (955, 390, 22), (880, 805, 26)):
        pygame.draw.circle(layer, (*S.BUBBLE, 90), P(x, y), L(rr))
        pygame.draw.circle(layer, (*S.BUBBLE, 230), P(x, y), L(rr), L(7))
        pygame.draw.circle(layer, (255, 255, 255, 210), P(x - rr * 0.35, y - rr * 0.35),
                           L(max(4, rr // 5)))
    surf.blit(layer, (0, 0))


def artwork() -> pygame.Surface:
    art = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    background(art)
    character(art)
    bubble(art)
    return art


def resized(surf, size):
    return pygame.transform.smoothscale(surf, (size, size))


def macos_shape(art: pygame.Surface) -> pygame.Surface:
    """Icono de macOS: cuadrado redondeado de 824/1024 con margen y sombra (guía de Apple)."""
    out = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    inner = L(824)
    off = (CANVAS - inner) // 2
    shadow = pygame.Surface((CANVAS, CANVAS), pygame.SRCALPHA)
    for i in range(12, 0, -1):
        pygame.draw.rect(shadow, (0, 0, 0, 7), (off - i * 2, off + L(10) - i, inner + i * 4,
                                                inner + i * 3), border_radius=L(185) + i * 2)
    out.blit(shadow, (0, 0))
    out.blit(rounded(art, inner, L(185)), (off, off))
    return out


def rounded(art, size, radius):
    """`art` reducido a `size` y recortado con esquinas redondeadas (o círculo)."""
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    scaled = pygame.Surface((size, size), pygame.SRCALPHA)    # con canal alfa (aunque `art`
    scaled.blit(pygame.transform.smoothscale(art, (size, size)), (0, 0))   # no lo tenga)
    scaled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return scaled


def png_bytes(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def write_ico(path: Path, art):
    """.ico con imágenes PNG dentro (formato admitido desde Windows Vista)."""
    images = [png_bytes(resized(art, s)) for s in ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for size, img in zip(ICO_SIZES, images):
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(img),
                               offset + len(data))
        data += img
    path.write_bytes(header + entries + data)


def write_icns(path: Path, art):
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            pygame.image.save(resized(art, size), str(iconset / f"icon_{size}x{size}.png"))
            pygame.image.save(resized(art, size * 2), str(iconset / f"icon_{size}x{size}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(path)], check=True)


def main():
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    art = artwork()
    flat = pygame.Surface(art.get_size())                     # iOS: sin transparencia
    flat.blit(art, (0, 0))
    for size in sorted(set(IOS_SIZES) | set(LINUX_SIZES)):
        pygame.image.save(resized(flat, size), str(OUT / f"icon-{size}.png"))
    for size in ANDROID_SIZES:
        pygame.image.save(rounded(flat, size, size // 2), str(OUT / f"icon-round-{size}.png"))
        pygame.image.save(resized(flat, size), str(OUT / f"icon-square-{size}.png"))
    pygame.image.save(resized(flat, 512), str(OUT / "icon.png"))
    mac = macos_shape(art)
    pygame.image.save(resized(mac, 512), str(OUT / "icon-macos.png"))   # ventana en macOS
    if shutil.which("iconutil"):
        write_icns(OUT / "icon.icns", mac)
    else:
        print("Aviso: iconutil no existe (solo en macOS); no se genera icon.icns")
    write_ico(OUT / "icon.ico", mac)
    print("Iconos generados en", OUT)


if __name__ == "__main__":
    main()
