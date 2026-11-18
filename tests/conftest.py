import os

# Pygame sin ventana ni audio, para CI y para este entorno.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from bubblequest import settings as S  # noqa: E402


@pytest.fixture(autouse=True)
def _no_intro(monkeypatch):
    """Sin la presentación del nivel 1: los tests van directos al nivel (test_intro.py la
    vuelve a activar)."""
    monkeypatch.setattr(S, "INTRO_ENABLED", False)
