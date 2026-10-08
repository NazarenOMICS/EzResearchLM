# Contratos y estados ejecutables de EZ

Versión de esquema: `2.0`. Los esquemas JSON incluidos en `packages/ez/schemas/`
validan contratos, revisiones QA, manifiestos de fuentes y estados de corrida.
Una versión futura desconocida del contrato o journal se rechaza sin migrarla.

## Artefactos y autoridad

| Artefacto | Función | Regla de escritura |
|---|---|---|
| `research-contract.json` | Pregunta, contexto congelado, alcances, búsquedas, QA, políticas y presupuesto | Revisiones explícitas, con padre y hash |
| `contracts/<revision>.json` | Historial de contratos | Conservado por transacciones |
| `events.jsonl` | Decisiones, resultados externos y transacciones | Secuencia con hashes encadenados, un escritor |
| `run-state.json` | Proyección del último estado confirmado | Reconstruible desde el journal |
| `sources.json` | Identidad, versión, procedencia, hash del PDF e ID remoto | Su hash pertenece al estado |
| `acquisition/<source>/attempts.json` | Intentos, códigos, tiempos, URLs saneadas y resultados | Guardado durante la adquisición |
| `qa/manifest.json` | Pregunta, alcance, corpus y hash de cada respuesta | Confirmado en journal |
| `qa/*.json` | Respuestas originales y referencias de NotebookLM | Verificadas por hash antes de revisar |
| `reviews/<hash>.json` | Cobertura y afirmaciones propuestas por el anfitrión | Revisión conservada con actor |
| `verification/*.json` | QA de respaldo de las afirmaciones propuestas | Recibos por hash de afirmación/contrato/corpus |
| `citation-resolution/*.json` | QA original, texto indexado de NotebookLM y cotejo literal | Recibos en el estado; original conservado |
| `answer.json` | Afirmaciones habilitadas, referencias, cobertura y límites | Derivado de la revisión y QA de respaldo |

Las transacciones registran documentos y estado antes de proyectarlos. Si un corte
deja un archivo en su versión anterior, `continue` puede completar esa transacción.
Si el archivo contiene otro cambio, la recuperación lo conserva y declara un error
de integridad. Los fragmentos finales de eventos interrumpidos se preservan para
diagnóstico antes de continuar el journal. La cadena detecta modificaciones
accidentales; no es una firma digital contra quien controla toda la carpeta.

## Políticas y suficiencia

| Política | Efecto de una fuente faltante |
|---|---|
| `hard_block` | Retiene las conclusiones de sus subpreguntas |
| `soft_block` | Mantiene la obligación visible; permite otras conclusiones respaldadas |
| `contextual` | Requiere resolver su política efectiva antes de habilitar su alcance |
| `historical` | Mantiene contexto histórico, sin bloquear automáticamente |
| `optional` | Su ausencia no bloquea por sí sola |

Cada política declara `source_id`, `scope_ids`, `rationale` y `locked_by_user`.
Modificar una obligación fijada por el usuario exige una autorización explícita.
El puntaje QMD, la disponibilidad OA y el número de archivos no prueban suficiencia.

Una fuente PMC puede especificar `pmc_version` como entero positivo. Sin selección
explícita, la existencia de varias versiones exige revisión antes de usar el PDF.
Cambiar esa selección tras el descubrimiento requiere una corrida nueva. Se
conservan licencia, tipo de versión, metadatos y checksum del servicio Cloud; los
paquetes históricos siguen siendo legibles, pero no se invoca el servicio OA retirado.

`execution.status` expresa ejecución, espera, cancelación o fallo.
`answer.status` expresa respuesta `complete`, `partial` o `unavailable` respecto al
alcance acordado. `integrity.status` separa trazabilidad `pending`, `unknown`,
`pass`, `warn` o `fail`. `pass` no significa validez científica universal.

Señales compatibles: `NEEDS_CORPUS` para falta de corpus utilizable;
`NEEDS_SOURCE_RESCUE` para fuentes pendientes; `NEEDS_SOURCE_REVIEW` para identidad
o política pendiente; `NEEDS_MORE_QA` para cobertura insuficiente en alcances que
ninguna política retiene; `NEEDS_QA_REVIEW` cuando EZ espera la revisión del
anfitrión; `review_invalid` y `review_outdated` cuando la revisión enviada no se puede
usar tal como está; `quota_exhausted` cuando NotebookLM alcanzó el límite de la cuenta;
`NEEDS_TRACEABILITY_REPAIR` para integridad no verificable. Pueden coexistir con una
respuesta parcial. Un fallo de integridad impide entregar afirmaciones afectadas.

