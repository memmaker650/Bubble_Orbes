# BubbleQuest

Juego de plataformas arcade en una sola pantalla, en la línea de *Bubble Bobble*: lanzas orbes
para atrapar enemigos, y los revientas tocándolos antes de que escapen (más rápidos y enfadados).
Python + **pygame-ce**, **sqlite3** para puntuaciones/ajustes/progreso y **Briefcase** para empaquetar
(macOS e iOS).

## Controles

| Acción        | Teclado (macOS)          | Táctil (iOS)         |
|---------------|--------------------------|----------------------|
| Mover         | ← → / A D                | botones ◀ ▶          |
| Saltar        | ↑ / W / Espacio          | botón ▲              |
| Bajar de una plataforma | ↓ / S          | botón ▼              |
| Lanzar orbe   | Z / X / Shift izq.       | botón ○              |
| Menú / volver | Enter / Esc              | tocar                |

Una pulsación de salto sube media altura; una segunda pulsación en el aire completa el salto (hace
falta para subir de una plataforma a la siguiente). Los saltos atraviesan las plataformas finas
desde abajo y la flecha abajo las atraviesa hacia abajo. Si dejas un orbe con enemigo demasiado
tiempo, el enemigo se libera enfadado.

## Estructura

```
pyproject.toml          Configuración de Briefcase y pytest
src/bubblequest/
  settings.py           Constantes (pantalla lógica 360x760, física, reglas, colores)
  levels.py             Carga y valida los niveles JSON (ver "Niveles")
  level_generator.py    Generador de niveles (plantillas, niveles procedurales 5-20)
  resources/levels/     Un JSON por nivel
  entities.py           Body (física), Player, Enemy, Bubble — lógica pura
  world.py              Reglas: disparo, captura, puntos, vidas, victoria/derrota — sin dibujo
  db.py                 sqlite3: puntuaciones, ajustes, nivel desbloqueado (migraciones con user_version)
  display.py            Superficie lógica escalada a la ventana + conversión de coordenadas
  controls.py           Teclado + táctil multitoque + botones en pantalla
  scenes.py             Menú, juego, puntuaciones
  app.py / __main__.py  Bucle principal y punto de entrada de Briefcase
tests/                  pytest (base de datos, mundo/física y arranque headless)
```

La lógica (`entities`, `world`, `levels`, `db`) no dibuja nada y solo usa `pygame.Rect`, así que se
prueba sin ventana. Los niveles son ficheros JSON en `src/bubblequest/resources/levels/` (ver la sección
siguiente).

## Niveles (ficheros JSON)

Cada nivel es un fichero `src/bubblequest/resources/levels/level_NN.json` (se cargan ordenados por
`number`). Se pueden editar a mano; el juego los valida al arrancar y, si hay un error, dice en qué
fichero. `python -m bubblequest.level_generator` crea los que falten **sin sobrescribir** los existentes
(con `--force` los regenera desde el generador y se pierden los retoques a mano).

```json
{
  "number": 5,
  "name": "Nivel 5",
  "tutorial": false,
  "enemies_attack": true,
  "map": ["    S    ", "         ", "  =====  ", "..."]
}
```

| Campo            | Significado                                                              |
|------------------|--------------------------------------------------------------------------|
| `number`         | Número del nivel que ve el jugador (0 = tutorial). No se puede repetir.  |
| `name`           | Nombre informativo.                                                      |
| `tutorial`       | `true` muestra la guía de pasos del tutorial.                            |
| `enemies_attack` | `false` = los enemigos no hacen daño (tutorial).                         |
| `map`            | El mapa, como lista de filas de texto (de arriba abajo).                 |

### Caracteres del mapa

| Carácter | Significado                                                                         |
|:--------:|-------------------------------------------------------------------------------------|
| ` `      | Vacío.                                                                              |
| `#`      | Bloque sólido: no se atraviesa y bloquea ataques y visión.                          |
| `=`      | Plataforma fina: se atraviesa saltando desde abajo y bajando con la flecha abajo.   |
| `L`      | Ladrillo/cemento: sólido que sirve de parapeto (bloquea el paso, la vista de los enemigos, la lengua, el láser y las burbujas). |
| `P`      | Inicio del jugador (uno por nivel, obligatorio).                                    |
| `S`      | Estrella de fin de nivel: con todos los enemigos eliminados, al tocarla se completa. |
| `E`      | Enemigo rojo: ataca sacando la lengua.                                              |
| `A`      | Enemigo azul: ataca con un láser por los ojos.                                      |
| `H`      | Botiquín: recupera un corazón (no se coge con la vida al completo).                 |
| `C`      | Moneda de oro: +100 puntos.                                                         |
| `B`      | Bomba: se enciende al golpearla con una burbuja o pulsando la acción encima; a los 3 s explota y elimina a los enemigos a menos de ~140 px (3,5 casillas). |

Reglas del mapa:

- **9 columnas** por fila y **16 filas o más**. Con más de 16 el nivel es más alto que la pantalla
  y se hace scroll vertical (limitado al alto del mapa).
- Solo se describe el **interior**: los bordes (finos) se añaden solos alrededor.
- Enemigos, botiquines y monedas conviene ponerlos justo **encima de una plataforma** (`=`).
- Un salto completo (doble pulsación) sube unas **3 filas**: las plataformas deben estar como mucho
  a 3 filas unas de otras para poder subir.
- El jugador puede empezar **abajo** (la estrella arriba), **arriba del todo** (la estrella abajo
  del todo) o **a mitad** del nivel (la estrella arriba o abajo). En los niveles 5 a 20 el
  generador rota esas cuatro disposiciones.

### Bombas (`B`)

