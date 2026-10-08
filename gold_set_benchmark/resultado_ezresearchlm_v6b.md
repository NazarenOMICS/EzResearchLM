# Benchmark en vivo de EZresearchLM v6b

## Preparación

- Fecha: 2026-10-08, zona horaria America/Montevideo.
- Rama: `claude/laughing-noether-fcf794`.
- Pregunta M2: “¿Qué proteínas y procesos de Corynebacterium glutamicum se sabe que son afectados por el etambutol, y qué se desconoce sobre su efecto proteómico global?”
- Instalación editable con extra `notebooklm`: correcta; `notebooklm-py==0.8.0`.
- `python scripts/validate.py`: OK; 17 + 4 pruebas pasaron, con la advertencia prevista del auditor de citas.
- No se usaron Anna's Archive ni Sci-Hub. No se leyeron cookies, tokens ni `.env`.

## A. Investigación desde cero

- Corrida: `ez-b1b5387785bb40b2`.
- Plan: `direct`, 6 búsquedas (PubMed, Europe PMC y OpenAlex), 4 preguntas QA, máximo 15 fuentes cribadas.
- Resultado: `answer.status=complete`; 15 fuentes incluidas; 49 candidatos decididos.
- PDFs descargados: 10.
- Descargas fallidas: 5, todas `routes_exhausted` y quedaron como `manual_needed`.
- `processing_stuck`: 0.
- Consultas NotebookLM: 4.
- Afirmaciones entregadas: 84.
- `uncited_statements`: 40.
- `report.md` empieza con “Lo central”: no; empieza con `# Informe de evidencia`.

Minutos de reloj, calculados desde `at` en `events.jsonl`: plan 0,6; descubrimiento 0,2; cribado/importación 0,4; adquisición 0,7; subida 1,3; readiness 0,2; QA 4,2; total 6,5.

## B. M2 directo y verificado

La primera corrida B fue `ez-9ec4c0a8ef9f4813`; su entrega directa produjo 107 afirmaciones y la verificación retuvo 3. Para registrar C correctamente antes de verificar, se repitió la actualización directa como `ez-d65b6ef28a304e90`, conservando el mismo proyecto, pregunta, notebook y fuentes verificadas.

### Directo

- Afirmaciones entregadas: 103.
- Afirmaciones con `merged_from`: 0.
- Consultas QA: 5.
- Tiempo de reloj hasta la entrega directa: 5,8 minutos.
- Existe `direct/report.md`: sí.

### Verificación

- `ez continue <corrida> --verify --json`: completado.
- Afirmaciones entregadas después de verificar: 8.
- Afirmaciones retenidas: 2.
- Motivos: 2 `verdict_partial`.
- Consultas extra de verificación: 2.
- Tiempo de verificación: 5,5 minutos.
- Tiempo acumulado de la corrida repetida, incluyendo verificación: 12,9 minutos.

## C. Precisión del modo directo

- Muestra: 20 afirmaciones seleccionadas con `random.seed(42)` desde `direct/answer.json`.
- Juicios registrados con `ez verify`: 20.
- Respaldadas: 18.
- Parciales: 2.
- No respaldadas: 0.
- La muestra completa con pasajes y PDF quedó fuera del repositorio, en `EZresearchLM-scratch-v6b/muestra_precision.md`.

## Límites de lectura

Este informe conserva métricas y estados, no pasajes ni textos completos de afirmaciones. Las corridas y sus artefactos permanecen fuera del repositorio; el commit contiene únicamente este informe.
