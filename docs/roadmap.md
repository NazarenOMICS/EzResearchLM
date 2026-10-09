# Hoja de ruta de EZ

Actualizada: 2026-10-08. Este es el **único plan vigente**. Reemplaza a la
auditoría P1–P14, al plan v2 por fases (0–7), a la lista de mejoras pendientes y a
`docs/history/plan-refactor-v6.md`. Esos documentos quedan como registro del porqué de cada
cambio. `docs/history/ez-refurbish-implementation-plan.md` y `docs/history/refurbish-progress.md` son
anteriores a todo esto y solo tienen valor histórico.

Cada ítem tiene un dueño: **código** (se hace en el repositorio y se valida offline)
o **usuario** (requiere la cuenta de NotebookLM, una máquina Windows o el criterio de
una persona).

## 1. Dónde estamos

Corrida en vivo v6, M2 sobre PDFs ya cargados
(`gold_set_benchmark/resultado_ezresearchlm_v6.md`):

| Modo | Afirmaciones | Consultas | Minutos |
|---|---:|---:|---:|
| Directo | 102 | 5 | 7 |
| Verificado | 9 de 10 | +2 | +7 |

En v5 la misma misión entregó 0 de 14 en 20 minutos.

Corrida v6b (`gold_set_benchmark/resultado_ezresearchlm_v6b.md`):

1. **Desde cero**, en un proyecto nuevo: 6,5 minutos en total, con 4 preguntas y
   4 consultas a NotebookLM. Se cribaron 49 candidatos, se incluyeron 15 y se
   descargaron 10. Las 5 descargas fallidas fueron `routes_exhausted`. Entregó 84
   afirmaciones.
2. **M2 directo:** 103 afirmaciones en 5,8 minutos; ninguna se unió con otra.
   Con `--verify`, 8 de 10 en 5,5 minutos más.
3. **Precisión del modo directo:** en 20 afirmaciones al azar, 18 respaldadas,
   2 parciales y 0 no respaldadas (90 %). Con n = 20, el intervalo de confianza al
   95 % va de 70 % a 97 % (Wilson).

Corrida v6c (`gold_set_benchmark/resultado_ezresearchlm_v6c.md`), desde cero con
Unpaywall configurado:

1. 5,3 minutos hasta la entrega directa.
2. 8 de 15 descargas fallaron; 2 se rescataron con PDFs del usuario. Las rutas
   registradas fueron sobre todo `access_denied`, `tls_downgrade` y `rate_limited`.
   Unpaywall configurado no cambió el resultado: la hipótesis de B6 queda descartada.
3. 87 afirmaciones: 20 en el cuerpo y 67 en el anexo; ninguna unida.
4. `--import-folder` no asignó ninguno de los 2 PDFs.

**Qué no sabemos todavía:**

1. cómo se compara EZ con ChatGPT con búsqueda y con NotebookLM manual;
2. si la instalación funciona en un Windows limpio y en Claude Desktop.

## 2. Hecho

**Auditoría y plan v2:**

1. Fase 0: una sola rama; Anna's Archive fuera; aviso de versión preliminar.
2. Fase 1, rigor:
   1. revisión versionada por corpus;
   2. bibliografía completa en cada cita;
   3. retenciones, preguntas omitidas y exclusiones registradas;
   4. señales coherentes;
   5. detección de cuota agotada;
   6. validación en seco `--check`.
3. Fase 2, corpus:
   1. cribado con tope de fuentes;
   2. deduplicación DOI, PMID y PMCID;
   3. PDFs duplicados por hash;
   4. identidad por PMID o PMCID;
   5. lagunas clasificadas por causa;
   6. conteo de consultas.
4. Fase 3, entregables: `report.md`; redacción con `ez draft` y marcadores `[EZ:<id>]`.
5. Fase 4, lanzamiento parcial: README humano; capa legacy separada; canary de NotebookLM.
6. Fase 5, madurez:
   1. `ez research --update` con diferencias;
   2. revisión humana con `ez verify`;
   3. aviso de números ausentes en los pasajes.
7. Fase 6: extensión experimental de Claude Desktop (servidor MCP y paquete `.mcpb`).

**Refactor v6:**

1. Retención por afirmación, no por subpregunta.
2. Verificación con cualquier fuente del corpus.
3. Revisión que se corrige sola.
4. Notebook por proyecto y conversación nueva por pregunta (`--new`).
5. Modo directo por defecto.
6. Búsqueda y descarga en paralelo.
7. Espera interna del procesamiento.
8. PDFs atascados excluidos sin frenar la corrida.
9. Oraciones repetidas unidas y resumen "Lo central".
10. `ez continue --verify`.
11. Tiempos explicados al usuario.

