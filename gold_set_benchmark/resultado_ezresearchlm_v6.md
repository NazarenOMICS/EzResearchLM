# Benchmark en vivo de EZresearchLM v6

## Identificación y preparación

- Fecha: 2026-10-08, zona horaria America/Montevideo.
- Rama: `claude/laughing-noether-fcf794`.
- Commit evaluado: `5239a6390554ba64ee1bed6e31bf72ddb7358f76`.
- Pregunta M2: “¿Qué proteínas y procesos de *Corynebacterium glutamicum* se sabe que son afectados por el etambutol, y qué se desconoce sobre su efecto proteómico global?”
- Corrida v5 usada con `--update`: `ez-095891d2214d46aa`.
- Corrida v6 principal: `ez-5e4e9ae130664ff7`.
- Tipo de misión heredado: `academic`.
- El contrato se importó desde una propuesta separada con `plan.delivery = "direct"`.
- No se usaron Anna's Archive ni Sci-Hub. No se leyeron valores de cookies o tokens ni archivos `.env`.

La rama se actualizó mediante avance directo. La instalación editable con el extra `notebooklm` terminó correctamente e instaló `notebooklm-py==0.8.0`. El entorno necesitó además el extra de navegador de ese cliente para abrir el login. Después del acceso, `ez setup --check --json` informó `can_notebook_qa: true`.

## Validación local

`python scripts/validate.py` terminó con código 0. Pasaron los bloques de 17, 4 y 133 pruebas; el último omitió una prueba. El bloque intermedio emitió la advertencia esperada de preservación ante un fallo simulado del auditor de citas. El auxiliar de benchmark informó dos casos controlados `deadline_exceeded`, pero el conjunto que los ejercita terminó `OK`.

## Canary de NotebookLM

El primer intento usó el notebook registrado en la corrida v5, `a783355e-c24d-49bf-b1e2-0bc83c790df4`. NotebookLM devolvió `not found` porque ese notebook había sido borrado por el usuario. Ese intento no evaluó el comportamiento del código y no se considera un fallo del canary.

Después de refrescar el acceso, el canary se repitió sobre el notebook compartido creado por v6, `7cdf38fa-e33d-4e28-85b7-68a674311408`. Consumió dos consultas y terminó con `passed: true`.

| Check | Resultado | Detalle |
|---|---|---|
| `list_notebooks` | pasó | 84 notebooks |
| `list_sources` | pasó | 14 fuentes listas |
| `source_fulltext` | pasó | 88.716 caracteres |
| `qa_native_citations` | pasó | 9 citas con pasaje |
| `fresh_conversation` | pasó | `is_follow_up=False` |
| `verdict_format` | pasó | Dictamen `supported` |
| `verdict_native_citations` | pasó | Citas nativas presentes |

El canary certificó `fresh_conversation`. De manera consistente, las cinco respuestas QA y los dos lotes de verificación de la corrida principal guardaron `is_follow_up: false` y `turn_number: 1`.

## Incidencia de recuperación del notebook compartido

La primera actualización v6, `ez-373e56864af24023`, no pudo reutilizar el notebook v5 porque había sido borrado. EZ creó el notebook de proyecto `7cdf38fa-e33d-4e28-85b7-68a674311408`, lo marcó `notebook_shared: true` y subió los 14 PDFs verificados. Trece quedaron listos y el PDF de Meyer et al. (2023), DOI `10.1016/j.tcsw.2023.100116`, permaneció en `PREPARING` durante tres ventanas internas y una espera explícita adicional de 600 segundos.

Se eliminó únicamente esa carga remota atascada. La salvaguarda de reconciliación impidió que la misma corrida repitiera la subida sin revisión. No se forzaron hashes ni se alteró el corpus: `ez doctor` volvió a informar `healthy: true` después de restaurar el artefacto local exacto. Se creó entonces la corrida principal desde la misma v5. Esta reutilizó las 13 fuentes listas del notebook de proyecto y subió solo el PDF faltante, que procesó correctamente.

En consecuencia, para la corrida principal `notebook_shared` fue `true`, se reutilizaron 13 identificadores remotos y se subió 1 PDF. La secuencia completa de recuperación realizó 15 subidas remotas: 14 en el intento inicial y 1 en la corrida principal.

## M2 en modo directo

### Resultado

