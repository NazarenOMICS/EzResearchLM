# Registro de importación — M2 (regla 2 de reglas_benchmark.md)

Condición: EZresearchLM. Corrida: `ez-01569990fb414ed4` (proyecto `gold-set-benchmark`).

| Campo | Valor |
|---|---|
| Fuente | `src-radmacher-2005` |
| Motivo | Sin acceso abierto: la adquisición terminó en `routes_exhausted` (todas las rutas OA fallaron) |
| Archivo importado | `C:\Users\Administrator\Documents\Obsidian Vault\Research\Papers\radmacher_2005_ethambutol_cglutamicum.pdf` |
| Tamaño / páginas | 529 345 bytes, 10 páginas |
| SHA-256 | `cc39cb0dcbf40911725e7eb68fbe27709c90f440701fba666f078f8077b6d61c` |
| Copia en la corrida | `imports\cc39cb0dcbf40911725e7eb68fbe27709c90f440701fba666f078f8077b6d61c.pdf` |
| Momento de importación | 2026-10-08T00:26:20Z (2026-10-07 21:26:20 -03) |
| Comando | `ez rescue ez-01569990fb414ed4 --source src-radmacher-2005 --import <pdf> --origin-provider user_import` |
| Identidad confirmada | 2026-10-08T00:26:27Z, `--confirm-identity --reviewer host_agent` |
| Título (PDF, p. 1) | Ethambutol, a cell wall inhibitor of Mycobacterium tuberculosis, elicits L-glutamate efflux of Corynebacterium glutamicum |
| DOI (PDF, p. 1) | 10.1099/mic.0.27804-0 |
| Versión | Versión publicada: "Microbiology (2005), 151, 1359–1368", recibido el 2 de diciembre de 2004 |
| Cotejo externo | Crossref: mismo título, DOI, volumen 151, número 5, páginas 1359-1368, journal-article |
| Eventos en el journal | `pdf_import` (actor `user`, ejecutado por el anfitrión según la instrucción del usuario) e `identity_confirmed` (actor `host_agent`) en `events.jsonl` |

Los resultados de M2 deben informarse con esta importación y sin ella (regla 2.3).
