# Hoja de ruta de EZ

Actualizada: 2026-10-11. Este es el **único plan vigente**. Reemplaza a la
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

### Próxima sesión (desde 2026-10-09)

Todo lo anterior está en `main`. El orden para retomar:

1. **Prueba real en Windows con Codex**, desde un clon nuevo de `main` y con
   `~/.ezresearch` borrado. Repetir la pregunta del etambutol y comprobar:
   1. plan con `ez plan` y cribado con `ez screen`, sin JSON ni scripts escritos por el agente;
   2. segunda ronda de cribado por citas y cuántos artículos agrega;
   3. seguimientos en orden: afirmaciones entregadas, `ez recall`, `ez ask`, `ez research`;
   4. «¿qué dice Smith 2019?» (no está en el corpus): debe ofrecer buscar, no responder de memoria;
   5. un párrafo de tesis con marcadores y `ez draft --check`;
   6. alargar la charla hasta que el agente compacte el contexto y repetir un seguimiento.

   Primer intento (2026-10-11, Codex): el login de NotebookLM se cerró solo. `ez setup
   --install-notebooklm` instalaba `notebooklm-py` sin el extra `[browser]`, es decir, sin
   Playwright. Corregido: se instala `notebooklm-py[browser]` y `ez setup --check` informa
   `login_browser_missing` en una instalación anterior. La prueba se repite desde cero.

   Dependencias (2026-10-11): salió `lxml`, que nadie importaba. PyPDF2, abandonada en la
   3.0.1, se reemplazó por `pypdfium2` para el texto (identidad, `--import-folder`, páginas) y
   por `pypdf` para la validación estructural y los metadatos. Sobre 68 PDFs de corridas
   anteriores, la identidad verificada pasó de 31 a 40, sin perder ninguna, y leer todas las
   páginas, de 149 s a 13 s. `pyflakes` quedó en el extra `dev`.

   Segundo intento (2026-10-11, Codex): con «descargalo en documents», el agente clonó y se
   detuvo, sin presentarse ni guiar. La sesión había empezado en una carpeta vacía y nunca
   cargó `AGENTS.md`. Corregido: los README tienen una sección para el agente y `AGENTS.md`
   y `CLAUDE.md`, una regla de primer contacto; `ez setup --check` devuelve `introduction`
   con ejemplos de lo que se puede pedir. Los ejemplos de la guía del agente ya no usan el
   tema del gold set, y un test lo controla.

   Tercer intento (2026-10-11, Codex): con el mismo pedido, el agente solo corrió `git clone`
   y no abrió ningún archivo, así que nada del repositorio podía guiarlo. El mensaje que
   sugieren los README ahora pide instalar, leer `AGENTS.md` y guiar paso a paso. Con ese
   mensaje, la prueba del usuario funcionó mejor.

   Cuarto intento (2026-10-11, Codex): la ventana de login se abrió y se cerró al instante dos
   veces. EZ tomaba el `notebooklm` de otro agente (Hermes) que estaba antes en el PATH, y el
   perfil de navegador guardado tenía una sesión a medias (`Missing required cookies: SID`):
   el login la daba por buena y cerraba. Corregido: EZ usa primero su instalación aislada,
   `login_command` lleva `--fresh`, la sesión a medias se informa como `incomplete_login` y
   la guía pide abrir el login en una ventana visible.

   Quinto intento (2026-10-11): la ventana seguía cerrándose. Causa reproducida en local: sin
   sesión, NotebookLM lleva a su portada pública (`notebook.google.com/trynow`), que
   `notebooklm login` (0.8.0 y 0.8.4) toma por una sesión iniciada. Corregido: `ez setup
   --login` abre su propia ventana de Google, desprendida del agente, espera la cookie de
   sesión de Google (solo su nombre) y recién entonces corre `notebooklm login`. Probado en
   local: la ventana queda abierta y visible, cerrarla da `browser_closed` y una sesión real
   termina en `ready` con `notebooklm list` funcionando. Falta el ingreso de una persona
   desde cero en esa ventana.

   Login probado por el usuario (2026-10-11). Primera entrega: las afirmaciones se mostraban solo
   con su marcador. Ahora `ez status --answer`, `ez draft`, `ez recall` y el informe dan la cita
   de autor y año de cada afirmación (`citation`, «García et al., 2021»), y la guía pide
   mostrarla antes del marcador.

   Prueba larga con Codex (2026-10-11), M2: 2 de 10 artículos clave en el corpus. Schubert 2017 y
   tcsw.2018 se descargaron pero quedaron fuera en silencio por identidad no confirmada: el DOI
   impreso estaba cortado por un salto de línea o seguido del punto de la oración. Corregido: el
   DOI cortado se une y el punto final se acepta; un PDF descargado sin identidad confirmada pausa
   con `NEEDS_IDENTITY_CONFIRMATION` en vez de quedar fuera. Sobre los PDFs de esa corrida y los 68
   anteriores, la identidad automática ganó esos dos artículos y otro más, sin perder ninguno.

   Costo de las esperas (misma prueba): 37 M tokens de entrada; el 41 % se fue en 118 consultas de
   espera, porque Codex esperaba de a 30 s y `ez status` devolvía 56 KB (97 KB con `--answer`).
   Codex permite esperar hasta 5 minutos con un `write_stdin` vacío. Cambios: JSON sin sangría y
   resumido por defecto (`--full` para todo; 6,8 KB y 10 KB), `ez wait`, que vuelve cuando la
   corrida se pausa o termina, y la guía de esperas largas. Reproduciendo la sesión con estos
   cambios, el costo estimado baja a unos 22 M (−41 %).

   Base local (misma prueba): varios `ez ask` (1 a 2 minutos cada uno) buscaban datos literales: la
   referencia de Schubert, si existía «Smith 2019», condiciones de cultivo. `ez recall` busca ahora
   también en el texto de los PDFs del proyecto, página por página (con caché), y devuelve pasajes
   literales con `[EZ:pdf-<hash>-p<página>]`, autor y año, y si están en la lista de referencias;
   `ez draft --check` valida esos marcadores. En el proyecto real respondió esas tres preguntas en
   7 a 11 segundos. El umbral de cobertura sigue sin medición.

   Instalación (misma prueba): Codex instaló EZ en la carpeta temporal de su chat, los informes
   quedaron en `~/.ezresearch` (oculta) y en un chat nuevo hubo que pegarle la ruta. Ahora el agente
   pregunta dónde instalar (`Documents\EZresearchLM` por defecto), `ez setup --projects-dir` deja
   los proyectos en una carpeta visible y mueve los anteriores, y `~/.ezresearch/install.json`
   dice dónde está `ez`; el README trae un mensaje para retomar en un chat nuevo.

   Búsqueda y cribado (misma prueba): el plan buscó una sola frase en tres proveedores, con 20
   resultados, y el cribado excluyó 69 candidatos con una razón genérica; entre ellos, Lim 2019,
   que tenía todos los términos de la búsqueda. Ahora `--exclude-rest` no alcanza a candidatos
   con todos los términos de una búsqueda del plan (19 en esa corrida): se deciden uno por uno.
   `ez plan` avisa (`search_advice`) con una sola formulación o menos de 25 resultados, y la guía
   ya no pide preferir artículos abiertos al cribar.

   Modo de entrega (misma prueba): Codex eligió la entrega verificada «porque es para una tesis»;
   leyó cada respuesta de QA, escribió la revisión a mano y entregó 5 afirmaciones. La guía y
   AGENTS.md piden ahora la entrega directa siempre y `ez continue --verify` (automático) para
   redactar; `ez plan --delivery verified` lo advierte en `search_advice`, y `ez draft` avisa si
   las afirmaciones no están verificadas.

   NotebookLM sin intervención manual (misma prueba): tras renovar el login, EZ no reintentó una
   creación de notebook que nunca había ocurrido y Codex lo creó a mano; un corte de red hizo que
   relanzara `ez ask` tres veces, con una corrida nueva cada vez, y el proyecto figuraba con 12
   «investigaciones». Ahora, si ningún notebook tiene el título de la corrida, EZ lo crea de nuevo;
   `ez ask` retoma la misma pregunta sin respuesta en su corrida, y las preguntas de seguimiento se
   cuentan y listan aparte (el proyecto real: 3 investigaciones y 9 seguimientos). Sigue pendiente
   que el agente rotule los datos externos («fuente externa, no del corpus»): en la prueba, la
   entrada de UniProt salió sin rótulo pese a la regla.

   Lo que lee el agente (2026-10-11): AGENTS.md mezclaba operación y desarrollo, y pedía leer
   completa una guía de 30 KB que repetía sus secciones; en la prueba se leyó tres veces y quedó
   en el contexto de cada llamada. Ahora AGENTS.md (3,3 KB) es solo para operar, el desarrollo
   está en `docs/development.md`, CLAUDE.md importa AGENTS.md, la guía tiene un núcleo de 10,5 KB
   y secciones en `docs/agent/` que cada pausa nombra en `read`, y `operator_reminder` bajó de 557
   a 341 caracteres. Lo que un agente lee al empezar pasa de ~37 KB a ~14 KB; falta medirlo en vivo.

   Antes de la próxima prueba (2026-10-11): la sección «Installation (for the agent)» del README
   mandaba clonar en la carpeta de documentos sin preguntar, y el agente la lee antes de tener
   `AGENTS.md`. Ahora pide preguntar la carpeta, igual que «For the agent». `SETUP.md` explica
   `install.json`, `ez setup --login` y `--projects-dir`, y ya no remite a `docs/history/`. Los
   datos de la prueba anterior quedaron en `~/.ezresearch-prueba-2026-10-11`, para que la prueba
   arranque desde cero y sirvan de base para medir `ez recall`.

   Artículos clave perdidos en la prueba anterior (2026-10-11, analizado con los datos de la
   corrida y búsquedas en vivo, sin repetir la prueba). De los 8 que faltaron, 4 no aparecieron en
   la búsqueda, 2 se excluyeron en el cribado y 2 se descargaron sin identidad confirmada (ya
   corregido):
   1. Las dos búsquedas del plan eran una sola formulación: la segunda solo agregaba palabras a la
      primera (en PubMed, de 20 resultados a 0) y ambas tenían el mismo organismo y fármaco. Con el
      grupo cercano o el blanco del fármaco, 3 de los 4 perdidos salen entre los 6 primeros de algún
      proveedor; el cuarto está en los puestos 31 y 62 de la búsqueda original. Ahora `ez plan`
      avisa en `search_advice` cuando una búsqueda contiene todos los términos de otra y cuando
      todas comparten un núcleo de dos o más términos, y `docs/agent/corpus.md` lo explica.
   2. La ampliación por citas encontró 3 de los 4 entre 625 registros nuevos, pero quedaron en los
      puestos 77, 381 y 112, y al cribado pasan 40. El puntaje compara con la pregunta y las QA en
      español; usando solo las palabras de las búsquedas, los puestos pasan a 47, 308 y 32 y los 4
      que el agente incluyó suben. Con una sola corrida no se cambia: se mide en la próxima.
   3. Uno de los excluidos en el cribado ya lo protege la regla de `--exclude-rest`. El otro (2024)
      no nombra el fármaco en el resumen; rescatarlo exige saber que su vía es la que el fármaco
      afecta, y no se fuerza con código.

   Medición de `ez recall` (2026-10-11), sin repetir la prueba: los 9 seguimientos de la sesión de
   Codex, repetidos con el código actual sobre el proyecto tal como estaba en cada uno, comparados
   con lo que respondieron `ez ask` y Codex. `ez recall` habría evitado NotebookLM en 3; dio por
   suficientes 2 que no lo eran: crecimiento sin datos (0,62) y «Smith 2019», que no existe (0,67).
   Los aciertos suficientes tenían 0,60, 0,64 y 0,83: ningún umbral separa los casos, así que el
   0,6 queda. Los pasajes de PDF nunca cambiaron una decisión: las 9 consultas estaban solo en
   español y los PDFs en inglés, así que coincidían en el nombre del organismo y ganaban tablas de
   cepas y listas de referencias; con los términos en inglés, los pasajes pasan a ser los
   pertinentes. Cambios:
   1. Un trabajo nombrado en la pregunta (autor y año, o DOI) que no está entre las fuentes del
      proyecto impide `sufficient` y aparece en `named_works_absent`, con su aviso.
   2. Los pasajes de listas de referencias se siguen mostrando pero no cuentan para
      `pdf_coverage`.
   3. `query_language_mismatch` avisa cuando menos de 3 palabras de la consulta que no son nombres
      propios aparecen en los PDFs; en la sesión, 7 de las 9 consultas.


   Afirmaciones que salen de listas (2026-10-11), medido sobre las respuestas guardadas de la
   prueba anterior, sin consultar NotebookLM. NotebookLM responde en listas anidadas por estudio
   y condición, y EZ guardaba cada viñeta suelta: 176 de 262 afirmaciones eran fragmentos como
   «Concentración de EMB: 10 µg/ml», sin decir de qué estudio ni de qué condición. Además, 92
   tenían LaTeX crudo (`\(10\text{ }\mu\text{g/ml}\)`), y de las 18 uniones de afirmaciones
   repetidas, 16 juntaban el mismo fragmento de condiciones o estudios distintos, mezclando sus
   pasajes. Así falló el seguimiento de condiciones de cultivo en `ez recall`. Cambios:
   1. Cada afirmación guarda en `context` los títulos y rótulos bajo los que estaba; el informe,
      `ez status`, `ez draft`, `ez ask`, las notas del proyecto, `ez recall` y la verificación lo
      usan. Los títulos y las viñetas que solo rotulan dejan de contarse como oraciones.
   2. El LaTeX simple pasa a texto plano (µg/ml, °C, OD600, ≈, letras griegas).
   3. Dos afirmaciones con distinto contexto ya no se unen por tener el mismo texto.

   Resultado sobre esas respuestas: 193 de 193 fragmentos con contexto, LaTeX en 0 afirmaciones y
   2 uniones, ambas legítimas. Las corridas ya entregadas conservan su `answer.json`; el cambio
   vale para las entregas nuevas.