**Decisiones tomadas:**

1. Una afirmación fallida no arrastra a su subpregunta.
2. La entrega directa es la opción por defecto y la verificada queda para redactar.

## 3. Descartado o reemplazado

1. Protocolos de verificación v3 y v4 (pasajes en la pregunta, lotes grandes): rompían la entrega en vivo. Los reemplaza v5.
2. Plantilla compacta de revisión QA para el agente: la reemplazan el modo directo y `--verify`.
3. Un notebook por corrida: lo reemplaza el notebook por proyecto.
4. Consultas paralelas a NotebookLM: con `--new` en un mismo notebook tienen que ir en serie. Cada pregunta tarda alrededor de un minuto, igual que en la web.
5. Parámetro `min_oa`: pertenece a los wrappers legacy y no afecta a `ez`. No se toca.
6. Entrega progresiva en dos tandas: con notebook compartido y modo directo, la primera respuesta ya llega en minutos. Se reconsidera solo si la corrida desde cero tarda demasiado.

## 4. Pendiente, en orden

### Ronda 7 (2026-10-08): mejoras iterativas antes de la comparación

Hecho y validado offline:

1. Acceso abierto en el cribado, consultado a OpenAlex.
2. Pedido temprano de PDFs (`NEEDS_USER_PDFS`, `pdf-request.md`, `--skip-missing`).
3. Páginas por pasaje.
4. `ez export`.
5. Estimación de tiempo.
6. Onboarding paso a paso (`onboarding` en `ez setup --check` y guion de primera conversación).
7. Guía para escribir preguntas QA.
8. Medidor `gold_set_benchmark/puntuar.py`.
9. Pedido de artículos clave sin acceso abierto antes de descargar (`NEEDS_KEY_PDFS`, `key-pdfs.md` con enlaces al DOI).
10. Carpetas por proyecto: bandeja de PDFs que EZ toma sola, informes con su `.bib` e índice `README.md` (`docs/carpetas.md`).
11. Elección de proyecto ante cada pregunta (`ez projects --suggest`) y biblioteca del proyecto: PDFs verificados reutilizados sin descargar, respuesta solo con lo que ya hay (`reuse_only`).

12. Enlaces al DOI en cada lista de artículos, opciones para elegir con un clic (`choices`) y
    carpetas en inglés (`inbox/`, `reports/`, `README.md`) con migración de las anteriores.
13. Preguntas de seguimiento con `ez ask`, respondidas solo con la biblioteca del proyecto.
14. Barandas contra la deriva del agente (2026-10-09), tras una prueba con Codex en Windows en
    la que, después de compactar el contexto, el agente respondió con búsqueda web y sin el
    corpus: reglas fijas al inicio de AGENTS.md, CLAUDE.md y la guía; `operator_reminder` en
    cada salida JSON; `ez plan` y `ez screen` para que el agente no escriba JSON a mano;
    aviso en `docs/history/`.

Ciclo de iteración desde ahora:

1. Correr M1, M2 y M3 sin abrir el gold set.
2. Puntuar con `puntuar.py`.
3. Corregir.
4. Repetir hasta que el puntaje deje de mejorar.

Recién entonces sigue A3.

### Fase A. Medir (bloquea todo lo demás)

| ID | Tarea | Dueño | Puerta |
|---|---|---|---|
| A1 | ~~Corrida v6b~~ **Hecho** (2026-10-08). La precisión del modo directo fue de 90 %: supera la regla del 80 % y el modo directo sigue siendo el valor por defecto | usuario | `gold_set_benchmark/resultado_ezresearchlm_v6b.md` |
| A2 | Acuerdo humano del modo verificado: 30 afirmaciones juzgadas con `ez verify` | usuario | Porcentaje de acuerdo publicado |
| A3 | Benchmark M1 a M3 con ChatGPT con búsqueda y con NotebookLM manual, según `gold_set_benchmark/reglas_benchmark.md`, y M3 (control negativo) con EZ | usuario | Planilla con referencias inventadas, precisión y tiempo por sistema |

**Regla de decisión:**

1. Si la precisión del modo directo (A1) es menor al 80 %, el modo verificado pasa a ser el valor por defecto.
2. Si EZ no supera a las alternativas en referencias inventadas y precisión (A3), se revisa el producto antes de distribuirlo.

