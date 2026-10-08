# Dónde queda cada cosa

EZ trabaja en una carpeta propia, su base operativa. Por defecto es `~/.ezresearch`
(en Windows, `C:\Users\<tu usuario>\.ezresearch`). Ahí conviven lo que tú usas y lo que
EZ necesita para poder verificar cada resultado.

```
.ezresearch/
├── proyectos/                      ← lo tuyo
│   └── <proyecto>/
│       ├── LEEME.md                índice: cada investigación, su estado y enlaces
│       ├── bandeja/                deja aquí tus PDFs
│       └── informes/
│           ├── 2026-10-08-<pregunta>-<id>.md    el informe de evidencia
│           └── 2026-10-08-<pregunta>-<id>.bib   su bibliografía para Zotero
├── runs/                           ← registro de trabajo de EZ, no editar
│   └── ez-<id>/                    una carpeta por investigación
├── contexts/                       preferencias de cada proyecto
└── ez-config.json                  configuración (por ejemplo, el correo para Unpaywall)
```

## Lo que usas tú

1. **`proyectos/<proyecto>/LEEME.md`.** Es la puerta de entrada. Lista las investigaciones
   del proyecto con fecha, pregunta y estado, con enlaces al informe y a su carpeta de
   trabajo. EZ lo regenera en cada entrega.
2. **`bandeja/`.** Cuando EZ te pide un artículo que no pudo descargar, guárdalo aquí y
   dile que siga. EZ reconoce cada PDF por su título y su DOI, y lo incorpora a la
   investigación que lo necesita. Si no puede confirmar que el PDF corresponde al
   artículo, te lo pregunta. Tus archivos no se mueven ni se borran: EZ guarda una copia.
3. **`informes/`.** Una copia de cada informe, con nombre por fecha y pregunta, y su
   bibliografía en BibTeX. Puedes moverlos, compartirlos o editarlos sin afectar nada.

## Lo que usa EZ

`runs/ez-<id>/` guarda todo lo necesario para comprobar una investigación: contrato,
fuentes con su hash, respuestas de NotebookLM, el registro encadenado `events.jsonl`,
`answer.json` y el `report.md` original. No lo edites: `ez doctor` detecta cualquier
cambio. Si necesitas algo de ahí, la copia en `informes/` es tuya.

## PDFs de otras carpetas

Si ya tienes tus PDFs en otro lugar (tu biblioteca, Zotero, Descargas), pídele a EZ que
los tome de esa carpeta: «usa los PDFs de <carpeta>». EZ solo lee carpetas fuera de su
base cuando se lo pides así, y no las modifica.
