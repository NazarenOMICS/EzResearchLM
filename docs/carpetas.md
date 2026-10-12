# Dónde queda cada cosa

EZ trabaja en una carpeta propia, su base operativa. Por defecto es `~/.ezresearch`
(en Windows, `C:\Users\<tu usuario>\.ezresearch`). Ahí conviven lo que tú usas y lo que
EZ necesita para poder verificar cada resultado.

Tus proyectos (`projects/`) pueden estar en otra carpeta, a la vista: durante la primera
conversación EZ te propone `Documentos\EZresearchLM\projects`, junto a la instalación, y la
guarda con `ez setup --projects-dir`. EZ copia los proyectos existentes, verifica los archivos
y recién entonces actualiza la configuración. La carpeta de origen se conserva para recuperación;
ante una colisión o un fallo, el origen y la ruta configurada quedan intactos. El registro de
trabajo (`runs/`) queda por defecto en `.ezresearch`; `--root` o `EZRESEARCH_RUNS_ROOT` pueden
elegir otra raíz. `install.json` le dice a tu agente dónde está instalado EZ cuando vuelves en un
chat nuevo.

```
.ezresearch/
├── projects/                       ← lo tuyo
│   └── <proyecto>/
│       ├── README.md               índice: cada investigación, su estado y enlaces
│       ├── inbox/                  deja aquí tus PDFs
│       ├── reports/
│       │   ├── 2026-10-08-<pregunta>-<id>.md    el informe de evidencia
│       │   └── 2026-10-08-<pregunta>-<id>.bib   su bibliografía para Zotero
│       └── notes/                  vault de Obsidian: pasajes por fuente y afirmaciones por investigación
├── runs/                           ← registro de trabajo de EZ, no editar
│   └── ez-<id>/                    una carpeta por investigación
├── contexts/                       preferencias de cada proyecto
└── ez-config.json                  configuración (por ejemplo, el correo para Unpaywall)
```

## Lo que usas tú

1. **`projects/<proyecto>/README.md`.** Es la puerta de entrada. Lista las investigaciones
   del proyecto con fecha, pregunta y estado, con enlaces al informe y a su carpeta de
   trabajo. EZ lo regenera en cada entrega.
2. **`inbox/` (bandeja).** Cuando EZ te pide un artículo que no pudo descargar, guárdalo aquí y
   dile que siga. EZ reconoce cada PDF por su título y su DOI, y lo incorpora a la
   investigación que lo necesita. Si no puede confirmar que el PDF corresponde al
   artículo, te lo pregunta. Tus archivos no se mueven ni se borran: EZ guarda una copia.
3. **`reports/` (informes).** Una copia de cada informe, con nombre por fecha y pregunta, y su
   bibliografía en BibTeX. Puedes moverlos, compartirlos o editarlos sin afectar nada.
4. **`notes/` (notas).** La memoria del proyecto, lista para abrir como vault de Obsidian.
   `sources/` tiene una nota por artículo con todos los pasajes que NotebookLM citó de él,
   su página y las afirmaciones que respaldan; `researches/` tiene una nota por
   investigación con sus afirmaciones enlazadas a los artículos. EZ la reescribe en cada
   entrega a partir de las investigaciones verificables, así que no conviene editarla.
   `ez recall` recupera afirmaciones y pasajes guardados sin volver a consultar NotebookLM; la
   coincidencia léxica no determina si responden la pregunta. Un marcador apunta a un registro,
   la localización literal del pasaje y la verificación de una afirmación son estados distintos.

## Lo que usa EZ

`runs/ez-<id>/` guarda todo lo necesario para comprobar una investigación: contrato,
fuentes con su hash, respuestas de NotebookLM, el registro encadenado `events.jsonl`,
`answer.json` y el `report.md` original. No lo edites: `ez doctor` detecta cualquier
cambio. Si necesitas algo de ahí, la copia en `reports/` es tuya.

## Proyectos y reutilización

Cada pregunta pertenece a un proyecto. Cuando haces una pregunta nueva, EZ te dice si se
parece a uno de tus proyectos y te pregunta si la suma ahí o abre uno nuevo. Dentro de un
proyecto, los artículos ya verificados en investigaciones anteriores se reutilizan sin
volver a descargarlos, y todas las investigaciones usan el mismo notebook de NotebookLM
mientras entren sus 50 fuentes. Si una creación se interrumpió, EZ adopta el único notebook con
el título de esa corrida y lo registra como compartido; la siguiente corrida lo reutiliza.

## PDFs de otras carpetas

Si ya tienes tus PDFs en otro lugar (tu biblioteca, Zotero, Descargas), pídele a EZ que
los tome de esa carpeta: «usa los PDFs de <carpeta>». EZ solo lee carpetas fuera de su
base cuando se lo pides así, y no las modifica.
