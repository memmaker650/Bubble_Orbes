"""Constantes del juego. Todo en coordenadas lógicas (se escala a la ventana)."""

# --- Pantalla lógica (relación ~ iPhone en vertical) ---
TILE = 40
COLS = 9
ROWS = 16
FIELD_W = COLS * TILE          # 360
FIELD_H = ROWS * TILE          # 640  -> zona de juego
LOGICAL_W = FIELD_W
LOGICAL_H = FIELD_H + 120      # + barra de controles táctiles
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

# --- Burbujas ---
BUBBLE_SIZE = 28
BUBBLE_SPEED = 300.0
BUBBLE_SHOT_TIME = 0.4
BUBBLE_RISE = 55.0
BUBBLE_EMPTY_LIFE = 5.0
BUBBLE_ENEMY_LIFE = 7.0
BUBBLE_ARM_TIME = 0.25         # tiempo antes de poder reventarla
SHOOT_COOLDOWN = 0.3

# --- Reglas ---
START_LIVES = 3
INVULN_TIME = 2.0
POINTS_BUBBLE = 10
POINTS_ENEMY = 100
POINTS_LEVEL = 500

# --- Colores ---
BG = (18, 20, 40)
SOLID = (70, 80, 150)
PLATFORM = (120, 140, 230)
PLAYER = (80, 220, 140)
ENEMY = (235, 90, 90)
BUBBLE = (150, 210, 255)
WHITE = (240, 240, 250)
BLACK = (0, 0, 0)
BUTTON = (50, 60, 120)
