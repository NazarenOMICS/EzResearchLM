# Ejecución del refactor EZ

Actualizado: 2026-09-18. Rama de trabajo: `codex/ez-refurbish`.
Estado: **candidato interno; validación final incompleta; no listo para lanzar**.

El plan de referencia es [ez-refurbish-implementation-plan.md](ez-refurbish-implementation-plan.md).
El usuario autorizó implementarlo por etapas y eligió el agente anfitrión como
backend de planificación. No se contrató ni se exige otra API de modelos.

## Implementación y evidencia por fase

| Fase | Cambios implementados | Evidencia disponible / condición pendiente |
|---|---|---|
| F0 · Línea base | Copia con hashes del trabajo previo; wrappers y corridas conservados | `baseline-validation.md`; no commits, reset, clean ni stash |
| F1 · Validación | Ejecutor de pruebas offline, smoke aislado, CI Windows/Linux y comprobación del paquete instalado | Matriz local comprobada; CI remoto aprobado en Windows/Linux con Python 3.10/3.12 sobre `257cb28`; instalación aislada y smoke |
| F2 · Contratos y estado | Esquemas v2, journal con hashes, bloqueo de escritor, transacciones recuperables, migración lateral | Fixtures de cortes, modificaciones ajenas, versión desconocida, conflicto legacy y conservación del origen |
| F3 · Políticas y gates | Cinco políticas por alcance, semántica real del switch, respuesta parcial, retención por integridad, `--require-complete` | Pruebas de políticas, switch en PowerShell, QA vacía, citas ajenas, archivos alterados y revisión obsoleta |
| F4 · Supervisión | Presupuestos y procesos con deadline; cancelación de descendientes; reconciliación de operaciones remotas | Fixtures de cuelgues/hijos y HTTP continuo; cortes controlados con NotebookLM real después de subida y antes de confirmar QA |
| F5 · Recuperación | Rutas públicas, DOI, PMC Cloud vigente, Europe PMC, OpenAlex, Unpaywall, CORE, OpenAIRE, validación, procedencia, importación manual y Anna opt-in | Fixtures de errores y consentimiento; PDF real recuperado por OpenAlex y por PMC Cloud; benchmark curado y credenciales opcionales pendientes |
| F6 · Interfaz y contexto | Los siete comandos `ez`, setup aislado, contexto versionado, historial y reutilización de PDFs verificados; SETUP, CLAUDE y slash commands alineados con EZ | Paquete probado fuera del checkout; onboarding de usuario nuevo en Windows limpio pendiente |
| F7 · Operador anfitrión | Guía de EZ, contratos de planificación y revisión, QA NotebookLM, auditoría de citas y nueva QA de respaldo por afirmación | Recorrido autenticado interno con afirmaciones citadas; evaluación independiente y usuarios nuevos pendientes |
| F8 · Beta y lanzamiento | Protocolo, métricas locales sin telemetría y requisitos de evidencia | E2E técnicos internos documentados; no hay beta realizada, E2E de release en Windows limpio ni autorización de lanzamiento |

Esta tabla distingue implementación de aceptación. Una fase con código o pruebas
locales no queda certificada si todavía faltan sus comprobaciones externas.

## Archivos principales

- `packages/ez/cli.py`, `setup.py`, `context.py`: interfaz, entorno y contexto.
- `contracts.py`, `schemas/`, `state.py`, `legacy.py`: contratos, persistencia y migración.
- `policies.py`, `engine.py`, `audit.py`, `doctor.py`: ejecución y controles de entrega.
- `discovery.py`, `acquisition.py`, `pdf.py`, `consent.py`: fuentes y recuperación.
- `process.py`, `winjob.py`, `upload.py`: procesos acotados y subidas.
- `tests/`, `packages/paper_search/tests/`, `notebooklm/tests/`: pruebas de regresión.
- `scripts/validate.py`, `check_installed.py`, `run_smoke_tests.ps1`, `.github/workflows/ci.yml`: comprobaciones reproducibles.
- `docs/ez-host-operator.md`, `ez-contracts.md`, `external-contracts.md`, `beta-and-release.md`: operación, formatos y validación externa.

Los wrappers previos mantienen sus nombres y sus recorridos compatibles. Los
cambios locales originales del usuario se preservan; el diff respecto de HEAD
incluye ese trabajo y no debe atribuirse íntegramente al refactor.

## Prueba real realizada

Corrida privada: `ez-1b786deb39914612`. La búsqueda por DOI
`10.1038/sdata.2016.18` obtuvo metadatos de Europe PMC. Se recuperó un PDF por una
ubicación alternativa de OpenAlex, con destino público del editor. La validación
estructural reconoció 9 páginas y 254899 bytes; se cotejaron título e identificador.
SHA-256 del archivo: `cdddd9f4808f7e3e1f013139c3915ef4d7cdccb008fa947ef5f72b4c7b6ffde7`.

