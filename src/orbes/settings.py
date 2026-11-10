"""Constantes del juego. Todo en coordenadas lógicas (se escala a la ventana)."""

# --- Carpetas de usuario (logs) ---
ORG_ID = "com.SkullWithGasMask"   # <base>/com.SkullWithGasMask/BubbleQuest (ver paths.py)
APP_NAME = "BubbleQuest"

# --- Pantalla lógica (relación ~ iPhone en vertical) ---
TILE = 40
COLS = 9                       # casillas interiores del nivel (los bordes no cuentan)
ROWS = 16                      # filas visibles en pantalla (y mínimo de un nivel); un nivel
                               # puede tener más filas y entonces se hace scroll vertical
BORDER = 12                    # grosor visible de los bordes del nivel (antes 1 casilla = 40)
FIELD_W = COLS * TILE + 2 * BORDER   # 384
FIELD_H = ROWS * TILE + 2 * BORDER   # 664  -> zona de juego (coordenadas del mundo)
HUD_H = 28                     # franja superior con puntos, nivel y vidas
CONTROLS_H = 120               # barra de controles táctiles
LOGICAL_W = FIELD_W
LOGICAL_H = HUD_H + FIELD_H + CONTROLS_H   # 812 (misma proporción que antes)
FLOOR_Y = FIELD_H - BORDER     # altura del suelo en un nivel de 16 filas (borde inferior)


def level_height(rows):
    """Alto del mundo (px) para un nivel de `rows` filas, con sus bordes."""
    return rows * TILE + 2 * BORDER


def cell_pos(col, row):
    """Esquina superior izquierda de una casilla interior en coordenadas del mundo."""
    return BORDER + col * TILE, BORDER + row * TILE
FPS = 60

# --- Cámara (niveles más altos que la pantalla) ---
CAMERA_ANCHOR = 0.55           # el jugador se mantiene a esta altura de la pantalla (0 arriba)
CAMERA_SMOOTH = 7.0            # rapidez con que la cámara alcanza al jugador

# --- Física ---
GRAVITY = 1500.0
MAX_FALL = 700.0
JUMP_V = 640.0                 # salto completo ~136 px: llega a plataformas a 3 filas
JUMP_FULL_H = JUMP_V ** 2 / (2 * GRAVITY)       # altura del salto completo (~136 px)
# Jugador: una pulsación salta la mitad de alto; una segunda pulsación en el aire completa el
# salto hasta JUMP_FULL_H (desde donde despegó). Los enemigos siguen usando JUMP_V.
JUMP_SHORT_FACTOR = 0.5        # fracción de la altura completa con una sola pulsación
JUMP_V_SHORT = (2 * GRAVITY * JUMP_FULL_H * JUMP_SHORT_FACTOR) ** 0.5
PLAYER_SPEED = 170.0
COYOTE_TIME = 0.08
DROP_TIME = 0.2                # al pulsar abajo, ignora las plataformas finas este tiempo

# --- Enemigos ---
ENEMY_BASE_SPEED = 55.0
ENEMY_SPEED_STEP = 12.0        # +velocidad por nivel...
ENEMY_SPEED_MAX_STEPS = 6      # ...hasta el nivel 7; después no aumenta (no superan al jugador)
ENEMY_ANGRY_FACTOR = 1.6

# Enemigo rojo: lengua
TONGUE_RANGE = 110             # longitud de la lengua en el súper ataque (alcance máximo)
TONGUE_REACH_NORMAL = 55       # ataque normal: la mitad
TONGUE_OUT = 0.18              # segundos en sacarla
TONGUE_HOLD = 0.15             # segundos estirada
TONGUE_IN = 0.2                # segundos en recogerla
TONGUE_COOLDOWN = 1.5
TIRED_SPEED = 0.7              # tras sacar la lengua va cansado: un 30 % más lento
TIRED_TONGUE_LEN = 6.75        # lengua de cansancio: largo mínimo (px)...
TIRED_TONGUE_PANT = 4.5        # ...más lo que se estira al jadear
TIRED_MOUTH_ANGLE = 30         # boca abierta (grados) mientras jadea
TIRED_MOUTH_DEPTH = 15         # profundidad de la boca abierta dentro del cuerpo (px)
TIRED_LEAN = 10                # inclinación hacia delante al ir cansado (grados)
MOUTH_INSIDE = (95, 20, 35)

# Enemigo azul: láser por los ojos
LASER_WINDUP = 0.35            # aviso (ojos brillando) antes de disparar; 0 = sin aviso
LASER_DURATION = 1.0           # el rayo dura 1 s
LASER_RECHARGE = 4.0           # y necesita 4 s para recargar
LASER_REACH_NORMAL = 180       # ataque normal: hasta la mitad del ancho; súper: hasta el muro

