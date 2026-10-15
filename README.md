# Orbes

Juego de plataformas arcade en una sola pantalla, en la línea de *Bubble Bobble*: lanzas orbes
para atrapar enemigos, y los revientas tocándolos antes de que escapen (más rápidos y enfadados).
Python + **pygame-ce**, **sqlite3** para puntuaciones/ajustes/progreso y **Briefcase** para empaquetar
(macOS e iOS).

## Controles

| Acción        | Teclado (macOS)          | Táctil (iOS)         |
|---------------|--------------------------|----------------------|
| Mover         | ← → / A D                | botones ◀ ▶          |
| Saltar        | ↑ / W / Espacio          | botón ▲              |
| Lanzar orbe   | Z / X / Shift izq.       | botón ○              |
| Menú / volver | Enter / Esc              | tocar                |

Los saltos atraviesan las plataformas desde abajo. Si dejas un orbe con enemigo demasiado tiempo,
el enemigo se libera enfadado.

## Estructura

```
pyproject.toml          Configuración de Briefcase y pytest
src/orbes/
  settings.py           Constantes (pantalla lógica 360x760, física, reglas, colores)
  levels.py             Niveles como mapas de texto (# sólido, = plataforma, P jugador, E enemigo)
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
prueba sin ventana. Para añadir niveles basta con añadir un mapa a `LEVELS` en `levels.py`.

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install briefcase pygame-ce platformdirs pytest

pytest                  # tests (usan el driver de vídeo "dummy", no abren ventana)
briefcase dev           # ejecutar el juego en el escritorio
```

La base de datos se guarda en la carpeta de datos de usuario (`platformdirs`): en macOS
`~/Library/Application Support/Orbes/orbes.db`; en iOS, dentro del sandbox de la app.

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
nombre en `LICENSE`. Los iconos van en `src/orbes/resources/` (`icon.icns` para macOS y
`icon-<tamaño>.png` para iOS); sin ellos Briefcase usa uno por defecto y avisa.

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