| Campo | Valor |
|---|---:|
| `answer.status` | `complete` |
| Alcances entregados | 5 de 5 |
| Afirmaciones entregadas | 102 |
| Afirmaciones retenidas | 0 |
| `uncited_statements` | 42 |
| PDFs válidos y con identidad verificada | 14 |
| PDFs listos en NotebookLM | 14 |
| `notebook_shared` | `true` |
| PDFs subidos por la corrida principal | 1 |

Las 102 afirmaciones entregadas provinieron de oraciones citadas de las cinco respuestas QA. Los 42 elementos de `uncited_statements` quedaron fuera de las afirmaciones entregadas. No se reproducen aquí sus textos ni los pasajes de respaldo.

### Consultas y llamadas externas

El corte de `ez doctor --metrics --json` inmediatamente después de la entrega directa informó 5 consultas a NotebookLM, 17 llamadas externas y `external_failures: {}`. La integridad local quedó verificada y las 102 afirmaciones entregadas tenían trazabilidad registrada.

### Minutos de reloj por etapa

Los tiempos se calcularon con los campos `at` de `events.jsonl`. Cada etapa termina cuando aparece el primer estado de la etapa siguiente. El total directo va desde `research_requested` hasta el primer estado `done/completed`.

| Etapa | Minutos |
|---|---:|
| Preparación e importación del contrato | 0,43 |
| Descubrimiento | 0,11 |
| Adquisición | 0,00 |
| Subida y reconciliación | 0,43 |
| Espera de procesamiento | 0,35 |
| QA y publicación directa | 5,73 |
| Total directo | 7,05 |

La adquisición fue prácticamente nula porque los 14 PDFs y sus identidades se reutilizaron desde v5. La etapa de subida incluye la reconciliación de las 13 fuentes ya presentes y la única subida nueva.

## Paso a modo verificado sobre la misma corrida

Se completó `review-request.json` con 10 afirmaciones tomadas de las cinco respuestas QA, dos por pregunta. El conjunto cubrió los cinco alcances y combinó mecanismo de pared, división celular, eflujo de glutamato, regulación y la brecha de proteómica global. `ez continue --review ... --check --json` devolvió `valid: true` y no consumió consultas.

### Resultado verificado

| Campo | Valor |
|---|---:|
| Afirmaciones propuestas | 10 |
| Afirmaciones entregadas | 9 |
| Afirmaciones retenidas | 1 |
| `answer.status` | `partial` |
| Alcances completos | `sq2`, `sq3`, `sq5` |
| Alcances parciales | `sq1`, `sq4` |
| `review_adjustments` | 0 |

La única retención fue `m2-v6-c06`, sobre la falta de identificación concluyente del transportador específico del eflujo de glutamato. El motivo final fue `verdict_unsupported`; el dictamen textual también fue `unsupported`. Las otras nueve afirmaciones se entregaron con trazabilidad. El fallo de una afirmación no arrastró a las demás de sus alcances.

Después de la verificación, `ez doctor --metrics --json` informó 7 consultas acumuladas a NotebookLM, 26 llamadas externas, `external_failures: {}`, 9 afirmaciones entregadas y 9 con trazabilidad. El incremento respecto del modo directo fue de 2 consultas, correspondientes a los dos lotes de verificación.

### Minutos del paso verificado

Los límites también se tomaron de `events.jsonl`.

| Etapa | Minutos |
|---|---:|
| Preparación y chequeo de la revisión, brecha entre el primer `done` y la importación | 4,10 |
| Reconciliación previa a `qa_review_submitted` | 0,51 |
| Verificación en NotebookLM y publicación | 2,54 |
| Importación y ejecución verificada | 3,05 |
| Transición completa desde la respuesta directa hasta la verificada | 7,15 |

## Diagnóstico

La corrida principal validó el comportamiento buscado por v6 en tres aspectos. Primero, un notebook de proyecto compartido permitió reutilizar 13 de 14 fuentes remotas y limitar la subida a un PDF. Segundo, el modo directo produjo una respuesta completa con cinco consultas, aunque conservó 42 oraciones no citadas fuera de la entrega. Tercero, la verificación retuvo una sola afirmación y entregó las otras nueve, en lugar de propagar esa insuficiencia a todo el alcance compartido.

El reintento del canary sobre el notebook v6 pasó todos los checks y confirmó `fresh_conversation`; el `not found` anterior se explica por la eliminación del notebook v5 y no constituye un fallo del código. Permanece una limitación operativa distinta: una carga de PDF quedó atascada en `PREPARING` y requirió crear una nueva actualización para que la salvaguarda de reconciliación no fuera eludida. La corrida principal terminó con integridad `pass`, sin fallas externas registradas y con estado verificado `partial`.