`research --require-complete` o `continue --require-complete` conserva una opción
de automatización en la corrida: una entrega parcial sigue disponible y citada,
pero devuelve código 2. Continuaciones posteriores heredan esa opción. Sin ella,
una respuesta parcial válida devuelve 0; esto no convierte la cobertura en completa.

## Revisión y entrega

`plan.delivery` define cómo se entrega. Con `direct` (por defecto en contratos nuevos)
EZ no espera revisión: al terminar la QA convierte cada oración de NotebookLM que tenga
al menos una cita con pasaje en una afirmación con esos pasajes nativos (protocolo
`ez-direct-v1`). No hay segunda consulta. Las oraciones sin cita quedan en
`uncited_statements` y no son evidencia. Las abreviaturas de especie (*C. glutamicum*),
*et al.* y similares no cortan oraciones. Un contrato sin el campo se trata como
`verified`. En una corrida directa, una revisión enviada después activa la entrega
verificada y la reemplaza; `ez continue --verify [IDS]` arma esa revisión con las 10
afirmaciones respaldadas por más fuentes o con las indicadas, y guarda la entrega
directa en `direct/`. Las oraciones casi idénticas entre respuestas (Jaccard de
palabras ≥ 0,8) se unen en la primera, con la unión de alcances y pasajes.

En modo `verified`, el anfitrión presenta `qa-review.json` con hashes del contrato y corpus, revisor,
cobertura por subpregunta y afirmaciones con IDs de preguntas y números de cita.
Cada cita debe aparecer en la respuesta original de NotebookLM, referir a una
fuente verificada y conservar un pasaje citado. El adaptador exige otra QA de
NotebookLM sobre el respaldo completo de cada afirmación (protocolo
`ez-verdict-v5-grounded`). La pregunta lleva solo las afirmaciones, en lotes de hasta
seis y de no más de 4.000 caracteres; un lote rechazado por tamaño se divide. El
dictamen `supported` se acepta si sus citas nativas apuntan a fuentes verificadas del
corpus (no solo a las que citó la QA),
o, cuando NotebookLM no devuelve citas ni preguntando por la afirmación sola, si su
cita textual aparece literal en el texto indexado de una de esas fuentes. Una respuesta
de formato no reconocido, vacía o sin respaldo comprobable no cuenta como aprobación y
retiene solo la afirmación afectada: las demás de su subpregunta se entregan y la
subpregunta figura en `answer.partial_scope_ids`. Solo las políticas de fuente
(`hard_block` ausente o revisión de política pendiente) retienen subpreguntas enteras.
Errores mecánicos de la revisión se corrigen y quedan en `review_adjustments`: una
subpregunta ajena a la pregunta QA se recorta a las de esa pregunta, los números de cita
sin pasaje se descartan si queda al menos uno y un alcance `sufficient` sin afirmaciones
pasa a `insufficient`.

El protocolo v3 (septiembre de 2026) pegaba los pasajes propuestos en la pregunta; en
las corridas reales del 2026-10-07 NotebookLM respondió sin citas nativas y no se
entregó ninguna afirmación. Por eso v5 vuelve a la pregunta sin pasajes, el formato con
el que se entregaron afirmaciones en la primera prueba real.

Antes de adquirir, el anfitrión decide cada candidato en una copia de
`screening-request.json` (`include`, `exclude` o `uncertain`, con razón) y la importa
con `ez continue --screening`. El cribado debe corresponder al `sources_hash` vigente
y no puede superar `budgets.max_sources` (40 por defecto). Una fuente ya subida a
NotebookLM no se excluye en la misma corrida. Las fuentes obligatorias del contrato
entran incluidas.

