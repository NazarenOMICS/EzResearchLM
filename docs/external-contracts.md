# Fronteras externas verificadas durante el refactor

Fecha de inspección: 2026-09-17. Estos contratos describen adaptadores, consultas de
metadatos y las descargas reales indicadas. El recorrido autenticado interno se
documenta por separado en `refurbish-progress.md`; no equivale a aprobación de release.

- **NotebookLM:** se inspeccionó el paquete local `notebooklm-py 0.8.0`, incluyendo
  el serializador de `ask --json` y los tipos `AskResult`/`ChatReference`. El adaptador
  utiliza `answer`, `references`, `source_id`, `citation_number` y `cited_text`.
  `create`, `source add` y `source list` mantienen IDs explícitos. No se usa `ask --new`,
  que en esta versión elimina la conversación anterior. La compatibilidad efectiva
  de create/upload/list/ask se comprobó en la corrida autenticada interna. El servicio
  emite citas agrupadas y por rango, y puede devolver citas sin pasaje. La revisión
  entrega únicamente afirmaciones con pasajes verificables. El dictamen de respaldo
  usa `EZ_VERDICT` / `EZ_RATIONALE`: el formato JSON en bloque de código devolvió
  referencias vacías y fue retenido. La nueva consulta devolvió citas nativas con pasajes.
  Las anclas sin pasaje solo se resuelven cuando una cita textual de la propia QA
  aparece una vez en `source fulltext` de la misma fuente; se preservan ambos
  originales y un recibo del cotejo. Para subidas, el nombre real del archivo se
  prepara de forma determinista: `--title` por sí solo no determinó el título remoto.
- **OpenAIRE:** el adaptador usa Graph API v3, `/research-products?pid=...`, y filtra
  DOI exacto e instancias con `accessRight.code=c_abf2`; conserva URLs, repositorio,
  licencia y versión disponible. El endpoint respondió HTTP 200 en un probe de
  metadatos. Referencia: [Graph API](https://graph.openaire.eu/docs/apis/graph-api/).
- **CORE:** se comprobó HTTP 200 en `/v3/search/works/`; la respuesta contiene
  `results`, `doi`, `downloadUrl`, `sourceFulltextUrls` y enlaces `outputs`.
  El adaptador acepta solamente obras con DOI coincidente. La clave opcional
  `EZRESEARCH_CORE_API_KEY` se envía únicamente al host de la API, no a repositorios
  de descarga ni a redirecciones externas. Referencia: [CORE API](https://core.ac.uk/services/api).
- **PMC:** el servicio OA anterior fue retirado en agosto de 2026. Se sustituyó
  por el bucket público `pmc-oa-opendata`, consultando sus prefijos por PMCID y
  metadatos por versión. El adaptador conserva licencia, tipo de versión y checksum
  esperado; no presupone que la versión más alta sea la preferida. Varias versiones
  quedan para revisión si el contrato no selecciona `pmc_version`. Las diferencias
  de checksum impiden aceptar el PDF. La prueba real con `PMC4792175.1` descargó un
  PDF estructuralmente válido y confirmó el checksum; su DOI extraído con espacios
  requirió cotejo del anfitrión, sin presentarlo como identidad automática aprobada.
  Fuentes oficiales: [retiro del servicio OA](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/),
  [servicio Cloud](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/),
  [estructura y metadatos](https://pmc-oa-opendata.s3.amazonaws.com/README.txt).
- **OpenAlex / Unpaywall / Europe PMC:** las ubicaciones alternativas se
  conservan aunque exista una URL anterior. Unpaywall sin email registra omisión,
  no un intento inventado. Los paquetes PMC antiguos con más de un PDF necesitan
  identidad inequívoca; no se elige por orden alfabético. Quedan pendientes los casos reales
  de recuperación del conjunto curado y cuotas/credenciales aplicables a beta.
- **Windows:** el supervisor usa Job Objects con `KILL_ON_JOB_CLOSE`, sin permisos
  de escape, para evitar procesos hijos huérfanos. Se probó timeout y salida normal
  del padre con un descendiente que intentaba escribir después. Referencia:
  [Job Objects de Microsoft](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

Los límites de proveedores, autenticación y formatos pueden cambiar. Los fallos se
conservan como fallos; una búsqueda que devuelve vacío tras un error registrado no
se considera una consulta satisfactoria sin resultados. No se incluyen credenciales,
cookies, PDFs reales ni exportaciones de NotebookLM en este documento.

## Canary de recuperación pública

Se solicitó una sola obra, DOI `10.1038/sdata.2016.18`. DOI, OpenAlex, Unpaywall
y OpenAIRE llevaron al PDF público del editor; PMC Cloud entregó otra representación
del mismo artículo, con checksum oficial y revisión explícita de identidad.
Europe PMC devolvió 403 en la descarga desde este equipo: se respetó el bloqueo.
Estas rutas repetidas no equivalen a cinco obras independientes ni a un benchmark.

CORE expuso un fallo relevante: sus metadatos asociaron a la obra un PDF de dos
páginas que era una adenda, DOI `10.1038/s41597-019-0009-6`. El verificador anterior
aceptaba el título y el DOI original citados dentro de ella. Se corrigió para retener
avisos de corrección/adenda y encabezados con identificadores contradictorios en
`needs_review`; la revisión del anfitrión rechazó ese archivo como sustituto.
La misma comprobación se aplica al elegir entre miembros de archivos PMC históricos.
Los resultados originales se conservan, junto a `identity-recheck.json` y una prueba
de regresión sintética. No se cuenta CORE como recuperación válida de esta obra.
