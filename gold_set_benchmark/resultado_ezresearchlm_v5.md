# Validación en vivo de `ez-verdict-v5-grounded`

## Identificación y preparación

- Fecha: 2026-10-08 (America/Montevideo).
- Commit evaluado: `0298ccf5f8a4821a711f6f6d711d45da1e27342c`.
- Rama: `claude/laughing-noether-fcf794`.
- Tipo de misión: `academic` para M1 y M2.
- Se reutilizaron las corridas anteriores mediante `--update`; no se usaron Anna's Archive ni Sci-Hub y no fue necesario rescatar PDFs.
- La instalación editable con el extra `notebooklm` terminó correctamente. El primer `notebooklm login` no pudo iniciar porque faltaba el componente de navegador de Playwright; tras instalar esa dependencia del entorno, el segundo intento detectó una sesión válida y guardó la autenticación. `ez setup --check --json` terminó luego con `can_notebook_qa: true`.

### Validación local

`python scripts/validate.py` terminó con código 0. Pasaron tres bloques de 17, 4 y 121 pruebas. El bloque intermedio emitió la advertencia esperada de preservación ante `citation audit returned 1`; el auxiliar de benchmark mostró dos casos `deadline_exceeded` (`paper` y `control`), pero el bloque que los ejercita terminó `OK`.

## Canary de NotebookLM

Se usó el notebook de la corrida M1 anterior. El canary consumió 2 consultas y terminó con `passed: true`; la falla de citas del dictamen era no crítica.

| Check | `ok` | `detail` |
|---|---:|---|
| `list_notebooks` | sí | 86 notebooks |
| `list_sources` | sí | 11 fuentes listas |
| `source_fulltext` | sí | 63.028 caracteres |
| `qa_native_citations` | sí | 7 citas con pasaje |
| `verdict_format` | sí | dictamen `supported` |
| `verdict_native_citations` | no | `verification_citation_without_passage` |

## M1 — principios FAIR

Pregunta: “¿Qué establecen los principios FAIR para la gestión de datos científicos?”

Corrida v5: `ez-73aa86dd7edb4f92`.

### a. Afirmaciones y estado

| Propuestas | Entregadas | Retenidas | `answer.status` | Alcances entregados |
|---:|---:|---:|---|---|
| 15 | 4 | 11 | `partial` | `sq7` |

### b. Motivos de retención

| `reason` | Conteo |
|---|---:|
| `scope_not_sufficient` | 8 |
| `verification_foreign_source` | 3 |

### c. Referencias de las afirmaciones entregadas

Las 4 afirmaciones entregadas contienen 6 referencias: 5 con rol `qa`, 1 con rol `verification` y 0 con rol `verification_quote`. Hubo 0 referencias con `found_in_fulltext: false` y 0 afirmaciones entregadas con el aviso `numbers_not_in_passages`.

| Afirmación | Referencias | `verification` | `verification_quote` | `found_in_fulltext: false` |
|---|---:|---:|---:|---:|
| `m1-c13` | 2 | 0 | 0 | 0 |
| `m1-c14` | 1 | 0 | 0 | 0 |
| `m1-c15` | 1 | 0 | 0 | 0 |
| `m1-c16` | 2 | 1 | 0 | 0 |

### d. Archivos de `verification/`

Todos los dictámenes enumerados fueron parseables. No se reproducen respuestas ni pasajes.

| Archivo | Lote | `references` | `EZ_VERDICT` parseable | `stated_verdict` por id |
|---|---:|---:|---:|---|
| `1d86555ac1161875323e87986c59eebb18cdd95379f9a6d3602c4d89b15a8037.json` | 6 | 7 | sí | `m1-c01=supported`; `m1-c02=supported`; `m1-c03=supported`; `m1-c04=supported`; `m1-c05=supported`; `m1-c07=supported` |
| `dd367c4d22679afc75c944dc83f969ae3aab2d80228ad2419e6cb39cfddb2418.json` | 6 | 8 | sí | `m1-c08=supported`; `m1-c09=supported`; `m1-c10=supported`; `m1-c11=supported`; `m1-c12=supported`; `m1-c13=supported` |
| `2e47f5a90b4e81483d59664c4d4061384e0833fee01d20f71fd9ab58b6e4f39d.json` | 3 | 3 | sí | `m1-c14=supported`; `m1-c15=supported`; `m1-c16=supported` |

### e. Consultas, errores y pausas

`ez doctor --metrics --json` informó 10 consultas a NotebookLM, 40 llamadas externas y `external_failures: {}`. En `events.jsonl`, todos los eventos `external_result` tuvieron `exit_code: 0`; no aparecieron `quota_exhausted`, `question_too_long` ni fallas de comandos externos.

Durante la preparación de la revisión hubo dos rechazos locales, sin consumo de consultas: el chequeo `ez continue <M1> --review <review> --check --json` devolvió `ReviewError` porque `m1-c02` incluía un alcance no cubierto por su pregunta QA; el intento inmediato de importación `ez continue <M1> --review <review> --json` devolvió `review_invalid`. Se corrigieron los alcances y el chequeo posterior aceptó las 15 afirmaciones.

### f. Resultado de `ez doctor`

