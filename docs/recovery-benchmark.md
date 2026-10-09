# Protocolo de benchmark de recuperación

Estado: **piloto técnico; aceptación independiente y benchmark representativo
pendientes**. Este protocolo mide adquisición e identidad de fuentes. NotebookLM
sigue siendo el motor de evidencia y QA; recuperar un PDF no valida una respuesta
científica ni acredita un E2E autenticado.

## Piloto y alcance

El corpus público mínimo está en `benchmarks/recovery-pilot.json`: cinco obras
únicas conocidas públicamente y un control negativo de adenda que no debe
aceptarse como sustituto del artículo solicitado. Las cinco obras son el denominador
del piloto; el control se informa aparte. Esta selección sirve para comprobar el
procedimiento y encontrar fallos. No constituye un corpus representativo final ni
una aprobación de lanzamiento.

El runner es `scripts/benchmark_recovery.py`. La lectura y validación del corpus
sin `--execute` no contacta servicios:

```powershell
python scripts/benchmark_recovery.py --corpus benchmarks/recovery-pilot.json --output runs/refurbish-validation/recovery-pilot-20260920/
```

La ejecución autorizada de adquisición se solicita explícitamente:

```powershell
python scripts/benchmark_recovery.py --corpus benchmarks/recovery-pilot.json --output runs/refurbish-validation/recovery-pilot-20260920/ --execute
```

Conservar resultados y PDFs en esa carpeta privada, fuera de Git. No publicar
credenciales, cookies, rutas personales ni contenido de los archivos recuperados.
Los metadatos bibliográficos públicos y el protocolo sí pueden versionarse.

## Corpus y denominadores

Antes de ejecutar, congelar el corpus con su hash, el candidato o árbol de código,
sus hashes, presupuesto y proveedores habilitados. Registrar por obra la identidad
esperada, versiones aceptables y evidencia fechada de una ruta autorizada conocida.
El benchmark final debe cubrir disciplinas y rutas del alcance de soporte acordado;
las credenciales opcionales se declaran antes de medir.

Una obra elegible aporta como máximo un éxito. Cinco rutas para la misma obra no
son cinco obras. Reintentos, proveedores y documentos duplicados se registran
aparte. Mantener los fallos 403, timeouts, presupuesto agotado y errores del producto
en el denominador fijado; no eliminar casos por su resultado desfavorable. Conservar
exclusiones predefinidas y cualquier cambio de elegibilidad con fecha, motivo y
revisión, mostrando también el denominador original.

La tasa por proveedor usa su propio número de obras o intentos elegibles, indicado
explícitamente. No sustituye la tasa de recuperación por obra. El control negativo
no aumenta el denominador ni el numerador de recuperación: su resultado mide si se
evita aceptar un documento incorrecto.

## Estructura, identidad y revisión

Registrar tres resultados distintos:

1. **Estructura PDF:** archivo legible, páginas y comprobaciones técnicas. Este
   resultado no prueba la identidad bibliográfica.
2. **Identidad automática:** dictamen del verificador y sus motivos, conservando
   `needs_review` cuando corresponda. Encontrar un título o DOI citado dentro del
   PDF no demuestra que el archivo sea esa obra.
3. **Aceptación independiente:** cotejo humano registrado de título, autoría,
   identificador propio, tipo documental y versión contra el corpus congelado.
   Permanece pendiente hasta que un revisor independiente emita el dictamen; no se
   deduce del resultado automático ni de una revisión del anfitrión.

Una adenda, corrección o suplemento no sustituye al artículo, salvo que el corpus
haya pedido explícitamente ese documento. Conservar el archivo y la evidencia del
rechazo. El control del piloto debe detectar esa confusión aunque el documento
contenga título y DOI del artículo en sus referencias.

## Registro y lectura de resultados

Por intento, conservar obra, proveedor, URL, fecha, duración, estado o error,
procedencia, hash del archivo y dictámenes disponibles. Separar trabajo activo de
espera externa, recuperación automática de rescate manual, y primer intento de
reintentos posteriores. Una corrección del código genera una nueva ejecución;
conservar también el resultado anterior.

Informar números absolutos: obras elegibles, recuperadas con estructura válida,
identidad automática favorable, `needs_review`, rechazos, fallos y aceptaciones
independientes. Mostrar recuperaciones automáticas sobre el denominador original
como resultado técnico preliminar. Mientras falte revisión independiente, la tasa
de aceptación queda pendiente; no presentar esa ausencia como cero recuperaciones
ni presentar el resultado automático como aceptación independiente.

El umbral propuesto de lanzamiento es ≥90% de obras curadas con ruta autorizada
conocida, recuperadas con identidad y versión aceptadas, según
[el protocolo de beta](beta-and-release.md). Evaluarlo requiere el corpus
representativo acordado y su revisión independiente. Incluso cinco éxitos de cinco
en este piloto no acreditan ese criterio de lanzamiento.

## Resultado del piloto del 2026-09-20

Se ejecutó el corpus congelado sobre el paquete instalado `0.2.0a2`, con Python
3.11, presupuesto de 90 segundos por caso y un intento por URL. El informe privado
`runs/refurbish-validation/recovery-pilot-20260920/report.json` conserva los hashes
del código, runner y archivos, junto al corpus usado en `corpus.json`. El SHA-256
del corpus fue
`8701188ff6dad97667c7a926d23ba52afe6f405aef6b7d5e3599f155bff60071`.

| Medición | Resultado observado |
|---|---|
| Obras elegibles intentadas | 5 de 5; ninguna excluida |
| PDFs estructuralmente válidos | 5 de 5 |
| Identidades automáticas favorables | 3 de 5 |
| Identidades pendientes de revisión | 2 de 5 |
| Aceptación independiente y tasa aceptada | Pendientes; campos `null` en el informe |
| Control negativo de adenda | 1 retenido en `needs_review`; 0 aceptaciones falsas en ese único control |

Las rutas finales registradas fueron OpenAlex para `fair-doi`, CORE para
`ecology-doi` y descarga directa para `seaborn-publisher`, `research-interviews` y
`scikit-jmlr`. Estos dos últimos quedaron pendientes de revisión de identidad.
El control de adenda se descargó por ruta directa: su estructura era válida, pero
el verificador no lo aceptó automáticamente como el artículo solicitado.

No se configuraron las credenciales opcionales de Unpaywall ni CORE; Anna estuvo
deshabilitada. Los intentos conservan también respuestas HTML, ausencia de correo
para Unpaywall, timeouts y proveedor no disponible. La procedencia CORE registrada
no acredita el funcionamiento de su ruta autenticada.

Estos resultados pertenecen a la línea base instalada `0.2.0a2`; no se atribuyen al
candidato `0.2.0a3` en desarrollo. No hubo QA de NotebookLM ni E2E autenticado en
este piloto. La revisión independiente sigue pendiente y la ausencia de falsos
positivos en un solo control no estima su frecuencia general. El piloto no acredita
el umbral de recuperación de lanzamiento ni reemplaza el benchmark representativo.