# Ataque normal: si el jugador está cerca (dentro del alcance normal); recarga normal.
# Súper ataque: si está más lejos (hasta el alcance máximo); recarga este número de veces más.
SUPER_COOLDOWN_FACTOR = 2.0

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
# "normal" es el juego tal cual (láser 1 s + 4 s de recarga).
#   enemy_speed  -> multiplica la velocidad de los enemigos (fácil -30 %, difícil +30 %)
#   attack_delay -> segundos que el enemigo tiene que verte antes de atacar (fácil +0,3 s)
#   preempt      -> ataques preventivos: atacan donde vas a estar (difícil)
#   cooldown     -> multiplica la recarga de la lengua y del láser
#   lives, bubble_life -> vidas iniciales y segundos que dura un enemigo atrapado
#   max_lives    -> máximo de corazones (superando niveles o con botiquines)
DIFFICULTIES = {
    "easy":   {"lives": 5, "max_lives": 5, "enemy_speed": 0.7, "attack_delay": 0.3,
               "preempt": False, "cooldown": 1.25, "bubble_life": 9.0},
    "normal": {"lives": 3, "max_lives": 3, "enemy_speed": 1.0, "attack_delay": 0.0,
               "preempt": False, "cooldown": 1.0, "bubble_life": 7.0},
    "hard":   {"lives": 2, "max_lives": 3, "enemy_speed": 1.3, "attack_delay": 0.0,
               "preempt": True, "cooldown": 0.75, "bubble_life": 5.0},
}
LEVEL_HEAL = 1.0               # corazones que se ganan al superar un nivel
PREEMPT_LOOKAHEAD = 0.4        # difícil: los enemigos anticipan dónde estarás en estos segundos
DIFFICULTY_ORDER = ("easy", "normal", "hard")
DEFAULT_DIFFICULTY = "normal"
LEVEL_SELECT = True            # selector de nivel en "Nueva partida" (para probar niveles)

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
# Daño en corazones. El contacto quita medio: si el corazón solo queda "a medias" se sigue
# jugando (herido); si se vacía del todo, muere. Lengua y láser quitan uno entero y matan.
DAMAGE_TOUCH = 0.5
DAMAGE_ATTACK = 1.0
MEDKIT_HEAL = 1.0              # corazones que recupera un botiquín
MEDKIT_SIZE = 24
HURT_INVULN = 1.5              # herido (sin morir): segundos invulnerable parpadeando
KNOCKBACK_SPEED = 220.0        # empujón al ser herido por contacto...
KNOCKBACK_TIME = 0.18          # ...durante este tiempo (sin control horizontal)
RESUME_INVULN = 2.0            # invulnerable al retomar una partida guardada
POINTS_BUBBLE = 10
POINTS_ENEMY = 100
POINTS_LEVEL = 500
POINTS_COIN = 100
COIN_SIZE = 18
POPUP_TIME = 0.8              # "+100" flotando al coger una moneda

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
ENEMY_ANGRY = (255, 60, 60)
ENEMY_BLUE_ANGRY = (40, 90, 255)


def enemy_color(kind, angry=False):
    """Color de un enemigo según su tipo ("tongue" rojo, "laser" azul) y si está enfadado."""
    if kind == "laser":
        return ENEMY_BLUE_ANGRY if angry else ENEMY_BLUE
    return ENEMY_ANGRY if angry else ENEMY
TONGUE = (255, 120, 170)
LASER = (255, 40, 40)
BUBBLE = (150, 210, 255)
WHITE = (240, 240, 250)
BLACK = (0, 0, 0)
BUTTON = (50, 60, 120)
STAR_YELLOW = (255, 215, 40)
STAR_BLUE = (60, 140, 255)
PANEL = (28, 32, 70)
BRICK = (172, 78, 56)
BRICK_DARK = (130, 55, 40)
MORTAR = (178, 170, 156)
HEART = (235, 60, 80)
HEART_EMPTY = (150, 110, 125)
MEDKIT_WHITE = (250, 250, 252)
MEDKIT_EDGE = (170, 175, 190)
MEDKIT_CROSS = (225, 35, 45)
GOLD = (255, 200, 40)
GOLD_DARK = (200, 140, 20)
GOLD_SHINE = (255, 245, 180)
DIFFICULTY_COLORS = {"easy": (110, 210, 130), "normal": (255, 215, 40), "hard": (240, 90, 90)}
