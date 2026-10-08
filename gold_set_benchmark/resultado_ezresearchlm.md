# Resultado de la condición EZresearchLM

Fecha de ejecución: 2026-10-07 / 2026-10-08 (hora local -03).
Repositorio: `EZresearchLM-noether`, rama `claude/laughing-noether-fcf794`.
Operador: agente anfitrión (EZ), siguiendo `AGENTS.md` y `docs/ez-host-operator.md`.
Proyecto EZ: `gold-set-benchmark`.

Las puntuaciones de este archivo quedan pendientes: no hubo afirmaciones
entregadas que puntuar. Versión del gold set: la vigente en esta rama al momento
de la corrida; el gold set no se abrió salvo `reglas_benchmark.md`.

## Resultado principal

**Afirmaciones entregadas: 0.** Se propusieron 25 afirmaciones (15 en M1, 10 en
M2) y EZ retuvo todas. En las dos corridas `answer.json` quedó con
`claims: []`, `answer.status: unavailable` y `release_validation: false`.

El bloqueo no está en el contenido de las afirmaciones ni en el corpus, sino en
el protocolo de respaldo (`ez-verdict-v4-batch`): EZ pide a NotebookLM un
dictamen por afirmación y exige que ese dictamen traiga citas nativas con pasaje.
NotebookLM respondió con el formato esperado (`EZ_VERDICT` / `EZ_RATIONALE`, con
comillas textuales de los pasajes propuestos) pero devolvió `references` vacío en
las cinco consultas de verdicto. Sin cita nativa, EZ no puede cotejar el dictamen
contra la fuente y retiene la afirmación.

Motivos registrados en `withheld_claims`:

| Motivo | M1 | M2 |
|---|---|---|
| `verification_citation_without_passage` | 10 | 10 |
| `verification_without_citations` | 5 | 0 |

Evidencia: los 5 archivos de `verification/` de ambas corridas tienen
`references` de longitud 0 (3 en M1, 2 en M2). Varios dictámenes decían
`supported`. No se modificó el código de EZ para sortear esta condición.

## Corridas

| | M1 | M2 |
|---|---|---|
| Pregunta | principios FAIR para la gestión de datos científicos | proteínas y procesos de *C. glutamicum* afectados por etambutol y vacío proteómico |
| ID de corrida | `ez-defa593878654053` | `ez-01569990fb414ed4` |
| Pseudónimo de métricas | `6f0cc866a0d7a357ca89` | `aac31d542381ca3e794c` |
| Minutos activos | 36,8 (2205,8 s) | 27,1 (1625,8 s) |
| Llamadas externas / fallidas | 107 / 10 | 92 / 1 |
| Preguntas QA a NotebookLM | 7 | 5 |
| Lotes de verdicto | 3 | 2 |
| Fuentes encontradas | 40 | 51 |
| PDFs adquiridos y válidos | 31 | 29 |
| Identidad verificada y en corpus | 11 | 14 |
| Sin PDF (`manual_needed`) | 9 | 22 |
| Excluidas `identity_unconfirmed` | 20 | 15 |
| Excluidas `routes_exhausted` | 9 | 22 |
| Afirmaciones propuestas / entregadas | 15 / 0 | 10 / 0 |
| Cobertura final | 7 alcances insuficientes | 5 alcances insuficientes |
| `local_integrity_verified` | true | true |

Fuentes clave que sí entraron al corpus, con identidad verificada:

- M1: Wilkinson et al. 2016, DOI 10.1038/sdata.2016.18 (publicación que formula los principios).
- M2: Radmacher et al. 2005, DOI 10.1099/mic.0.27804-0 (importada por el usuario);
  Schubert et al. 2017, DOI 10.1128/mbio.02213-16; Meyer et al. 2023, DOI
  10.1016/j.tcsw.2023.100116; Jankute et al. 2018, DOI 10.1016/j.tcsw.2018.06.003.

## M2 con y sin importación (regla 2.3)

- **Con importación:** condición ejecutada. Corpus de 14 fuentes verificadas,
  incluida Radmacher 2005. Afirmaciones entregadas: 0 de 10 propuestas.
- **Sin importación:** no medida. La primera pasada de QA sí corrió sobre un
  corpus previo sin Radmacher (hash `17cef2561e40`, 6 fuentes verificadas, 5
  respuestas QA archivadas en `qa/`), pero no se produjo revisión ni `answer.json`
  para ese corpus. Al cambiar el corpus, EZ archivó su plantilla de revisión
  (`review-request-17cef2561e40.json`) y una revisión contra ese hash sería
  rechazada como `review_outdated`. Medir esta condición exige una corrida nueva.

Dado que la retención ocurre en el protocolo de respaldo y no depende del
contenido del corpus, no hay motivo para esperar un recuento distinto de 0 en la
condición sin importación con el adaptador actual.

## Errores y pausas, con mensaje textual

1. `discovery_failed` (M1, tres veces): "Un proveedor no completó la búsqueda. Se
   conservaron los resultados anteriores." Causa: Semantic Scholar devolvió HTTP
   429 con "No SEMANTIC_SCHOLAR_API_KEY set or it's empty. Using unauthenticated
   access with lower rate limits." Se retiró ese proveedor de los contratos de
   ambas corridas antes de completar el descubrimiento.
2. `notebooklm_failed`: "NotebookLM no completó la operación; la corrida conserva
   su checkpoint." Dos causas distintas:
   - Sesión cerrada a mitad de la subida de fuentes; `ez setup --check` pasó a
     `can_notebook_qa: false` con `notebooklm_failure: auth_or_configuration_required`.
     Se resolvió con login del usuario y las corridas retomaron desde su checkpoint.
   - Consulta de verdicto rechazada por tamaño: "Chat request was rejected by the
     server (status 3). This usually means the request was malformed or too large
     — most often an over-long question past the server-side size limit; shorten it
     and try again." Umbral medido sobre el prompt real: falla por encima de unos
     5800 caracteres y pasa por debajo de unos 5200. Las afirmaciones se acortaron
     y reordenaron hasta que cada lote entró; los lotes finalmente enviados no
     dieron error de tamaño.
3. `waiting_on_processing` (M1): "NotebookLM todavía procesa fuentes. Ejecuta ez
   continue más adelante."
4. `NEEDS_QA_REVIEW`: "El agente anfitrión debe revisar QA y completar una copia
   de review-request.json; luego usar ez continue --review."
5. `NEEDS_MORE_QA` (estado final de ambas): "El corpus todavía no respalda una
   respuesta entregable. Revisa QA y fuentes."
6. `quota_exhausted`: **no ocurrió** en ninguna de las dos corridas.

## Consecuencia para la medición de acuerdo humano

`medicion_acuerdo.csv` y `medicion_acuerdo_para_marcar.csv` no se generaron: sin
afirmaciones entregadas no hay filas que marcar, y por lo tanto no hay acuerdo
humano que calcular para esta condición. El README debe seguir diciendo que la
verificación es automática y no revisada.

## Artefactos de respaldo (fuera del repositorio)

`C:\Users\Administrator\.ezresearch\runs\ez-defa593878654053` y
`...\ez-01569990fb414ed4`: contratos y su historial, `events.jsonl` con hashes
encadenados, `sources.json`, `qa/` con manifiesto y respuestas, `reviews/`,
`verification/` con los recibos de dictamen, y `answer.json`. No se commitean.
