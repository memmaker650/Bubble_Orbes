import os

# Pygame sin ventana ni audio, para CI y para este entorno.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
