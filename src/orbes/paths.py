"""Carpeta de datos del juego (logs), según el sistema operativo:

  macOS:   ~/Library/Application Support/com.SkullWithGasMask/BubbleQuest
  iOS:     <contenedor de la app>/Library/Application Support/com.SkullWithGasMask/BubbleQuest
           (en iOS ~ es la carpeta privada de la app, así que la ruta relativa es la misma)
  Windows: %APPDATA%\\com.SkullWithGasMask\\BubbleQuest
  Linux:   ~/.local/share/com.SkullWithGasMask/BubbleQuest  (o $XDG_DATA_HOME)

Dentro: ``log/`` (un fichero por día, ver log.py).
Con la variable de entorno BUBBLEQUEST_DATA se puede usar otra carpeta (p. ej. para pruebas).
"""

import os
import sys
from pathlib import Path

from . import settings as S

ENV_VAR = "BUBBLEQUEST_DATA"


def data_dir(system=None, home=None, env=None) -> Path:
    """Carpeta de datos según el sistema (no la crea)."""
    system = sys.platform if system is None else system
    home = Path.home() if home is None else Path(home)
    env = os.environ if env is None else env

    if env.get(ENV_VAR):
        return Path(env[ENV_VAR])
    if system in ("darwin", "ios"):
        base = home / "Library" / "Application Support"
    elif system.startswith("win"):
        base = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
    else:
        base = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return base / S.ORG_ID / S.APP_NAME


def log_dir(**kwargs) -> Path:
    """Carpeta de los ficheros de log: ``log/`` dentro de la carpeta de datos."""
    return data_dir(**kwargs) / "log"
