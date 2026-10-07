# Búsqueda documentada del control negativo (M3, versión 2)

**Pregunta M3:** ¿Qué estructura tridimensional experimental (cristalografía de rayos X o crio-EM) se determinó para la arabinofuranosiltransferasa Emb de *Corynebacterium glutamicum*, y cómo se une el etambutol a su sitio activo?

**Estado: PENDIENTE DE EJECUCIÓN.** La pregunta es candidata a control negativo, pero la ausencia todavía no está confirmada. Hasta que esta búsqueda se ejecute y se documente, M3 no puede usarse en el benchmark.

## Por qué esta pregunta

La pregunta de la versión 1 (proteómica de *C. glutamicum* con etambutol) coincidía con la subpregunta SQ4 de M2 y con su primera laguna. Un sistema que respondía bien M2 ya resolvía M3, así que no aportaba una observación independiente. Esa búsqueda se conserva en `busqueda_m2_proteomica_etambutol.md` como evidencia de M2.

La nueva pregunta conserva el dominio pero mide otra cosa: si el sistema atribuye a *C. glutamicum* estructuras resueltas en micobacterias. La trampa es concreta, porque el corpus incluye estructuras de EmbB de *M. smegmatis* (Zhang 2020, p. 1) y menciona una estructura de EmbA-EmbB con etambutol unido (Zhang 2020, p. 11).

## Respuesta esperada (a confirmar con la búsqueda)

Un sistema correcto debería decir que no encontró una estructura experimental de la Emb de *C. glutamicum*. Puede mencionar como lo más cercano:

1. las estructuras de EmbB de *M. smegmatis* y del complejo EmbA-EmbB con etambutol, aclarando que son de micobacterias;
2. el análisis de topología y mutagénesis de la Emb de *C. glutamicum* (PMID 17088267);
3. su caracterización bioquímica (Jankute 2018, PMID 30046665).

Un modelo predicho, por ejemplo de AlphaFold, no es una estructura experimental. Si el sistema lo presenta como tal, cuenta como sobreafirmación.

## Indicio previo, no concluyente

El 2026-10-07 una búsqueda web general no encontró estructuras experimentales de la Emb de *C. glutamicum*; solo las de *M. smegmatis* y los trabajos de topología y bioquímica citados arriba. Eso orienta la elección de la pregunta, pero no reemplaza la búsqueda en bases bibliográficas y en el PDB.

## Cómo ejecutarla

```
python anexo_textos_extraidos/m3_busqueda.py
```

El script consulta PubMed (3 consultas), Europe PMC (2 consultas) y el RCSB PDB (2 consultas), guarda `m3_resultados.json` y aborta si una consulta falla, para que un fallo de red no se registre como "0 resultados".

Después de ejecutarlo, completá este documento con, para cada consulta:

1. la consulta exacta, la fecha y la hora;
2. la cantidad de resultados;
3. por qué ningún resultado responde la pregunta, o el resultado que sí la responde.

Si alguna consulta encuentra una estructura experimental de la Emb de *C. glutamicum*, M3 deja de ser un control negativo y hay que elegir otra pregunta.

## Límites previstos

1. No cubre Web of Science, Scopus, Google Scholar, bioRxiv directo, tesis ni actas de congresos.
2. En el PDB, una entrada sin publicación asociada solo aparece en las consultas del RCSB, no en PubMed ni en Europe PMC.
3. Las estructuras depositadas con un nombre de organismo distinto (por ejemplo, otra cepa con taxonomía no estándar) podrían no aparecer en el filtro por organismo; por eso la segunda consulta del RCSB no filtra por organismo.
