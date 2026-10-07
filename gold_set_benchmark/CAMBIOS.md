# Cambios del gold set

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
