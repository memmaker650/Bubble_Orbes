"""Carpeta de datos (paths.py): dónde van los logs según el sistema operativo."""

from pathlib import Path

from orbes import paths
from orbes.paths import data_dir, log_dir

HOME = Path("/Users/memmaker650")
END = Path("com.SkullWithGasMask") / "BubbleQuest"


def test_macos():
    assert data_dir("darwin", HOME, {}) == Path(
        "/Users/memmaker650/Library/Application Support/com.SkullWithGasMask/BubbleQuest")


def test_ios_same_relative_path_inside_the_app_container():
    container = Path("/var/mobile/Containers/Data/Application/1234-ABCD")
    assert data_dir("ios", container, {}) == container / "Library" / "Application Support" / END


def test_windows():
    assert data_dir("win32", HOME, {"APPDATA": r"C:\Users\x\AppData\Roaming"}) == \
        Path(r"C:\Users\x\AppData\Roaming") / END
    assert data_dir("win32", HOME, {}) == HOME / "AppData" / "Roaming" / END


def test_linux():
    assert data_dir("linux", HOME, {}) == HOME / ".local" / "share" / END
    assert data_dir("linux", HOME, {"XDG_DATA_HOME": "/datos"}) == Path("/datos") / END


def test_environment_variable_wins(tmp_path):
    assert data_dir("darwin", HOME, {paths.ENV_VAR: str(tmp_path)}) == tmp_path


def test_logs_go_to_a_log_subfolder():
    assert log_dir(system="darwin", home=HOME, env={}) == data_dir("darwin", HOME, {}) / "log"


def test_data_dir_creates_nothing(tmp_path):
    data_dir("darwin", tmp_path, {})
    assert list(tmp_path.iterdir()) == []
