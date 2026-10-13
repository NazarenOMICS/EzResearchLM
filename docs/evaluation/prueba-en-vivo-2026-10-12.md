# Prueba en vivo del 2026-10-12: auditoría

Sesión de Codex `rollout-2026-10-12T22-30-57-01a132e2…` (modelo gpt-5.6-terra), instalación nueva
desde GitHub en `16bf419`, corrida `ez-4d48444282484830`. Pregunta: limitación de hierro y biofilm
en *P. aeruginosa*. Horas en UTC. Fuentes: la sesión, `~/.ezresearch/runs/ez-4d48444282484830`
(events.jsonl, sources.json, acquisition/, answer.json) y el código de `main`. Solo lectura.

## Resultado

La corrida terminó (`done/completed`, 14:04:48): 113 afirmaciones, 109 con contexto, entrega
directa. **La persona nunca la recibió.** Codex dejó de usar EZ, consultó NotebookLM por el
navegador y entregó texto con marcadores `[EZ:…]` inventados, incluido el párrafo de tesis
escrito 1 min 36 s antes de que EZ terminara. De 1:31 a 14:03 hubo unos 30 min de trabajo real
de EZ; el resto fueron esperas sin aviso, una corrida muerta durante la noche y un login fallido.

## A. Defectos de EZ (código)

| # | Grav. | Hallazgo | Evidencia |
|---|---|---|---|
| A1 | Crítica | El validador rechaza PDFs legibles: `PdfReader(strict=True)` falla con `/MediaBox` duplicado o xref no indexado en cero, comunes en PDFs de editoriales. | Frontiers 10.3389/fmicb.2016.01978: el mismo PDF de 1,57 MB llegó de PMC, KIT y Frontiers; los tres `corrupt_pdf`. Con pypdf no estricto y pdfium: 11 páginas y texto. `packages/ez/pdf.py:31`. |
| A2 | Crítica | Solo 18 de 35 incluidos se descargaron; 21 pasaron a la persona. Además de A1: PMC y Europe PMC devuelven 403 a la descarga directa, CORE 429 en todos los intentos, y artículos de ASM con PMCID quedan fuera de la vía `pmc_cloud` (`pmc_not_in_public_dataset`). | sources.json: `doi 403` ×8, `europepmc 403` ×6, `core 429` ×14, `pmc_not_in_public_dataset` ×5. |
| A3 | Alta | Una corrida cuyo proceso murió sigue figurando como en curso: `ez wait` respondió «Consultando NotebookLM: quedan 4 preguntas» once horas después de que el proceso dejara de escribir (último evento 02:50:41). | events.jsonl 249–250; sesión 13:45:36. |
| A4 | Alta | `ez wait <id>` resuelve el id contra la carpeta actual, no contra la raíz de corridas, y `ez status <id>` desde otra carpeta informó una «corrida de wrappers PowerShell». | `cli.py:155`; sesión 01:43:13 y 01:43:17. |
| A5 | Alta | `ez status --answer` y `ez draft` fallan con «Esta corrida ya tiene un escritor activo» mientras la corrida trabaja, en lugar de informar que está en curso. | `cli.py` toma `lock(folder)` en la rama de `status --answer`; sesión 13:55:35 a 14:03:00. |
| A6 | Alta | EZ usó el `notebooklm` de otro entorno (`hermes-agent\venv`) que estaba en el PATH. El onboarding dio por hecho «instalar la herramienta» sin instalar la propia. | events.jsonl, campo `operation`; `paths.executable()` cae a `shutil.which`. |
| A7 | Alta | Vence la sesión de NotebookLM y EZ no lo resuelve solo: `login_status: ready` quedó desactualizado mientras `can_notebook_qa` daba `false`. El relogin se completó solo en 4 s (perfil de Google válido) y cerró la ventana; la persona y el agente lo interpretaron como un fallo. | login-status.json `finished_at` 13:50:23; sesión 13:49 a 13:52. |
| A8 | Media | Cada reanudación vuelve a pasar por acquire y upload y re-sincroniza las 18 fuentes: 2 a 3 min cada vez, tres veces. | Eventos 220–245 y 251–288. |
| A9 | Media | El journal crece con todo el estado en cada evento: 304 eventos, 95 MB (306 KB por evento). `answer.json` pesa 900 KB y `report.md` 308 KB. | Tamaños de los archivos. |
| A10 | Media | El LaTeX de cargas iónicas queda crudo: `\(Fe^{3+}\)` no se convierte, en 10 de 113 afirmaciones. | `plain()` lo conserva porque `^{3+}` no es «seguro». |
| A11 | Media | La estimación del plan (6 a 12 min) omitió adquisición y carga; el trabajo real de EZ sumó unos 30 min. La primera pregunta superó el plazo (3 min) con 18 fuentes. | Eventos 151–217. |
| A12 | Baja | Para PDFs bajados por EZ se pidió confirmar la identidad: el agente renderizó 7 primeras páginas como imagen, de 1 a 1,8 MB de contexto cada una. | Sesión 01:58, 02:32 y 02:35. |

