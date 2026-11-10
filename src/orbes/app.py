"""Aplicación: bucle principal y gestión de escenas."""

import logging
import sys
from pathlib import Path

import pygame

from . import __version__
from . import settings as S
from . import translations
from .db import Database, default_db_path
from .display import Display
from .log import setup_logging
from .scenes import MenuScene

log = logging.getLogger(__name__)

RESOURCES = Path(__file__).parent / "resources"
ICON_PATH = RESOURCES / "icon.png"                 # icono de la ventana (tools/make_icons.py)
MACOS_ICON_PATH = RESOURCES / "icon-macos.png"     # con esquinas redondeadas y margen de macOS


def set_window_icon():
    """Icono de la ventana / del Dock al ejecutar sin empaquetar (empaquetada, la app usa el
    icono de Briefcase). En iOS no hay ventana que decorar."""
    if sys.platform == "ios":
        return
    path = MACOS_ICON_PATH if sys.platform == "darwin" else ICON_PATH
    try:
        pygame.display.set_icon(pygame.image.load(str(path)))
    except (FileNotFoundError, pygame.error):
        log.warning("No se encontró el icono %s (genéralo con tools/make_icons.py)", path)


# iOS manda a segundo plano la app y puede cerrarla sin avisar: se guarda en ese momento.
SAVE_EVENTS = (pygame.APP_WILLENTERBACKGROUND, pygame.APP_TERMINATING)


class App:
    def __init__(self, db_path=None):
        pygame.init()
        pygame.display.set_caption("Orbes")
        set_window_icon()                  # antes de crear la ventana
        self.display = Display()
        self.db = Database(db_path or default_db_path())
        translations.load()
        translations.set_language(self.db.get_setting("language", translations.current().code))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = MenuScene(self)

    def change_scene(self, scene):
        self.scene = scene

    def quit(self):
        self.running = False

    def run(self, max_frames=None):
        frames = 0
        try:
            while self.running:
                dt = min(self.clock.tick(S.FPS) / 1000.0, 1 / 30)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.scene.on_close()
                        self.running = False
                    elif event.type in SAVE_EVENTS:
                        self.scene.on_close()
                    else:
                        self.scene.handle_event(event)
                self.scene.update(dt)
                self.scene.draw(self.display.surface)
                self.display.present()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        except Exception:
            log.exception("Error no controlado en el bucle principal (escena %s)",
                          type(self.scene).__name__)
            raise
        finally:
            log.info("Cerrando la aplicación tras %d frames", frames)
            self.db.close()
            pygame.quit()


def main():
    setup_logging()     # consola + BubbleQuest_AAAAMMDD.log (ver log.py y paths.py)
    log.info("Iniciando Orbes %s (Python %s, pygame-ce %s, %s)", __version__,
             sys.version.split()[0], pygame.version.ver, sys.platform)
    App().run()
