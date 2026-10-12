# Entrega, verificación y redacción

Parte de la guía del agente (`docs/ez-host-operator.md`). Léela cuando EZ entrega y cuando la
persona quiere redactar.

## La entrega directa

Al terminar las preguntas a NotebookLM, EZ entrega sin revisión del agente ni otra consulta:
cada oración de NotebookLM con una cita que incluye un pasaje es una afirmación (`qa1-1`,
`qa1-2`, …); las oraciones sin cita quedan aparte en `uncited_statements` y no son evidencia.
La deduplicación es conservadora: solo une texto y `context` idénticos, conservando cada fuente
y pasaje asociado. No unas sinónimos ni frases por contención. Con más de 8 afirmaciones el
informe empieza por «Lo central»: las respaldadas por más fuentes.

Una afirmación que sale de una lista trae `context`: los títulos y rótulos bajo los que estaba
(«Estudio A (Autor A, 2021) › Resultado observado»). Muéstralo con ella, porque sin ese contexto
un valor aislado puede no indicar a qué estudio o condición corresponde.

Lee `ez status <corrida> --answer --json` (resumido; `--full` trae la salida completa). La salida
compacta conserva el `context` de cada afirmación y la fuente de cada pasaje. Entrega solo
lo habilitado, con su `citation` y su marcador, y di también qué falta y por qué (`gaps`), las
afirmaciones retenidas (`withheld_claims`), las preguntas no consultadas
(`skipped_questions`) y lo que quedó fuera del corpus (`corpus_exclusions_summary`). El informe
de evidencia (`report.md`, copiado al `reports/` del proyecto) reúne respuesta, pasajes con
página cuando se localiza, fuentes numeradas, lagunas y exclusiones. Cita títulos, autores e identificadores desde
`source` o el informe, nunca desde memoria. Si una afirmación trae el aviso
`numbers_not_in_passages`, señálalo: un número suyo no aparece en sus pasajes.

Un marcador válido identifica un registro, pero no prueba que el pasaje esté localizado.
`found_in_fulltext` indica que el texto citado aparece literalmente en el texto indexado cotejado; eso no evalúa
por sí solo la afirmación. La entrega directa conserva la respuesta de NotebookLM y el pasaje
citado, aunque la localización quede pendiente. Una afirmación verificada pasó el cotejo automático de respaldo. `ez verify` registra
por separado el juicio que una persona hizo al leer el PDF.

## Verificar antes de redactar

`ez continue <corrida> --verify` le pregunta a NotebookLM si las fuentes respaldan las 10
afirmaciones centrales; `--verify qa1-2,qa3-1` verifica las elegidas (unas 2 consultas por
cada 10). Es automático: no leas ni revises a mano la QA. La entrega verificada reemplaza
`answer.json` y `report.md`; la directa queda en `direct/`. Las afirmaciones sin respaldo
quedan retenidas con su motivo y no arrastran a las demás. El respaldo automatizado no
equivale a una revisión científica humana.

## Redactar

Con `ez draft <corrida>` obtienes las afirmaciones con su `citation` y su marcador; si traen
`unverified`, verifícalas antes. `ez recall "<pregunta>" --project <proyecto> --full` recupera
el resultado completo; en MCP usa `full=true`. Su `evidence` (`needs_judgment` o `none`) dice si
recuperó algo, no si basta: `answer_assessed` queda en `false` y el juicio es tuyo. Escribe solo con las
afirmaciones entregadas que puedas atribuir (también puedes usar marcadores de `ez recall`:
`[EZ:<corrida>/<id>]` y `[EZ:pdf-…]`), cita cada una con autor y año más su marcador, y comprueba
con `ez draft <corrida> --check <archivo>`: rechaza marcadores inexistentes o retenidos y lista
las oraciones sin marcador. Una oración sin marcador que afirme algo de la literatura se
elimina o se apoya en una afirmación.

1. Responde lo que se pidió, en prosa clara; listas o tablas solo si la persona las pide.
2. Separa la evidencia de la interpretación y marca la interpretación como tal.
3. No mezcles organismo, población, método, dosis, tiempo o contexto entre fuentes sin decir
   que el vínculo es una inferencia.
4. No afirmes mecanismo, magnitud, causalidad o generalidad más allá de lo que dice el pasaje;
   explicita la incertidumbre y la evidencia indirecta.

## Revisión en persona

`ez verify <corrida>` muestra hasta cinco afirmaciones pendientes con su pasaje y su PDF.
Registra lo que la persona leyó con
`ez verify <corrida> --claim <id> --judgement supported|partial|unsupported --note …`.
`unsupported` retira la afirmación de la respuesta y del informe, también si la corrida se
vuelve a verificar. No registres juicios que la persona no hizo.

## Exportar y actualizar

1. `ez export <corrida>` genera la bibliografía en BibTeX (`--format ris` para Zotero;
   `--all` incluye todo el corpus, no solo lo citado).
2. `ez research "<misma pregunta>" --update <corrida>` crea una corrida nueva con el mismo
   plan, los PDFs verificados y las decisiones de cribado anteriores: solo se criban los
   candidatos nuevos, y el informe dice qué afirmaciones son nuevas, cuáles se mantienen y
   cuáles ya no se sostienen.