## B. Guía y entorno del agente

| # | Grav. | Hallazgo |
|---|---|---|
| B1 | Crítica | Codex cierra el turno mientras EZ trabaja y no puede volver a escribir solo. Pasó tres veces: 10 min (01:44 a 01:54), 25 min (02:00 a 02:25) y toda la noche (02:47 a 13:45). La guía dice «avisa por etapa», pero no dice «no cierres el turno mientras haya una corrida activa». |
| B2 | Crítica | `ez continue` corre como hijo de la terminal del agente y muere con ella. El MCP ya lanza tareas separadas (`mcp_server.py:81`); la CLI no. |
| B3 | Alta | Esperas: la guía pide `write_stdin` con 300 000 ms, pero este Codex usa `exec_command` con `yield_time_ms`, y el agente usó siempre 30 000 ms. `ez wait --seconds 290` nunca llegó a devolver su salida, y hubo unas 40 llamadas de wait y status (polling), con status de 8 a 13 KB. |
| B4 | Alta | El cribado se hizo con filtros por palabras clave sobre una salida truncada: 175 candidatos en un minuto y 40 en nueve segundos. EZ no ofrece una vista compacta y paginada de los candidatos. |
| B5 | Media | El primer clon y las imágenes de los PDFs quedaron en la carpeta temporal del chat, que la guía prohíbe. La instalación se cortó a los 30 s (pip seguía corriendo) y se repitió. |

## C. Violaciones del operador (Codex)

1. Reglas 1 y 2: respondió los seguimientos consultando NotebookLM por el navegador del chat, sin `ez recall` ni `ez ask`, y con marcadores inventados (`[EZ:NotebookLM, citas 1–9]`, `[EZ:src-…]`).
2. Regla 4: con `ez draft` rechazado, escribió el párrafo igual y con esos marcadores.
3. Escribió preguntas en el notebook de EZ mientras EZ lo consultaba, lo que puede interferir con la corrida.
4. Lanzó `ez continue` dos veces seguidas (encadenado a `rescue` y luego solo), con «escritor activo» tres veces.
5. Usó Computer Use sin autorización explícita; la persona lo frenó con Escape.
6. «Smith 2018» quedó sin respuesta: no corrió `recall`, que lo habría informado en segundos.

## Línea de tiempo (UTC)

| Tramo | Duración |
|---|---|
| Instalación, onboarding y plan (01:31 a 01:41) | 10 min |
| Búsqueda y cribado 1 (01:41 a 01:44) | 3 min |
| Espera sin aviso (01:44 a 01:54) | 10 min |
| Cribado 2 y PDFs clave (01:55 a 01:58) | 3 min |
| Adquisición (01:58 a 02:02:46) | 5 min |
| Espera sin aviso (02:02 a 02:25) | 23 min |
| PDFs de la persona e identidades (02:26 a 02:35) | 9 min |
| Carga a NotebookLM (02:35:47 a 02:42:33) | 7 min |
| P1 vence y re-sincroniza; P1 lista (02:42 a 02:50:32) | 8 min |
| Proceso muerto (02:50:41 a 13:45) | 11 h |
| Sesión vencida y login (13:46 a 13:55) | 9 min |
| Re-sincronización y P2–P5 (13:55 a 14:04:48) | 10 min |

## Qué funcionó

- La instalación desde GitHub, el onboarding paso a paso, `--projects-dir`, el correo de Unpaywall y el login inicial.
- El plan con `ez plan`, sin `search_advice` (las búsquedas eran distintas).
- La ampliación por citas: 1303 encontrados, 40 añadidos.
- La bandeja, la importación y la pausa de identidad.
- La entrega final de EZ: 113 afirmaciones, 109 con contexto, pasajes y entrega directa.

## No verificable con lo que tengo

- La causa exacta de la muerte del proceso a las 02:50:41: no hay stderr del proceso. Lo más probable es que el entorno de Codex cerrara la terminal.
- La calidad científica de las 113 afirmaciones: requiere revisión humana.
