# Plan de refactor v6: menos capas, menos espera

> Registro histórico. El plan vigente es `docs/roadmap.md`.

Fecha: 2026-10-08. Base: `gold_set_benchmark/resultado_ezresearchlm_v5.md`
(corrida en vivo del commit `0298ccf`).

## 1. Diagnóstico

1. NotebookLM dictaminó `supported` en las 29 afirmaciones propuestas (15 en M1,
   14 en M2). EZ entregó 4.
2. 21 de las 25 retenciones fueron `scope_not_sufficient`: una afirmación fallida
   marcaba su subpregunta como insuficiente y arrastraba a todas las demás de esa
   subpregunta (`engine.py`, `finalize`). En M2 una sola falla retuvo 13.
3. 4 retenciones fueron `verification_foreign_source`: la verificación citó otro
   PDF del corpus, verificado, distinto del citado en la QA (`audit.py`,
   `batch_verdicts`).
4. Las dos revisiones del agente fueron rechazadas por asignar una subpregunta que
   no correspondía a la pregunta QA de la afirmación. Cada rechazo es un turno más.
5. `--update` reutiliza PDFs pero crea un notebook nuevo, vuelve a subir todo y
   espera el procesamiento (`context.py`, `reuse_sources`). La cuenta del usuario
   ya acumula 86 notebooks.
6. Descarga, búsqueda y subida corren en serie, con 600 s por fuente y 3 intentos
   por ruta por defecto.
7. Hecho verificado en el código de `notebooklm-py==0.8.0` (`cli/chat_cmd.py`):
   `ask` sin `--new` continúa la conversación más reciente del notebook. Todas las
   preguntas de una corrida, incluida la verificación, comparten historial.

## 2. Evaluación: reutilizar notebooks

**Viabilidad.** Es viable. Cada consulta de EZ ya pasa `--source` con los IDs de
su propio corpus, de modo que un notebook con fuentes de otras corridas del mismo
proyecto no cambia qué fuentes puede citar NotebookLM. La identidad de una fuente
remota se reconcilia por su título determinista `<source_id>-<sha256[:12]>.pdf`,
que no depende de la corrida.

**Riesgos y mitigación.**

1. Historial compartido: con un notebook por proyecto, la primera pregunta de una
   corrida nueva continuaría la conversación de la anterior. Mitigación: cada
   consulta se hace con `--new`, que borra la conversación previa del notebook y
   empieza una limpia. EZ ya guarda localmente cada respuesta con su recibo, así
   que no se pierde evidencia. Además, cada pregunta queda independiente, también
   dentro de una misma corrida. Requiere validación en vivo (canary).
2. Límite de 50 fuentes por notebook en el plan gratuito: si el corpus nuevo no
   entra, EZ abre otro notebook del proyecto.
3. Deriva remota: la comprobación se restringe a lo que importa. Las fuentes de la
   corrida deben estar presentes y listas; las fuentes ajenas solo se aceptan si
   el registro del proyecto las conoce.
4. Dos corridas subiendo a la vez: el registro del proyecto se modifica bajo un
   bloqueo de archivo.
5. Notebook borrado a mano: si el notebook registrado no existe, se crea otro.
6. Desactivación: `EZ_NOTEBOOK_REUSE=0` vuelve a un notebook por corrida.

**Decisión.** Implementar.

## 3. Fases

### Fase 1. Dejar de tirar evidencia

1. Retención por afirmación: una afirmación verificada se entrega aunque otra de su
   subpregunta falle. La subpregunta queda como parcial. Solo las políticas de
   fuente (`hard_block` ausente, revisión pendiente) retienen subpreguntas enteras.
2. `answer.status` es `partial` cuando hay afirmaciones entregadas aunque ninguna
   subpregunta esté completa.
3. La verificación acepta citas a cualquier fuente del corpus verificado y las suma
   como referencias.
4. La revisión se corrige sola en vez de rechazarse:
   1. subpreguntas fuera de la QA se recortan a las de la QA;
   2. números de cita sin pasaje se descartan si queda al menos uno.

   Cada corrección queda en `review_adjustments`.

### Fase 2. Un notebook por proyecto

1. Registro `projects/<proyecto>/notebooks.json` en la carpeta de corridas.
2. La subida reutiliza el notebook del proyecto, sube solo los PDFs que falten y no
   espera procesamiento de los ya listos.
3. Las consultas usan `--new`.
4. El canary comprueba `--new`.

### Fase 3. Modo directo

1. `plan.delivery`:
   1. `direct`, el valor por defecto para contratos nuevos, entrega las oraciones
      de NotebookLM con sus citas y pasajes nativos, sin revisión del agente ni
      segunda consulta;
   2. `verified` conserva el flujo actual, para redactar con `ez draft`.
2. En modo directo, tras la QA, EZ arma `answer.json` y `report.md` automáticamente.
   Una revisión enviada después sigue el camino verificado.

### Fase 4. Velocidad de la primera corrida

1. Búsquedas y descargas en paralelo (hasta 6), con los eventos del registro
   escritos en orden desde el hilo principal.
2. Valores por defecto nuevos: 120 s por fuente y 2 intentos por ruta.
3. Espera interna del procesamiento de NotebookLM (hasta 4 min, cada 10 s) antes de
   pausar con `waiting_on_processing`.

### Fase 5. Documentación y validación

1. Guía del operador, guía de usuario, README y prompt de validación local.
2. Pruebas offline de cada fase.
3. Pendiente de validación en vivo:
   1. canary con `--new`;
   2. M2 en modo directo y en modo verificado sobre el notebook del proyecto;
   3. tiempo de reloj por etapa.

### Fase 6. Ajustes tras la corrida en vivo v6

Base: `gold_set_benchmark/resultado_ezresearchlm_v6.md` (M2 directo: 102 afirmaciones
en 7 min con 5 consultas; verificado: 9 de 10; un PDF atascado en `PREPARING`).

1. PDF atascado: tras la espera, si faltan como máximo 1 de cada 5, EZ sigue sin ellos
   (`processing_stuck`) y los vuelve a comprobar sin esperar en la próxima continuación.
2. Entrega directa más legible: oraciones casi idénticas entre respuestas se unen y el
   informe empieza por "Lo central" (las afirmaciones respaldadas por más fuentes).
3. `ez continue --verify [IDS]`: verificación sin escribir JSON; la entrega directa
   queda en `direct/`.
4. Tiempos explicados al usuario: cada pregunta tarda alrededor de un minuto, como en la
   web de NotebookLM; el estado indica cuántas preguntas quedan.

## 4. Estado

Fases 1 a 6 implementadas y validadas offline (`scripts/validate.py`). La corrida en
vivo v6 validó las fases 1 a 4; falta validar en vivo la fase 6, medir la precisión
del modo directo y medir una investigación desde cero.

## 5. Fuera de alcance

1. Consultas paralelas a NotebookLM: con `--new` cada consulta borra la
   conversación anterior del notebook, así que en un mismo notebook deben ir en
   serie.
2. Subidas paralelas: complican la reconciliación ante cortes y, con notebook por
   proyecto, dejan de ser el cuello de botella.