`answer.json` (esquema 2.1) agrega a cada referencia el objeto `source` con título,
autores, año, DOI/PMID/PMCID, hash y ruta del PDF y origen. También registra
`withheld_claims` (afirmaciones retenidas y su motivo), `skipped_questions`
(preguntas QA no consultadas por una política) y `corpus_exclusions` (fuentes que
quedaron fuera del corpus) y `gaps`, que explica por cada alcance sin respuesta si
falta acceso a una fuente, falló su descarga, espera identidad, no pasó la
verificación o el corpus no alcanza. Una afirmación puede llevar `warnings`
(`numbers_not_in_passages`: un número que no aparece en sus pasajes) y `human_check`
(el juicio registrado con `ez verify`; `unsupported` la retira con motivo
`human_rejected`). Una corrida creada con `ez research --update` agrega `changes`:
afirmaciones nuevas, mantenidas y que ya no se sostienen respecto de la anterior, y
las fuentes nuevas. Las respuestas de protocolos anteriores se muestran como
pendientes de una nueva verificación.

Los marcadores individuales, agrupados y por rango (`[1]`, `[1, 2]`, `[3–5]`)
conservan todos sus números. El anfitrión puede descartar material incompleto del
borrador QA y seleccionar afirmaciones cuyas citas sí tengan pasaje; no se entrega
el borrador entero por esa selección. Citas de fuentes ajenas o numeración ambigua
siguen bloqueando la revisión. El dictamen adicional usa el protocolo de texto
`EZ_VERDICT` / `EZ_RATIONALE` con citas nativas: el servicio puede omitir referencias
en bloques JSON. El lector conserva compatibilidad con dictámenes JSON anteriores
solo si incluyen referencias verificables. La versión del protocolo entra en la
clave de caché para no reutilizar una comprobación incompatible.

Un ancla sin pasaje puede resolverse solamente si la propia respuesta contiene una
cita textual seguida del marcador y esa cita aparece una sola vez en el texto
indexado de la misma fuente, obtenido de NotebookLM con deadline. El cotejo solo
normaliza Unicode y espacios; no usa coincidencias aproximadas, texto local del
PDF ni conocimiento del agente. Guarda el original, el snapshot y la respuesta
derivada. La posición normalizada queda en `resolution`; los offsets originales
siguen describiendo el ancla original, no deben interpretarse como el nuevo pasaje.
Sin coincidencia única la cita sigue sin resolverse y no habilita entrega.

El resultado conserva los dictámenes y sus explicaciones. La revisión humana
independiente de afirmaciones centrales sigue siendo un requisito de beta/release.
`release_validation: false` impide confundir un reporte de investigación con una
certificación del producto.

## Contexto y reutilización

`ez context` conserva revisiones de preferencias por proyecto y muestra enlaces a
corridas con contratos verificables. Cada investigación congela su contexto para
que cambios posteriores no reescriban decisiones históricas.

`ez research --reuse <corrida>` copia únicamente PDFs válidos con identidad
verificada, conserva procedencia y hashes, y registra el origen en `reused_from`.
Los IDs remotos anteriores se conservan como antecedentes, pero no habilitan QA
del notebook nuevo. Se crea y verifica un corpus independiente. El modo `reuse_only` omite descubrimiento
solamente cuando existe esa copia verificada; no declara suficiente el corpus.

## Límites externos

El ejecutor usa deadlines, captura acotada y cancelación de descendientes. En
Windows asigna el proceso a un Job Object antes de permitirle lanzar el comando;
en POSIX utiliza una sesión de procesos. Los procesos descendientes propios se
cierran también al terminar normalmente el padre.

EZ aplica un presupuesto de tiempo activo por corrida y por fuente. Los workers de
búsqueda, descarga y NotebookLM reciben el tiempo restante; las esperas del usuario
entre continuaciones no consumen tiempo activo. La limpieza de procesos puede
añadir unos segundos al vencimiento. QMD tiene un límite independiente y es opcional.
El login interactivo pertenece al usuario; sus verificaciones de acceso son acotadas.

## Migración y rollback

`doctor --migration-preview` captura hashes de los metadatos legacy. Aplicar ese
hash crea una corrida lateral; los originales y PDFs conservan su ubicación.
El contrato nuevo empieza pendiente de planificación, las identidades quedan para
revisión y los IDs remotos se conservan sin considerarlos prueba de identidad.
Un corpus remoto desconocido se detiene antes de subir nuevos archivos.

El flag legacy anterior a v2 siempre bloqueaba, incluso si guardaba `false`:
ese gate efectivo se conserva. La versión corregida hereda su bool real. Una
fuente histórica de Anna conserva su procedencia, pero EZ no vuelve a usar esa vía. Rutas relativas ambiguas
no se adivinan. Para volver al flujo anterior, usar los originales con los wrappers
compatibles; no convertir la corrida nueva sobrescribiendo los archivos anteriores.
