"""Ayuda para tests: obtener un enemigo de un tipo concreto en un mundo."""

from bubblequest import settings as S


def enemy_of(world, cls):
    """El primer enemigo de la clase `cls` del nivel; si el nivel no tiene ninguno (p. ej. el
    nivel 1 ya no tiene azules), se crea uno con las reglas del nivel y se añade."""
    found = next((e for e in world.enemies if isinstance(e, cls)), None)
    if found is not None:
        return found
    e = cls(*S.cell_pos(4, 9), world.enemies[0].speed, world.rng)
    e.cooldown_factor = world.rules["cooldown"]
    e.attack_delay = world.rules["attack_delay"]
    world.enemies.append(e)
    return e