El primer intento llegó a subida y se detuvo por autenticación expirada; no se
contabilizó como E2E. Después de que el titular renovara el login, se reanudó la
misma corrida: creación de notebook, subida, readiness, QA, revisión del anfitrión,
comprobación adicional de respaldo y entrega de tres afirmaciones citadas.
El resultado actual es `complete`, integridad `pass`; el diagnóstico remoto no
detectó inconsistencias. Los intentos fallidos y el contrato revisado se conservaron.

La prueba real motivó dos correcciones: lectura de citas agrupadas/por rango y
dictamen de respaldo con referencias nativas, porque JSON dentro de bloques de
código llegó sin referencias. Se excluyeron del borrador las afirmaciones sin
pasajes suficientes; cada afirmación entregada tiene cita sustantiva y nueva QA.
Esto prueba un E2E técnico interno con intervención del anfitrión, no un entorno
Windows limpio, una revisión científica independiente ni la aceptación de beta.

Segunda corrida privada: `ez-55ba25cb08a341ea`. Reutilizó el original verificado y
creó otro notebook. Se interrumpió el proceso después de subir y después de recibir
QA antes de guardarla. La continuación conservó el notebook y su fuente, entregó
una respuesta parcial con `NEEDS_SOURCE_RESCUE`, e importó la adenda con procedencia
y confirmación de identidad del anfitrión. La respuesta final cubre ambos alcances,
con integridad `pass`, dos fuentes remotas y la fuente original sin reemplazo.

La cita de la adenda llegó como ancla sin pasaje. EZ conservó la QA original y la
resolvió mediante una cita literal contigua al marcador que aparece una sola vez
en el texto indexado de esa misma fuente por NotebookLM. El snapshot, el cotejo y
sus hashes quedan en `citation-resolution/`; no se infirió el pasaje desde el PDF
local. Los casos de texto ausente, duplicado o de otra fuente siguen sin resolverse.

Las dos corridas fueron técnicas, en el equipo de desarrollo y con revisión del
anfitrión. Parte de la segunda se ejecutó desde el wheel aislado fuera del checkout;
los fallos encontrados motivaron revisiones del candidato durante la validación.
Por tanto, no acreditan dos recorridos de release sin cambios sobre Windows limpio.

Un tercer canary, limitado a subidas, descartó deliberadamente la respuesta de una
subida real y reanudó la operación. NotebookLM conservó una sola fuente; EZ recuperó
su ID por el nombre determinista del archivo y no volvió a subirla. El recibo
`upload-reconciliation.json` registra ese resultado; no se contabiliza como otro E2E.

## Evidencia local y candidato

Los informes están en `runs/refurbish-validation/`, fuera del control de versiones:

La matriz local anterior a la publicación pasó 95 pruebas por versión de Python (3.10, 3.11 y 3.12).
Incluye respuestas externas de formato incorrecto, recuperación tras pérdida de
respuesta al crear notebook y un servidor HTTP local que transmite continuamente:
el supervisor lo interrumpe dentro de cinco segundos más la gracia de limpieza.
Estos casos no contactan NotebookLM ni prueban autenticación real.

La matriz Ubuntu WSL pasó con Python 3.10.20 y 3.12.13 sobre una copia aislada del
código verificada por hashes. En cada versión hubo 94 pruebas aprobadas y una
omitida por requerir PowerShell; esa prueba sí se ejecutó en Windows. El mismo
wheel pasó instalación y comandos básicos fuera del árbol en ambos entornos Linux.
Esto comprueba el núcleo portable, no reemplaza GitHub Actions ni Windows limpio.

El canary de PMC Cloud conserva resultado, checksum, versión, licencia y revisión
de identidad en `provider-canary-20260917/pmc_cloud/`. Detectó que el servicio OA
anterior ya estaba retirado y motivó su sustitución en EZ y en el helper legacy.
La identidad automática quedó `needs_review`; el anfitrión cotejó título y DOI
extraídos de la primera página y guardó una revisión separada. Ese cotejo no se
presenta como una aprobación automática ni como QA de NotebookLM.

El canary adicional probó DOI, OpenAlex, Unpaywall, CORE, OpenAIRE y Europe PMC
para esa misma obra. Las cuatro primeras rutas válidas (DOI, OpenAlex, Unpaywall y
OpenAIRE) entregaron el PDF del editor; Europe PMC devolvió 403. CORE entregó una
adenda que el verificador inicial aceptaba por contener el título y DOI citados.
Se corrigió ese falso positivo, se añadió una regresión y se conservó tanto el
resultado original como la reevaluación en `provider-canary-20260917/identity-recheck.json`.
El archivo de CORE queda para revisión y fue rechazado como sustituto por el anfitrión.
Son comprobaciones de una sola obra, sin validez estadística como benchmark.

Las URLs de PDF ya conocidas se prueban antes de consumir presupuesto en APIs de
metadatos. Las rutas adicionales se intercalan por proveedor para que muchas URLs
de uno solo no agoten el límite y excluyan a los demás. Ambos casos tienen regresión.

