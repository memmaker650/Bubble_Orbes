"""Constantes del juego. Todo en coordenadas lógicas (se escala a la ventana)."""

# --- Pantalla lógica (relación ~ iPhone en vertical) ---
TILE = 40
COLS = 9                       # casillas interiores del nivel (los bordes no cuentan)
ROWS = 16
BORDER = 12                    # grosor visible de los bordes del nivel (antes 1 casilla = 40)
FIELD_W = COLS * TILE + 2 * BORDER   # 384
FIELD_H = ROWS * TILE + 2 * BORDER   # 664  -> zona de juego (coordenadas del mundo)
HUD_H = 28                     # franja superior con puntos, nivel y vidas
CONTROLS_H = 120               # barra de controles táctiles
LOGICAL_W = FIELD_W
LOGICAL_H = HUD_H + FIELD_H + CONTROLS_H   # 812 (misma proporción que antes)
FLOOR_Y = FIELD_H - BORDER     # altura del suelo (borde inferior)


def cell_pos(col, row):
    """Esquina superior izquierda de una casilla interior en coordenadas del mundo."""
    return BORDER + col * TILE, BORDER + row * TILE
FPS = 60

# --- Física ---
GRAVITY = 1500.0
MAX_FALL = 700.0
JUMP_V = 640.0                 # ~136 px de salto: llega a plataformas a 3 filas
PLAYER_SPEED = 170.0
COYOTE_TIME = 0.08

# --- Enemigos ---
ENEMY_BASE_SPEED = 55.0
ENEMY_SPEED_STEP = 12.0        # +velocidad por nivel
ENEMY_ANGRY_FACTOR = 1.6

# Enemigo rojo: lengua
TONGUE_RANGE = 110             # longitud máxima de la lengua
TONGUE_OUT = 0.18              # segundos en sacarla
TONGUE_HOLD = 0.15             # segundos estirada
TONGUE_IN = 0.2                # segundos en recogerla
TONGUE_COOLDOWN = 1.5

# Enemigo azul: láser por los ojos
LASER_WINDUP = 0.35            # aviso (ojos brillando) antes de disparar; 0 = sin aviso
LASER_DURATION = 1.0           # el rayo dura 1 s
LASER_RECHARGE = 4.0           # y necesita 4 s para recargar

# --- Burbujas ---
BUBBLE_SIZE = 28
BUBBLE_SPEED = 300.0
BUBBLE_SHOT_TIME = 0.4
BUBBLE_RISE = 55.0
BUBBLE_EMPTY_LIFE = 5.0
BUBBLE_ENEMY_LIFE = 7.0
BUBBLE_ARM_TIME = 0.25         # tiempo antes de poder reventarla
SHOOT_COOLDOWN = 0.3

# --- Dificultad ---
# "normal" es el juego tal cual (láser 1 s + 4 s de recarga). Los factores multiplican:
#   enemy_speed -> velocidad de los enemigos
#   cooldown    -> tiempo de recarga de la lengua y del láser
DIFFICULTIES = {
    "easy":   {"lives": 5, "enemy_speed": 0.8,  "cooldown": 1.25, "bubble_life": 9.0},
    "normal": {"lives": 3, "enemy_speed": 1.0,  "cooldown": 1.0,  "bubble_life": 7.0},
    "hard":   {"lives": 2, "enemy_speed": 1.25, "cooldown": 0.75, "bubble_life": 5.0},
}
DIFFICULTY_ORDER = ("easy", "normal", "hard")
DEFAULT_DIFFICULTY = "normal"

# --- Animaciones de muerte ---
GHOST_ALPHA = 153              # enemigo eliminado: 60 % de opacidad (153 de 255)
GHOST_WING_SCALE = 1.25        # tamaño de las alas (1.0 = tamaño original)
GHOST_RISE_START = 40.0        # sube despacio al principio...
GHOST_RISE_ACCEL = 160.0
GHOST_RISE_MAX = 260.0         # ...y acelera hasta esta velocidad (px/s)
DEATH_TIP_TIME = 0.2           # el jugador tarda esto en caer tumbado al hacer pie
DEATH_TIME = 1.6               # tiempo tumbado antes de reaparecer (si quedan vidas)
# Muerte final (sin vidas): tumbado -> se hunde en el suelo -> sale una lápida -> fin de partida
GRAVE_LIE = 0.6                # tumbado antes de empezar a hundirse
GRAVE_SINK = 0.9               # lo que tarda en hundirse del todo
GRAVE_RISE = 0.5               # lo que tarda la lápida en salir del suelo
GRAVE_RISE_START = 0.6         # la lápida empieza a salir a este punto del hundimiento (0..1)
GRAVE_HOLD = 1.2               # tumba a la vista antes de la ventana de fin de partida

# --- Estrella de fin de nivel ---
STAR_SIZE = 30
CELEBRATE_TIME = 1.8           # segundos celebrando (ya en el suelo) antes del mensaje
CELEBRATE_ARM_TIME = 0.3       # lo que tarda en levantar el brazo al hacer pie
CELEBRATE_TONGUE_AT = 0.6      # después saca la lengua (segundos desde que hace pie)
CELEBRATE_TONGUE_GROW = 0.15   # lo que tarda la lengua en salir del todo
CELEBRATE_MAX = 5.0            # tope desde que se toca la estrella, por si nunca hace pie
MESSAGE_TIME = 2.5             # duración de los avisos en pantalla

# --- Reglas ---
START_LIVES = 3
INVULN_TIME = 2.0
RESUME_INVULN = 2.0            # invulnerable al retomar una partida guardada
POINTS_BUBBLE = 10
POINTS_ENEMY = 100
POINTS_LEVEL = 500

# --- Colores ---
BG = (18, 20, 40)
SOLID = (70, 80, 150)
PLATFORM = (120, 140, 230)
PLAYER = (80, 220, 140)
PLAYER_DARK = (40, 150, 90)
PLAYER_TONGUE = (225, 40, 55)
WING = (235, 240, 255)
WING_EDGE = (150, 180, 230)
DIRT = (115, 82, 52)
DIRT_DARK = (80, 56, 36)
STONE = (150, 152, 168)
STONE_DARK = (95, 97, 112)
ENEMY = (235, 90, 90)
ENEMY_BLUE = (80, 130, 240)
TONGUE = (255, 120, 170)
LASER = (255, 40, 40)
BUBBLE = (150, 210, 255)
WHITE = (240, 240, 250)
BLACK = (0, 0, 0)
BUTTON = (50, 60, 120)
STAR_YELLOW = (255, 215, 40)
STAR_BLUE = (60, 140, 255)
PANEL = (28, 32, 70)
