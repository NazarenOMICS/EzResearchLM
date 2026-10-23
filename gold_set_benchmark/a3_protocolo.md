# Protocolo de A3: EZ frente a ChatGPT con búsqueda y NotebookLM manual

Compara tres sistemas sobre las misiones M1 a M3 de `misiones.csv`, con las reglas de
`reglas_benchmark.md`. La puerta de la hoja de ruta es una planilla con referencias inventadas,
precisión y tiempo por sistema. Si EZ no supera a las alternativas en referencias inventadas y
precisión, el producto se revisa antes de distribuirlo.

Todo el material de trabajo va en `gold_set_benchmark/a3/`, que git ignora. Solo se commitea el
informe final, que tiene conteos y no textos.

## 0. Antes de correr cualquier sistema

1. **Validar el gold set.** Revisá cada ítem de `validacion.md` contra el PDF original y marcá
   su casilla. Lo que no se sostenga se corrige ahora, como versión nueva en `CAMBIOS.md`.
2. **Congelarlo.** Commiteá la validación y anotá en `CAMBIOS.md` la fecha y el hash de ese
   commit (regla 1.2). Desde ahí, las reglas y el gold set no cambian hasta terminar A3.
3. **Decidir cuántas afirmaciones se puntúan.** La regla 3.1 dice «cada afirmación». EZ entrega
   unas 100 en M2, así que puntuar todas lleva horas. Si preferís puntuar una muestra (por
   ejemplo 20 al azar por respuesta, con `--maximo 20`), agregalo a `reglas_benchmark.md`
   **antes** del paso 1 y usá el mismo número en todos los sistemas.
4. Anotá el hash de `main` con que corre EZ y el modelo de ChatGPT que uses.

## 1. El mismo pedido para todos

El texto que se envía es igual en los tres sistemas. Se arma con la pregunta y las
subpreguntas de `misiones.csv`:

```text
<pregunta>

<subpreguntas, una por línea, si la misión las tiene>

Respondé con afirmaciones concretas. Para cada una, citá su fuente (autores, año y DOI).
Si algo no se sabe o no está en la literatura, decilo explícitamente.
```

En EZ, la pregunta va como pregunta de investigación y las subpreguntas como QA del plan.

## 2. Correr los sistemas

Primero EZ, porque NotebookLM manual usa los PDFs que reunió EZ (regla 2.4).

**EZ.** Usá un proyecto nuevo por misión y una corrida desde cero, operada como la operaría
una persona. Cronometrá desde el pedido hasta la entrega directa, incluidas tus intervenciones.
Para M2 hacé dos corridas (regla 2.3): una con el PDF de Radmacher 2005 importado con
`ez rescue` (anotá cuándo y con qué identidad), y otra en otro proyecto, sin importar nada.

**ChatGPT con búsqueda.** Usá un chat temporal (sin memoria ni personalización), con la
búsqueda activada y sin adjuntos. Pegá el pedido y copiá la respuesta con su botón de copiar,
que conserva los enlaces, a `a3/respuestas/chatgpt_<mision>.md`. No repreguntes.

**NotebookLM manual.** Usá un notebook nuevo por misión, con los mismos PDFs que terminaron en
el corpus de EZ para esa misión (en M2, los de la corrida con importación). Pegá el pedido y
copiá la respuesta a `a3/respuestas/notebooklm_<mision>.md`. Los números de cita se pierden al
copiar: pasá el cursor por cada uno y agregá al final del archivo una lista así:

```text
## Fuentes
[1] nombre del PDF o DOI
[2] …
```

Esto lo hacés vos en la web de NotebookLM. El agente que opera EZ no la usa (regla 7 de
`AGENTS.md`).

**Registro.** Por cada respuesta, una fila en `a3/registro.csv`:

```text
sistema,mision,minutos,lagunas_declaradas,lagunas_esperadas,corrida_ez,notas
```

`sistema` es `ez`, `ez-sin-pdf`, `chatgpt` o `notebooklm`. `lagunas_esperadas` sale de
`lagunas_esperadas.csv` (1 en M1, 4 en M2 y 1 en M3). En `lagunas_declaradas` va cuántas de esas
dice la respuesta. Lo cuenta quien evalúa, mirando la respuesta, no la planilla ciega.

## 3. Armar la planilla ciega

```powershell
python gold_set_benchmark/a3.py preparar --ez M1=<corrida> --ez M2=<corrida> --ez M3=<corrida> --ez-sin-pdf M2=<corrida> --comprobar-dois
```

Esto corta cada respuesta en oraciones, les quita marcadores, enlaces y encabezados, y las
mezcla al azar con una semilla fija en `a3/planilla_ciega.csv`. Qué sistema dio cada una queda
en `a3/clave.csv`. `--comprobar-dois` consulta doi.org y marca `doi_existe` (`si`, `no`,
`sin_doi` o `sin_comprobar`).

## 4. Puntuar

Esperá al menos un día desde que leíste las respuestas. Abrí solo `planilla_ciega.csv`, sin
`clave.csv` ni `respuestas/`, y completá:

1. `puntaje`: 0 sin fuente o con fuente inexistente; 1 fuente real que no la respalda; 2
   respaldo parcial o exagerado; 3 respaldo completo y alcance correcto. Usá `-` en una fila que
   no es una afirmación (un saludo, una oración que el corte partió mal).
2. `fuente_existe`: `no` si una fuente sin DOI no existe (título o URL inventados).
3. `prohibida`: el id de `afirmaciones_prohibidas.csv` si la fila la afirma.

## 5. Repuntaje y resultado

Una semana después, sin mirar los puntajes anteriores (regla 3.3):

```powershell
python gold_set_benchmark/a3.py repuntaje
```

Completá `a3/planilla_repuntaje.csv` y luego generá el informe:

```powershell
python gold_set_benchmark/a3.py resultados --salida gold_set_benchmark/resultado_a3.md
```

Si la coincidencia del repuntaje es menor al 80 %, el informe lo avisa: hay que precisar la
rúbrica antes de seguir. El informe se commitea junto con la versión del gold set, el hash de EZ
y el modelo de ChatGPT, y sus números pasan al README (C3).

## Límites conocidos

1. Si la misma persona recoge las respuestas y las puntúa, la evaluación no es del todo ciega:
   el estilo delata al sistema. La espera del paso 4 lo atenúa, y una segunda persona lo
   resuelve.
2. El corte por oraciones es aproximado: una afirmación larga puede quedar en dos filas.
   Puntuá cada fila por lo que dice.
