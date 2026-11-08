"""Guardar y retomar la partida: convierte el estado del mundo en un dict serializable a JSON.

Se guarda el nivel por su número (no por su posición en la lista) para que la partida siga
siendo válida aunque se añadan niveles. Si el mapa del nivel ha cambiado desde que se guardó
(no cuadran los enemigos), se retoma desde el principio de ese nivel con los puntos y vidas
que se tenían al empezarlo.
"""

import logging

from . import levels
from . import settings as S
from .entities import Bubble
from .world import World

log = logging.getLogger(__name__)

SAVE_VERSION = 2
# Versiones anteriores que aún se aceptan, pero solo para empezar el nivel desde el principio
# (v1: mapas con bordes de una casilla; las posiciones guardadas ya no sirven).
LEGACY_VERSIONS = {1}

_BODY = ("fx", "fy", "vx", "vy", "on_ground", "coyote")
_ENEMY = _BODY + ("direction", "state", "alive", "angry", "jump_cd",
                  "attack", "attack_t", "cooldown", "sight_t", "tired",
                  "super_attack")
_BUBBLE = ("fx", "fy", "vx", "state", "timer", "life", "age")


def _fields(obj, names) -> dict:
    return {n: getattr(obj, n) for n in names}


def _apply(obj, data, names):
    for n in names:
        if n in data:
            setattr(obj, n, data[n])
    obj.rect.topleft = (round(obj.fx), round(obj.fy))


def _player_data(w: World) -> dict:
    p = w.player
    data = {**_fields(p, _BODY), "facing": p.facing, "shoot_cd": p.shoot_cd, "invuln": p.invuln}
    if w.state == "dying":
        # Se cerró durante la animación de muerte (y le quedan vidas): se guarda como si
        # ya hubiera reaparecido en el inicio.
        x, y = w.spawn[0] + 6, w.spawn[1] + 8
        data.update(fx=float(x), fy=float(y), vx=0.0, vy=0.0, invuln=S.INVULN_TIME)
    return data


def snapshot(w: World) -> dict | None:
    """Estado a guardar, o None si no hay nada que retomar (partida perdida o juego terminado)."""
    if w.state == "lost" or (w.state == "dying" and w.lives <= 0):
        return None
    if w.state == "won":
        # Nivel terminado: se retoma al principio del siguiente
        if w.is_last_level:
            return None
        nxt = levels.LEVELS[w.level_index + 1]
        lives, score = (w.rules["lives"], 0) if w.tutorial else (w.lives, w.score)
        return {"version": SAVE_VERSION, "level_number": nxt.number, "tutorial": nxt.tutorial,
                "difficulty": w.difficulty, "lives": lives, "score": score, "fresh": True}

    p = w.player
    enemies = []
    for e in w.enemies:
        data = _fields(e, _ENEMY)
        data["kind"] = e.kind
        if e.kind == "laser":
            data["beam_end"] = e.beam_end
        enemies.append(data)
    bubbles = []
    for b in w.bubbles:
        data = _fields(b, _BUBBLE)
        data["captured"] = w.enemies.index(b.captured) if b.captured is not None else None
        bubbles.append(data)
    return {
        "version": SAVE_VERSION,
        "level_number": w.number,
        "tutorial": w.tutorial,
        "difficulty": w.difficulty,
        "lives": w.lives,
        "score": w.score,
        "fresh": False,
        "level_start_score": w.level_start_score,
        "elapsed": w.elapsed,
        "tutorial_done": sorted(w.tutorial_done),
        "touching_star": w._touching_star,
        "star_lit": w.star.lit if w.star is not None else False,
        "player": _player_data(w),
        "enemies": enemies,
        "bubbles": bubbles,
    }


def restore(data: dict) -> World:
    """Reconstruye el mundo a partir de lo guardado. Lanza ValueError si los datos no sirven."""
    try:
        version = data.get("version")
        if version != SAVE_VERSION and version not in LEGACY_VERSIONS:
            raise ValueError(f"versión de guardado desconocida: {version}")
        index = levels.index_of(int(data["level_number"]))
        lives, score = int(data["lives"]), int(data["score"])
        # Partidas guardadas antes de existir la dificultad: "normal"
        difficulty = data.get("difficulty", S.DEFAULT_DIFFICULTY)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"partida guardada no válida: {exc}") from exc

    if data.get("fresh"):
        return World(index, lives, score, difficulty=difficulty)
    if version in LEGACY_VERSIONS:
        log.info("Partida guardada con formato v%s: se retoma desde el principio del nivel", version)
        return World(index, lives, int(data.get("level_start_score", score)),
                     difficulty=difficulty)

    w = World(index, lives, int(data.get("level_start_score", score)), difficulty=difficulty)
    saved_enemies = data.get("enemies", [])
    if [e.kind for e in w.enemies] != [e.get("kind") for e in saved_enemies]:
        log.warning("El nivel %s ha cambiado desde que se guardó; se empieza desde el principio",
                    w.number)
        return w

    try:
        w.score = score
        w.elapsed = float(data.get("elapsed", 0.0))
        w.tutorial_done = set(data.get("tutorial_done", []))
        w._touching_star = bool(data.get("touching_star", False))
        if w.star is not None:
            w.star.lit = bool(data.get("star_lit", False))

        pd = data["player"]
        _apply(w.player, pd, _BODY)
        w.player.facing = pd.get("facing", 1)
        w.player.shoot_cd = pd.get("shoot_cd", 0.0)
        # Unos segundos de margen para que no te maten nada más volver
        w.player.invuln = max(pd.get("invuln", 0.0), S.RESUME_INVULN)

        for e, ed in zip(w.enemies, saved_enemies):
            _apply(e, ed, _ENEMY)
            if e.kind == "laser":
                e.beam_end = ed.get("beam_end", 0)

        w.bubbles = []
        for bd in data.get("bubbles", []):
            b = Bubble(0, 0, 1)
            _apply(b, bd, _BUBBLE)
            if bd.get("captured") is not None:
                b.captured = w.enemies[bd["captured"]]
                b.captured.center_on(b.rect.center)
            w.bubbles.append(b)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValueError(f"partida guardada no válida: {exc}") from exc

    w.message, w.message_timer = "", 0.0  # no repetir el aviso inicial del tutorial
    w.snap_camera()
    return w