`ez doctor <M1> --json` devolvió `healthy: true`, `findings: []`, estado `partial` y alcance `sq7`. Indicó que no había inconsistencias locales y aclaró que eso no acredita por sí solo un E2E ni habilita lanzamiento. Las métricas registraron `execution_status: completed`, 11 PDFs válidos, 11 identidades verificadas y 4 afirmaciones con trazabilidad.

### g. Diagnóstico

M1 no quedó en cero: entregó 4 afirmaciones. Aun así, el evento final `kind: transaction` (secuencia 144) conserva en `payload.documents.answer.json.value.withheld_claims[*].reason` 3 casos `verification_foreign_source` y 8 casos `scope_not_sufficient`; el campo `payload.documents.answer.json.value.answer.status` quedó en `partial`. Esto muestra que el dictamen textual `supported` no bastó cuando la procedencia de la referencia o la suficiencia del alcance falló.

## M2 — etambutol en *Corynebacterium glutamicum*

Pregunta: “¿Qué proteínas y procesos de *Corynebacterium glutamicum* se sabe que son afectados por el etambutol, y qué se desconoce sobre su efecto proteómico global?”

Corrida v5: `ez-095891d2214d46aa`.

### a. Afirmaciones y estado

| Propuestas | Entregadas | Retenidas | `answer.status` | Alcances entregados |
|---:|---:|---:|---|---|
| 14 | 0 | 14 | `unavailable` | ninguno |

### b. Motivos de retención

| `reason` | Conteo |
|---|---:|
| `scope_not_sufficient` | 13 |
| `verification_foreign_source` | 1 |

### c. Referencias de las afirmaciones entregadas

No hubo afirmaciones entregadas. Por lo tanto, los conteos para roles `verification` y `verification_quote`, referencias con `found_in_fulltext: false` y avisos `numbers_not_in_passages` son todos 0.

### d. Archivos de `verification/`

Todos los dictámenes enumerados fueron parseables. No se reproducen respuestas ni pasajes.

| Archivo | Lote | `references` | `EZ_VERDICT` parseable | `stated_verdict` por id |
|---|---:|---:|---:|---|
| `4f1ad7cc427f05d7e7e1066642fbfb31a2c64d013a58bf6538856e841e8f4e45.json` | 6 | 8 | sí | `m2-c01=supported`; `m2-c02=supported`; `m2-c03=supported`; `m2-c04=supported`; `m2-c05=supported`; `m2-c06=supported` |
| `6df6eebdbb345fbc902746253125c73ac16c3f203f33e2ebafb4ec0ea6cb6fd6.json` | 6 | 7 | sí | `m2-c07=supported`; `m2-c08=supported`; `m2-c09=supported`; `m2-c10=supported`; `m2-c11=supported`; `m2-c12=supported` |
| `f63f56026704999f58b6ab10c3e9e043fa0c537d056c69f4d5570e409fca8bc5.json` | 2 | 3 | sí | `m2-c13=supported`; `m2-c14=supported` |

### e. Consultas, errores y pausas

`ez doctor --metrics --json` informó 8 consultas a NotebookLM, 38 llamadas externas y `external_failures: {}`. En `events.jsonl`, todos los eventos `external_result` tuvieron `exit_code: 0`; no aparecieron `quota_exhausted`, `question_too_long` ni fallas de comandos externos.

El primer chequeo local `ez continue <M2> --review <review> --check --json` devolvió `ReviewError` porque `m2-c05` incluía un alcance no cubierto por su pregunta QA. Tras corregir la asociación, el chequeo aceptó las 14 afirmaciones y la importación continuó normalmente.

### f. Resultado de `ez doctor`

`ez doctor <M2> --json` devolvió `healthy: true`, `findings: []`, estado `unavailable` y ningún alcance entregado. Indicó que no había inconsistencias locales y aclaró que eso no acredita por sí solo un E2E ni habilita lanzamiento. Las métricas registraron `execution_status: waiting_user`, 14 PDFs válidos, 14 identidades verificadas y 0 afirmaciones con trazabilidad.

### g. Diagnóstico de las cero entregas

Los tres lotes produjeron 14 `stated_verdict: supported`, pero `m2-c11` terminó `unverified` con `reason: verification_foreign_source`. El evento final `kind: transaction` (secuencia 127) registra en `payload.documents.answer.json.value.withheld_claims[*].reason` 1 caso `verification_foreign_source` y 13 casos `scope_not_sufficient`; `payload.documents.answer.json.value.answer.status` es `unavailable`. Dado que todas las afirmaciones propuestas incluían el alcance común `sq1`, la insuficiencia de ese alcance retuvo también las afirmaciones cuyo dictamen individual había sido `supported`.

## Observación del login

Fue necesario ejecutar `notebooklm login`. El intento exitoso detectó la sesión existente y terminó sin pedir Enter ni ninguna otra entrada en la terminal después del flujo de navegador.

## Conclusión

Hecho: el canary pasó, aunque la cita nativa del dictamen falló en el control no crítico.
Hecho: v5 entregó 4 de 15 afirmaciones en M1 y 0 de 14 en M2, sin fallas externas ni agotamiento de cuota.
Inferencia: el protocolo sí separa el `stated_verdict` de la evidencia entregable y bloquea referencias de procedencia ajena.
Inferencia: la propagación de `scope_not_sufficient` desde un alcance común puede ser demasiado amplia para misiones donde una sola afirmación contaminada comparte ese alcance con todas las demás.
