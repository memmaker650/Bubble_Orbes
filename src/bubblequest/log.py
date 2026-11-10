"""Configuración central de logging: consola + un fichero por día en la carpeta de logs.

Cada módulo crea su propio logger con ``logging.getLogger(__name__)``; aquí solo se configura
el logger raíz del paquete una vez, al arrancar la app. El nivel se puede cambiar con la
variable de entorno ``BUBBLEQUEST_LOG_LEVEL`` (DEBUG, INFO, WARNING, ERROR).

Los ficheros se llaman ``BubbleQuest_AAAAMMDD.log`` y van a ``log/`` dentro de la carpeta de
datos (ver paths.py; en macOS
``~/Library/Application Support/com.SkullWithGasMask/BubbleQuest/log``). Si la app sigue abierta
al cambiar de día se pasa al fichero nuevo. Se conservan solo los ``KEEP_FILES`` ficheros más
recientes (por la fecha de su nombre), aunque no sean de días seguidos: si se juega de vez en
cuando, siguen ahí los logs de las últimas partidas.
"""

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from . import paths

FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
PACKAGE = __name__.rpartition(".")[0] or "bubblequest"
FILE_PREFIX = "BubbleQuest_"
DATE_FORMAT = "%Y%m%d"
KEEP_FILES = 10                   # al arrancar (y al cambiar de día) quedan los 10 últimos
LEVEL_ENV_VAR = "BUBBLEQUEST_LOG_LEVEL"


def default_log_dir() -> Path:
    """Carpeta de logs: ``log/`` dentro de la carpeta de datos del juego (ver paths.py)."""
    return paths.log_dir()


def log_file_for(log_dir: Path, day: date) -> Path:
    return Path(log_dir) / f"{FILE_PREFIX}{day.strftime(DATE_FORMAT)}.log"


def remove_old_logs(log_dir: Path, keep_files: int = KEEP_FILES) -> list[Path]:
    """Deja solo los ``keep_files`` ficheros ``BubbleQuest_AAAAMMDD.log`` más recientes (según
    la fecha de su nombre) y borra el resto, sin importar cuántos días hayan pasado. No toca
    ningún otro fichero. Devuelve los borrados, del más antiguo al más reciente."""
    logs = []
    for path in Path(log_dir).glob(f"{FILE_PREFIX}*.log"):
        try:
            day = datetime.strptime(path.stem[len(FILE_PREFIX):], DATE_FORMAT).date()
        except ValueError:
            continue  # no es un log diario nuestro (p. ej. una fecha imposible)
        logs.append((day, path))
    logs.sort()
    removed = []
    for _, path in (logs[:-keep_files] if keep_files > 0 else logs):
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
    return removed


class DailyFileHandler(logging.FileHandler):
    """Escribe en el fichero del día del registro y cambia de fichero al cambiar de día."""

    def __init__(self, log_dir, keep_files: int = KEEP_FILES):
        self.log_dir = Path(log_dir)
        self.keep_files = keep_files
        self.day = date.today()
        super().__init__(log_file_for(self.log_dir, self.day), encoding="utf-8")

    def emit(self, record):
        day = date.fromtimestamp(record.created)
        new_day = day != self.day
        if new_day:
            self.day = day
            if self.stream:
                self.stream.close()
                self.stream = None  # FileHandler.emit lo vuelve a abrir con el nombre nuevo
            self.baseFilename = os.path.abspath(log_file_for(self.log_dir, day))
        super().emit(record)
        if new_day:  # después de crear el fichero nuevo: así quedan justo `keep_files`
            remove_old_logs(self.log_dir, self.keep_files)


def setup_logging(level=None, log_dir=None) -> logging.Logger:
    """Configura el logger del paquete. Llamar una sola vez desde ``main()``."""
    level = level or os.environ.get(LEVEL_ENV_VAR, "INFO")
    logger = logging.getLogger(PACKAGE)
    logger.setLevel(level.upper() if isinstance(level, str) else level)
    if logger.handlers:  # ya configurado
        return logger

    formatter = logging.Formatter(FORMAT)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_dir = Path(log_dir) if log_dir else default_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = DailyFileHandler(log_dir)    # crea el fichero de hoy...
        removed = remove_old_logs(log_dir)           # ...y luego deja los 10 últimos (con él)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("No se pudo crear el fichero de log en %s; solo consola", log_dir,
                       exc_info=True)
    else:
        logger.info("Log en fichero: %s", file_handler.baseFilename)
        if removed:
            logger.info("Borrados %d logs antiguos (se conservan los %d últimos): %s",
                        len(removed), KEEP_FILES, ", ".join(p.name for p in removed))
    return logger
