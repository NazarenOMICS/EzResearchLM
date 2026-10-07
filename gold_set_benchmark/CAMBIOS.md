# Cambios del gold set

## Versión 2.1 (2026-10-07)

1. **Se ejecutó la búsqueda de ausencia de M3** (2026-10-07 16:34, `busqueda_control_negativo.md`). PubMed dio 16, 4 y 4 resultados; Europe PMC, 53 y 18; RCSB PDB, 0 entradas de *C. glutamicum* con arabinosyltransferase y 4 entradas sin filtro de organismo (7BVE, 7BVC y 7BVF de *M. smegmatis* y *M. tuberculosis*; 5NR3 humana). Ningún resultado es una estructura de rayos X o crio-EM de la Emb de *C. glutamicum*. M3 pasa a estado EJECUTADA y queda confirmada como control negativo.
2. **`misiones.csv` y `lagunas_esperadas.csv`**: la fila M3 registra la fecha de corte 2026-10-07 y la evidencia de la búsqueda.
3. **`m3_busqueda.py`** guarda el organismo fuente de cada entrada del PDB y escribe el resumen de consola en UTF-8. En la ejecución del 2026-10-07 la impresión falló por un carácter "α" en cp1252 después de guardar `m3_resultados.json`; las consultas no se afectaron.
4. **Se retiraron los módulos sin uso de Anna's Archive** (`packages/ez/consent.py` y `academic_platforms/anna_archive.py`, commit `6b65d7e`).

Verificación mecánica de la versión 2.1, con los 8 textos locales, incluido Radmacher 2005: 22 pasajes ok, 0 fallas, 0 sin texto local, 1 prohibida sin pasaje en PDF (M3-P02, evidencia bibliográfica). Los 22 ok son los 17 de la versión 2 más los 5 de Radmacher 2005.

## Versión 2 (2026-10-07)

Decisiones tomadas en la revisión del gold set de la versión 1:

1. **Devlin et al. 2025 sale de `articulos_clave.csv`.** Es un distractor (ayuno de carbono en *M. tuberculosis*, no etambutol): contarlo como clave penalizaba a un sistema que correctamente no lo cita. Sigue evaluado como trampa en M2-P01. Ver `reglas_benchmark.md`, regla 4.
2. **Regla para Radmacher 2005.** Se permite importarlo con `ez rescue` en la condición EZresearchLM, registrando la importación, y los resultados de M2 se informan con y sin ella. Ver `reglas_benchmark.md`, regla 2.
3. **M3 cambia de pregunta.** La de la versión 1 (proteómica de *C. glutamicum* con etambutol) coincidía con M2-SQ4. La nueva pregunta trata de la estructura experimental de la Emb de *C. glutamicum*. **Su búsqueda de ausencia está pendiente** (`busqueda_control_negativo.md`). La búsqueda anterior se conserva como evidencia de M2 en `busqueda_m2_proteomica_etambutol.md`, y su script pasó a `anexo_textos_extraidos/busqueda_m2_proteomica.py`.
4. **Los textos completos extraídos dejan de estar en el repositorio.** Se reemplazan por la huella SHA-256 de cada página (`anexo_hashes_paginas.json`) y por `verificar_pasajes.py`, que coteja huellas y pasajes contra los textos locales. Los textos de la versión 1 siguen en el historial de git (commit `4c82539`); quitarlos de ahí requiere reescribir la rama.

Correcciones adicionales:

5. **M2-R07** precisa que el inmunoblot midió la fusión DivIVA-mCherry expresada desde el locus nativo.
6. **Dos lagunas pasan a `notas_corpus.md`**: los PDFs que solo contienen material suplementario y las unidades ilegibles por la extracción. Describen la carpeta, no la literatura, y ningún sistema puede declararlas.

Verificación mecánica de la versión 2, con los textos locales: 17 pasajes ok, 0 fallas, 5 pasajes de Radmacher 2005 sin texto en el repositorio (se verifican contra el PDF original), 1 prohibida sin pasaje en PDF (M3-P02, evidencia bibliográfica).

## Versión 1 (2026-10-07)

Construcción inicial: commit `4c82539`.