- `offline-validation.json`: conteos, resultados y hashes del código bajo prueba.
- `validation-python310.json` y `validation-python312.json`: suites completas en
  entornos separados con dependencias fijadas. El lock selecciona `rpds-py` compatible
  con Python 3.10; la versión de Python 3.11+ no se instala en 3.10.
- `smoke-offline.json`: recorridos básicos de wrappers, con carpetas temporales aisladas.
- `installed-validation.json`: imports del paquete instalado, cuatro esquemas,
  guía incluida y recorrido context → research → continue → doctor sin red.
- `linux-runtime.json`, `validation-linux310.json`, `validation-linux312.json` e
  `installed-linux*.json`: matriz Linux aislada, con la omisión de PowerShell explícita.
- `candidate-manifest.json`: hash del wheel y enlaces/hash de los informes del candidato.
- `authenticated-e2e.json`: hashes y verificación de las dos corridas técnicas,
  citas, QA de respaldo, miembros remotos y transición parcial→completa; límites explícitos.
- `interruption-after-upload.json` y `interruption-qa-response.json`: recibos de
  cortes controlados con el servicio real, no simulaciones de su respuesta.
- `live-runs/ez-1b786deb39914612/`: contrato, decisiones, adquisición y checkpoint real.

Los informes no sustituyen una instalación limpia del sistema operativo. Un wheel
anterior deja de representar el árbol si se modifica el código; reconstruirlo y
repetir la comprobación de instalación antes de evaluar el candidato siguiente.

## Próximas condiciones de aceptación

1. Repetir el protocolo de aceptación sobre Windows limpio con el candidato final,
   conservando creación, subida, readiness, QA, revisión, respaldo y respuesta.
2. Completar el benchmark de recuperación con corpus curado.
   Comprobar los proveedores opcionales con sus
   credenciales legítimas cuando formen parte del alcance de soporte acordado.
3. Designar revisor independiente y cohorte de beta. Evaluar afirmaciones centrales,
   onboarding, comprensión de estados, reanudación y métricas con denominadores.
4. Revisar el manifiesto y aprobar el lanzamiento conforme a `beta-and-release.md`.

Renovar una sesión exige interacción del titular de la cuenta. La revisión humana,
la beta y la aprobación de lanzamiento no pueden deducirse de pruebas automatizadas.
No se publicará el producto como validado mientras falte esa evidencia.

## Publicación del candidato para CI

El usuario autorizó publicar los 87 archivos revisados en la rama
[`codex/ez-refurbish-ci`](https://github.com/NazarenOMICS/EzResearchLM/tree/codex/ez-refurbish-ci).
El commit `257cb2844370fc0336cb4911442a3097f69f740c` conserva la selección revisada
y corrige una inicialización tardía del supervisor en el wrapper legacy de respuestas,
con una prueba de regresión del recorrido de recall. El núcleo EZ no cambió.
La rama se preparó en un worktree separado; el índice y la rama de trabajo original
se conservaron. No se fusionó con main ni se publicó una versión de lanzamiento.

La [corrida de GitHub Actions 35390317770](https://github.com/NazarenOMICS/EzResearchLM/actions/runs/35390317770)
aprobó los cuatro trabajos: Windows y Ubuntu con Python 3.10 y 3.12. Incluye suite,
construcción e instalación del wheel fuera del checkout, comprobación de archivos
prohibidos y validación PowerShell 5.1/7 en Windows. La validación local previa del
commit pasó 96 pruebas y la instalación aislada en Python 3.11.

Los informes descargados y sus hashes quedan en `runs/refurbish-validation/`,
con `ci-candidate-manifest.json` como referencia del candidato publicado. El wheel
local de esta revisión está en `ci-dist/`, SHA-256
`dde999f069a72d957b7b60f38bf4c1b739d8e33f159a90f539191ce70f0fd8db`.
El manifiesto anterior y sus dos E2E se conservan como evidencia de la revisión
precedente; no se reasignan a este wheel ni se consideran una prueba de usuario
nuevo en Windows limpio. Siguen pendientes el benchmark curado, la revisión
independiente, la beta y la aprobación de lanzamiento.

## Preparación de primer uso, candidato 0.2.0a2

La revisión de UX agrega bienvenida con tres pasos, guía local mediante `ez --guide`
y ayuda de los siete comandos. README muestra primero el recorrido conversacional;
la referencia legacy se conserva plegada. El anfitrión recibe instrucciones para
explicar qué se completó, qué falta y quién debe actuar, sin pedir JSON al usuario.

La presentación de contexto, fuentes pendientes y diagnóstico evita mostrar
estructuras internas como recorrido principal. Las respuestas presentan una sola
vez las afirmaciones, conservando marcadores, pasajes, alcance parcial y límites.
El protocolo JSON y los gates de evidencia permanecen en el núcleo existente.

`docs/release-readiness.md` define el ensayo de primer uso, la ficha de evaluación
y las condiciones pendientes. El paquete se identifica como `0.2.0a2` para distinguirlo
del candidato anterior. La validación automática de esta revisión debe registrarse
por su propio commit; la comprensión por personas nuevas sigue sin evaluarse.
