"""Aplicación: bucle principal y gestión de escenas."""

import pygame

from . import settings as S
from .db import Database, default_db_path
from .display import Display
from .scenes import MenuScene


class App:
    def __init__(self, db_path=None):
        pygame.init()
        pygame.display.set_caption("Orbes")
        self.display = Display()
        self.db = Database(db_path or default_db_path())
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
                        self.running = False
                    else:
                        self.scene.handle_event(event)
                self.scene.update(dt)
                self.scene.draw(self.display.surface)
                self.display.present()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        finally:
            self.db.close()
            pygame.quit()


def main():
    App().run()