Una bomba se define poniendo el carácter **`B`** (de *bomba*) en una casilla del `map`, **justo encima de una
plataforma** (`=`), igual que enemigos, botiquines y monedas. No hay ningún campo aparte en el
JSON: al cargar el nivel, cada `B` se convierte en una bomba apagada en esa casilla. Ejemplo real
(`level_13.json`, filas 6 y 7):

```json
"map": [
  "...",
  " H    BEA",
  "===   ===",
  "..."
]
```

- **Se enciende** al golpearla directamente con una burbuja (la burbuja se gasta) o con el
  jugador encima pulsando la acción (en lugar de lanzar una burbuja). Entonces cambia a la
  imagen con la mecha encendida, que se va consumiendo, con una cuenta atrás 3, 2, 1.
- **Explota a los 3 s** (`BOMB_FUSE`) y elimina a todos los enemigos a menos de **~140 px**
  (`BOMB_RADIUS`, unos 2,5 cm en un iPhone, 3,5 casillas) en cualquier dirección, aunque haya
  muros en medio, también a los atrapados en burbujas. Al jugador no le hace daño. Enciende las
  bombas que pille dentro del radio (reacción en cadena). Deja humo gris que se difumina.
- Cada explosión queda registrada en el log (posición, enemigos eliminados y bombas encendidas
  en cadena).
- El generador (`place_bombs` en `level_generator.py`) pone **1 bomba en los niveles 10 a 12**
  (hasta 45 filas) y **2 en los niveles 13 a 20**, donde más enemigos quedan a su alcance, lejos
  del inicio del jugador. En los niveles 1 a 9 no hay bombas, pero se pueden añadir a mano con `B`.
- Ajustes en `settings.py`: `BOMB_FUSE`, `BOMB_RADIUS`, `EXPLOSION_TIME`, `SMOKE_TIME`.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install briefcase pygame-ce platformdirs pytest

pytest                  # tests (usan el driver de vídeo "dummy", no abren ventana)
briefcase dev           # ejecutar el juego en el escritorio
```

La base de datos (`BubbleQuest_database.db`) y los logs (`log/BubbleQuest_AAAAMMDD.log`, se
conservan los 10 últimos) se guardan en la carpeta de datos del juego: en macOS
`~/Library/Application Support/com.SkullWithGasMask/BubbleQuest`; en iOS, la misma ruta dentro del
contenedor privado de la app (ver `paths.py`). La primera vez se copia la base de datos de la
versión anterior (`~/Library/Application Support/Orbes/orbes.db`), que se conserva.

## Empaquetar

```bash
# macOS
briefcase create macOS
briefcase build macOS
briefcase run macOS
briefcase package macOS --adhoc-sign     # o con tu identidad de firma

# iOS (simulador)
briefcase create iOS
briefcase build iOS
briefcase run iOS
```

Antes de publicar, cambia en `pyproject.toml`: `bundle`, `author`, `author_email`, `url` y el
nombre en `LICENSE`.

Los iconos (el personaje con una burbuja saliendo de su boca) se generan con
`python tools/make_icons.py` en `src/bubblequest/resources/`: `icon-<tamaño>.png` (iOS y Linux),
`icon.icns` (macOS), `icon.ico` (Windows), `icon-round-*/icon-square-*` (Android) e `icon.png` /
`icon-macos.png` (icono de la ventana al ejecutar sin empaquetar). Para cambiar el dibujo, edita
el script y vuelve a ejecutarlo.

## Riesgo iOS

**macOS no tiene problema; iOS es el punto débil del stack.** Briefcase en iOS solo instala:

- paquetes Python puros, o
- paquetes con código nativo para los que exista una *wheel* compilada para iOS. PyPI no admite
  wheels de iOS: Briefcase consulta un repositorio secundario mantenido por BeeWare (en anaconda.org)
  que no cubre todos los paquetes ni todas las versiones. Para los que faltan se usa
  [BeeWare Mobile Forge](https://github.com/beeware/mobile-forge), donde se pueden aportar recetas.

`pygame-ce` es una extensión en C que depende de SDL2, así que **necesita una wheel para iOS que
yo no he podido comprobar que exista** (el entorno donde se montó el proyecto no tiene acceso a PyPI
ni a ese repositorio). Lo primero que debes hacer, antes de invertir en el juego:

1. Ejecutar `briefcase create iOS` con este proyecto tal cual. Si el paso `pip install` falla con
   "no matching distribution" o "Cannot compile native modules", la wheel no está disponible.
2. Si falta: compilar `pygame-ce` para iOS con Mobile Forge (requiere SDL2, SDL2_image/mixer/ttf
   compilados para iOS), o buscar una wheel ya construida por la comunidad.
3. Plan B: sustituir solo la capa de dibujo/entrada (`display.py`, `controls.py`, `scenes.py`) por otra
   que sí funcione en iOS. El motor (`world`, `entities`, `levels`, `db`) se reutiliza; solo hay que
   cambiar `pygame.Rect` por una clase `Rect` propia de unas 30 líneas.

Mientras tanto se puede desarrollar y jugar en macOS sin bloqueo.

## Hoja de ruta sugerida

- Sonido (efectos al disparar, reventar, perder vida) y música.
- Poder subirse a los orbes vacíos para llegar a plataformas altas (mecánica clásica).
- Frutas/bonus al reventar enemigos, combos y nivel de "prisa" por tiempo.
- Pantalla para introducir el nombre en las puntuaciones (hoy se usa el ajuste `player_name`).
- Más niveles, tipos de enemigo y jefes; pausa al perder el foco (importante en iOS).
- Iconos y pantalla de arranque.