2. **Puntuar la corrida** con `gold_set_benchmark/puntuar.py --mision M2` y anotar en
   `gold_set_benchmark/` cuántos de los 10 artículos clave entraron, en especial los dos de
   proteómica de *M. smegmatis* (T6).
3. **Medir `ez recall`**: en cuántos seguimientos alcanzó sin consultar NotebookLM y si
   alguna vez dio por suficiente algo que no lo era. Ajustar el umbral de cobertura (0,6,
   puesto sin medición) según eso.
4. **A3**: comparación con ChatGPT con búsqueda y con NotebookLM manual.
5. **C1 y D2**: instalación en un Windows limpio solo con el README, y prueba de la extensión
   de Claude Desktop.
6. **C4**: igualar versiones, fijar la extensión a una etiqueta y publicar `v0.3.0`.
7. Deuda técnica T2 a T5, después del lanzamiento.

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
15. Cobertura (2026-10-09): `ez plan` pide 25 resultados por búsqueda y proveedor (antes, sin
    `max_results`, eran 5); ampliación por citas en Europe PMC y OpenAlex con una segunda
    ronda de cribado; `ez ask` informa `evidence` y, si la biblioteca no alcanza, ofrece
    buscar artículos nuevos en vez de dejar que el agente complete. Falta medirlo en vivo
    contra el gold set de M2.
