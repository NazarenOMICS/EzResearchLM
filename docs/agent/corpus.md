# Plan, cribado y PDFs

Parte de la guía del agente (`docs/ez-host-operator.md`). Léela al armar el plan y en cada
pausa que la nombre.

## Contexto y corrida

1. `ez context --project <proyecto> --json`: registra con `--set <campo> <valor>` solo lo que
   la persona dijo explícitamente y afecta el alcance (idioma, disciplina, inclusiones,
   exclusiones, período, presupuesto). `research_history` lista investigaciones anteriores del
   proyecto; sus respuestas no sustituyen la evidencia que pide la pregunta actual.
2. `ez research "<pregunta natural>" --project <proyecto> --plan-only --json` crea la corrida.
   Con `--reuse <corrida anterior>`, EZ copia sus PDFs verificados y su procedencia. Las
   corridas de un proyecto comparten su notebook: lo ya procesado no se vuelve a subir.
3. Una corrida se reanuda ante una interrupción; cambiar la pregunta o la búsqueda exige otra.

## El plan

Arma el plan con
`ez plan <corrida> --qa "<pregunta>" … --query proveedor:"<texto>" … --json`. Valida sin
escribir en la corrida ni consultar servicios, guarda la propuesta en `proposals/` y devuelve
la estimación. Con el visto bueno de la persona, impórtalo con el comando que indica
(`ez continue <corrida> --contract <propuesta> --json`). Para cambiarlo, vuelve a usar
`ez plan`.

1. **Preguntas QA** (`--qa`, una por subpregunta, entre 3 y 5; cada una tarda alrededor de un
   minuto en NotebookLM y van en serie):
   1. Concretas y con el objeto explícito: «¿Qué cambios en la sensibilidad a la insulina se
      midieron en adultos tras al menos ocho semanas de ayuno intermitente, y con qué
      método?», no «¿Qué efectos tiene el ayuno?».
   2. Una sola cosa por pregunta; si pide dos, divídela.
   3. En la subpregunta de lagunas, termina con «¿qué no responden estas fuentes?».
   4. Sin presuponer la respuesta ni nombrar resultados que la persona espera.
2. **Búsquedas** (`--query`; proveedores `pubmed`, `europepmc`, `openalex`, `semantic`,
   `crossref`): al menos dos formulaciones por subpregunta, en el idioma de los artículos:
   sinónimos, el grupo taxonómico o la población más amplia, el nombre del mecanismo o del
   método. Sumar palabras a una búsqueda la estrecha y no es otra formulación: si todas comparten
   el organismo o la población y la intervención, agrega una que saque uno de ellos (el grupo
   cercano con la misma intervención, el blanco o el mecanismo sin el organismo). Cada búsqueda
   trae 25 resultados por proveedor (`--max-results`, hasta 100; no lo bajes). `search_advice`
   avisa si el plan se queda corto. `--no-citations` omite la ampliación por citas;
   `--reuse-only`, sin búsquedas, responde solo con la biblioteca del proyecto.
3. **Entrega**: directa, siempre (ver `docs/agent/entrega.md`). No uses `--delivery verified`
   salvo que la persona lo pida.
4. **Fuentes obligatorias**: necesitan identificadores verificados y una razón ligada al
   alcance; las fijadas por la persona conservan `locked_by_user: true`. Una política
   `contextual` pendiente necesita una decisión explícita. Las políticas son el único caso que
   justifica editar una copia de la propuesta antes de importarla. No inventes autores, DOI,
   títulos ni referencias.

## Cribado (`NEEDS_SCREENING`)

EZ deja `screening-request.json` con los candidatos (título, año, identificadores, resumen,
`open_access`, `in_project`). Decide cada uno con una razón breve: `include` si es relevante
para el alcance, `exclude` si no, `uncertain` si hace falta el criterio de la persona. Marca
`key` en los pocos incluidos que una persona del área citaría sí o sí.

1. Lee el título y el resumen de cada candidato que nombre el organismo, la población o la
   intervención de la pregunta, y decídelo con su propia razón. `--exclude-rest` es solo para
   lo claramente fuera de tema: EZ lo rechaza si alcanzaría a un candidato con todos los
   términos de una búsqueda del plan.
2. No decidas por `open_access`: se incluye por relevancia; un artículo clave sin acceso abierto
   se le pide a la persona antes de descargar.
3. `in_project: true` significa que ya está verificado en otra investigación del proyecto:
   incluirlo no cuesta descarga ni subida.
4. Consulta a la persona solo por los dudosos y por las fuentes obligatorias.

Registra las decisiones con
`ez screen <corrida> --include "id1,id2: razón" --exclude "id3: razón" --exclude-rest "razón" --key id1 --json`
(`--uncertain "ids: razón"` para los dudosos; `--check` solo valida). Después del primer
cribado, EZ busca en Europe PMC y OpenAlex los artículos que citan a los incluidos y los que
ellos citan, y vuelve a pausar una sola vez («Segunda ronda»); esos candidatos traen
`linked_to_included`. Solo se descargan los incluidos, hasta `budgets.max_sources` (40 por
defecto; NotebookLM gratuito admite 50). Las exclusiones quedan con su razón en
`corpus_exclusions`.

## PDFs y bandeja

1. **`NEEDS_KEY_PDFS`**, antes de descargar: muestra `key-pdfs.md` tal cual (título en negrita,
   revista, año y enlace al DOI) con las vías honestas para conseguirlos (acceso institucional,
   préstamo interbibliotecario, pedido a los autores) y el enlace a la bandeja. Espera su
   respuesta: si los deja en la bandeja, continúa; si no, `ez continue --skip-missing`.
2. **`NEEDS_USER_PDFS`**, después de descargar: muestra `pdf-request.md` como lista (título, año
   y enlace) y pregúntale si tiene alguno; si no, `--skip-missing`.
3. Cada descarga fallida informa en `corpus_exclusions[].routes` qué rutas se probaron. Si
   aparece `unpaywall (missing_email)`, pide un correo de contacto y guárdalo con
   `ez setup --unpaywall-email`.
4. Un PDF puntual: `ez rescue <corrida> --source <id> --import <pdf>`. Una carpeta:
   `ez rescue <corrida> --import-folder <carpeta>`, que asigna cada PDF a su fuente por título
   e identificadores impresos y lista los que no pudo asignar.

## Identidad (`NEEDS_IDENTITY_CONFIRMATION`)

EZ tomó de la bandeja o descargó PDFs cuya identidad no pudo confirmar solo
(`identity_review`, con la ruta de cada PDF). Abre la primera página, coteja título, autores y
DOI, y confirma juntos los que coincidan con
`ez rescue <corrida> --confirm-identity --source id1,id2 --reviewer host_agent` (no atribuyas a
la persona un cotejo que hiciste tú). Si uno es clave (`key`), díselo. Los que no coincidan
quedan fuera con `ez continue --skip-missing`. La validación estructural no prueba identidad;
una versión ya subida no se reemplaza en silencio.

## Procesamiento en NotebookLM

Tras subir PDFs, EZ espera hasta 4 minutos el procesamiento. Si unos pocos (hasta 1 de cada 5)
siguen sin procesar, sigue sin ellos: quedan en `corpus_exclusions` como `processing_stuck` y
se vuelven a comprobar en el próximo `ez continue`. Con `quota_exhausted`, NotebookLM llegó al
límite de la cuenta: avisa y continúa más tarde, sin repetir el trabajo. No agregues ni borres
fuentes de un notebook de EZ a mano.