### Fase B. Arreglos que salen de la medición

| ID | Tarea | Dueño |
|---|---|---|
| B1 | Corregir lo que muestren A1 a A3 (lentitud de la corrida desde cero, oraciones mal cortadas, falsos positivos) | código |
| B2 | Corpus inicial más chico: `budgets.max_sources` de 40 a 15, con ampliación cuando una subpregunta queda sin respaldo; priorizar rutas con identidad segura (PMC, Unpaywall) | código |
| B3 | **Hecho:** `ez rescue --import-folder` asigna cada PDF de una carpeta a su fuente por título e identificadores impresos; `--confirm-identity` acepta varios IDs. Tras v6c, que no asignó ninguno, también se asigna por título completo, DOI en el texto o DOI en el nombre del archivo, con la identidad pendiente de confirmar | código |
| B4 | Decidir la verificación por cita textual: mantenerla, exigir revisión humana o quitarla, según cuántas veces aparezca `verification_quote` en A1 a A3 | decisión |
| B5 | **Hecho:** la cláusula que sigue a la última cita, tras un punto y coma, pasa a «sin cita» | código |
| B6 | **Hecho en código, falta medir:** cada descarga fallida informa las rutas probadas y su motivo. Unpaywall se salteaba sin un correo de contacto; ahora se guarda con `ez setup --unpaywall-email`. v6c descartó que esa fuera la causa. Tras v6c: las redirecciones a http se reintentan por https y las fuentes que ningún índice ofrece se informan como `no_open_access_location`. Lo que queda son artículos pagos | código |
| B7 | **Hecho en código, falta medir:** se unen también las oraciones contenidas en otra que cita una fuente común, salvo que solo una niegue. Cada subpregunta muestra sus 10 afirmaciones más respaldadas y el resto va a un anexo. En v6c el anexo funcionó (20 de 87 en el cuerpo) y la unión no actuó: NotebookLM no repite oraciones casi iguales | código |

### Fase C. Lanzamiento en GitHub

| ID | Tarea | Dueño | Puerta |
|---|---|---|---|
| C1 | Instalación en un Windows limpio siguiendo solo el README | usuario | Lista de pasos que fallaron, o ninguno |
| C2 | **Hecho:** informes viejos y planes superados en `docs/history/`. El 2026-10-09 se quitó la capa de wrappers PowerShell (scripts `.ps1`, `notebooklm/scripts`, `examples/`, guías legacy) y `Rules_Of_Writing.md`, cuyas reglas generales pasaron a AGENTS.md | código | Raíz con README, AGENTS, CLAUDE y SETUP |
| C3 | Publicar en el README los resultados de A1 a A3 y los tiempos reales | código | Números con fecha y versión |
| C4 | Mergear `NazarenOMICS/EzResearchLM#1` a `main` y etiquetar la versión | usuario | Etiqueta `v0.x` |

### Fase D. Usuarios sin terminal

| ID | Tarea | Dueño |
|---|---|---|
| D1 | **Hecho:** `ez_continue` y `ez_submit` corren en segundo plano y `ez_status` informa la operación | código |
| D2 | Prueba real de la extensión en Claude Desktop, incluido el login | usuario |
| D3 | Migrar a `mcp` 2.x cuando su API se estabilice | código |

### Fase E. Mejoras de uso (después del lanzamiento)

| ID | Tarea | Dueño |
|---|---|---|
| E1 | **Hecho (ronda 7):** número de página por pasaje, ubicándolo en el PDF local | código |
| E2 | **Hecho (ronda 7):** `ez export` a BibTeX y RIS | código |
| E3 | **Hecho (ronda 7):** estimación de consultas y minutos al validar el contrato | código |
| E4 | Benchmark ampliado a 8 misiones | usuario |

### Fase F. Condicional

F1. Aplicación web propia. Requiere una API oficial con consulta y citas para cuentas
individuales, que hoy NotebookLM no ofrece. Se revisa cada vez que cambie esa API.
Mientras tanto, la vía para usuarios sin terminal es la extensión de escritorio (fase D).

## 5. Cómo se actualiza este plan

1. Cada cambio del plan se registra en este archivo con la fecha.
2. Un ítem pasa a "Hecho" cuando está en la rama con pruebas, o, si es de medición, cuando su informe está en `gold_set_benchmark/`.
3. Un ítem nuevo entra en la fase que corresponde por dependencia, no al final.