16. Memoria del proyecto (2026-10-09): en cada entrega EZ reescribe `projects/<p>/notes/`,
    un vault de Obsidian con los pasajes citados por fuente y las afirmaciones por
    investigación, y `ez recall` busca en ellos sin consultar NotebookLM. Los marcadores
    `[EZ:<corrida>/<id>]` permiten citar afirmaciones de otras investigaciones del proyecto
    y `ez draft --check` los resuelve. Reemplaza la búsqueda con QMD de la versión anterior.
    Falta medir cuántos seguimientos resuelve sin consultar NotebookLM.

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
| C4 | Etiquetar la versión: `NazarenOMICS/EzResearchLM#1` y `NazarenOMICS/EzResearchLM#2` ya están en `main`; falta igualar la versión del paquete (`0.2.0a3`) y la de la extensión (`0.3.0`) y fijar la extensión a esa etiqueta en vez de `@main` | usuario | Etiqueta `v0.x` |
| C5 | **Hecho (2026-10-09):** limpieza de código muerto. `search_topic.py` quedó en lo que EZ usa (búsqueda y deduplicación; de 1.096 a 187 líneas); salieron `unpaywall.py`, `base_search.py` (importaba un módulo inexistente), los métodos de descarga y lectura de los buscadores, `ez/upload.py` e importaciones sin uso | código | `pyflakes` sin avisos |

