# Benchmark en vivo de EZresearchLM v6c

## Preparación

- Fecha: 2026-10-08, zona horaria America/Montevideo.
- Rama: `claude/laughing-noether-fcf794`, actualizada desde remoto a partir de `f7e3def`.
- Instalación editable con extra `notebooklm`: correcta; `notebooklm-py==0.8.0`.
- `ez setup --check --json`: `unpaywall_configured=true`, `notebooklm_installed=true`, `can_notebook_qa=true` después del login.
- `python scripts/validate.py`: OK; 17 + 4 pruebas pasaron, con la advertencia prevista del auditor de citas.
- No se usaron Anna's Archive ni Sci-Hub. No se leyeron cookies, tokens ni `.env`.

## A. Investigación desde cero

- Proyecto: `prueba-v6c`.
- Corrida: `ez-fc873d31c13f4dd8`.
- Pregunta: “¿Qué proteínas y procesos de Corynebacterium glutamicum se sabe que son afectados por el etambutol, y qué se desconoce sobre su efecto proteómico global?”
- Plan: `direct`, 6 búsquedas (PubMed, Europe PMC y OpenAlex), 4 preguntas QA, máximo 15 fuentes incluidas.
- Resultado final: `answer.status=complete`, integridad `pass`, 15 fuentes cribadas y 4 preguntas QA procesadas.
- PDFs adquiridos: 9 en total: 7 por adquisición automática y 2 por rescate local.
- Fallos iniciales de adquisición: 8. Tras el rescate, permanecen 6 fuentes `routes_exhausted` sin PDF en el corpus.
- Tiempo total final: 600,5 segundos, aproximadamente 10,0 minutos. El primer pase hasta la entrega directa tomó 316,1 segundos (5,3 minutos); el resto corresponde a la reanudación, subida de los rescates y QA repetida.

## B. Fallos de adquisición y rutas registradas

Las rutas se transcriben solo como estados y proveedores; no se incluyen pasajes ni textos completos.

| Fuente | Estado final | Routes registradas en `corpus_exclusions` |
|---|---|---|
| `src-dd27d46c8ad656fd7ff0` | fallida | No registradas en `corpus_exclusions` |
| `src-3e961d5f194ce3542d84` | fallida | No registradas en `corpus_exclusions` |
| `src-5f6fbffd9d332d45e34a` | fallida | No registradas en `corpus_exclusions` |
| `src-74ac6cc1bf67f4fcc2e1` | fallida | No registradas en `corpus_exclusions` |
| `src-dc92ee8173b378d2f71a` | fallida | No registradas en `corpus_exclusions` |
| `src-d2a127d4d7d7e4b18d27` | fallida | `core: rate_limited`; `doi: tls_downgrade` |
| `src-a56507ba20bddc2779ec` | rescatada y en corpus | Inicialmente: `direct: access_denied`; `pmc_cloud: pmc_not_in_public_dataset`; `doi: tls_downgrade`; `openalex: html_instead_of_pdf`; `openaire: circuit_open`; `unpaywall: access_denied` |
| `src-cb2002fac4b49f7196fc` | rescatada y en corpus | Inicialmente: `doi: access_denied`; `core: network_timeout` |

## C. Rescate local

- Carpeta usada: `C:\Users\Administrator\.ezresearch\rescue-v6c`.
- `ez rescue <corrida> --import-folder <carpeta> --json`: `imported=0`, `unassigned=2`, `ambiguous=0`; el matching automático no pudo asignar los nombres de archivo.
- Se importaron explícitamente y se confirmó su identidad como `host_agent`:
  - `src-a56507ba20bddc2779ec`
  - `src-cb2002fac4b49f7196fc`
- Después de `ez continue`, ambos quedaron `validation_status=valid`, `identity_status=verified`, `notebook_status=ready` y entraron al corpus; el `corpus_hash` cambió.

## D. Entrega directa

- Afirmaciones entregadas: 87.
- Afirmaciones con `merged_from`: 0.
- Afirmaciones en el anexo: 67.
- Afirmaciones principales fuera del anexo: 20.
- `uncited_statements`: 39.
- Afirmaciones retenidas: 0.

Este informe conserva métricas, estados, identificadores y rutas de adquisición, pero no pasajes ni textos completos de afirmaciones. Las corridas y sus artefactos permanecen fuera del repositorio; el commit contiene únicamente este informe.