### Fase D. Usuarios sin terminal

| ID | Tarea | Dueño |
|---|---|---|
| D1 | **Hecho:** `ez_continue` y `ez_submit` corren en segundo plano y `ez_status` informa la operación | código |
| D2 | Prueba real de la extensión en Claude Desktop, incluido el login | usuario |
| D3 | Migrar a `mcp` 2.x cuando su API se estabilice | código |

### Deuda técnica conocida

| ID | Tema | Dueño |
|---|---|---|
| T1 | **Hecho (2026-10-09):** QMD salió de `ez setup` y de la documentación; ningún comando lo usaba. Su función (responder con pasajes ya citados antes de volver a preguntar) se retoma con un vault propio de EZ | código |
| T2 | `legacy_signals` nombra las señales vigentes (`NEEDS_SCREENING`, …): renombrarlo cambia el esquema de estado y requiere migración | código |
| T3 | `engine.py` (≈1.300 líneas) y `main()` de `cli.py` concentran casi toda la lógica; partirlos por etapa facilitaría mantenerlos | código |
| T4 | `paper_search_mcp` lee su propio `.env` desde la carpeta actual, además del que carga EZ | código |
| T5 | Las guías del usuario y del agente están solo en español, y los mensajes del programa también | código |
| T6 | La ampliación por citas y el pedido de 25 resultados no se midieron en vivo | usuario |

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
