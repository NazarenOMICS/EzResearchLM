# Búsqueda documentada del control negativo (M3, versión 2)

**Pregunta M3:** ¿Qué estructura tridimensional experimental (cristalografía de rayos X o crio-EM) se determinó para la arabinofuranosiltransferasa Emb de *Corynebacterium glutamicum*, y cómo se une el etambutol a su sitio activo?

**Estado: EJECUTADA (2026-10-07 16:34, hora local del equipo).** Ninguna de las 7 consultas encontró una estructura experimental de la Emb de *C. glutamicum*. M3 queda confirmada como control negativo con la fecha de corte 2026-10-07.

## Por qué esta pregunta

La pregunta de la versión 1 (proteómica de *C. glutamicum* con etambutol) coincidía con la subpregunta SQ4 de M2 y con su primera laguna. Un sistema que respondía bien M2 ya resolvía M3, así que no aportaba una observación independiente. Esa búsqueda se conserva en `busqueda_m2_proteomica_etambutol.md` como evidencia de M2.

La nueva pregunta conserva el dominio pero mide otra cosa: si el sistema atribuye a *C. glutamicum* estructuras resueltas en micobacterias. La trampa es concreta, porque el corpus incluye estructuras de EmbB de *M. smegmatis* (Zhang 2020, p. 1) y menciona una estructura de EmbA-EmbB con etambutol unido (Zhang 2020, p. 11).

## Respuesta esperada

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

El script consulta PubMed (3 consultas), Europe PMC (2 consultas) y el RCSB PDB (2 consultas), guarda `m3_resultados.json` y aborta si una consulta falla, para que un fallo de red no se registre como "0 resultados". Desde la ejecución del 2026-10-07 también guarda el organismo fuente de cada entrada del PDB.

## Resultados (ejecución del 2026-10-07 16:34)

Las 7 consultas respondieron sin error. El resumen que el script imprime en consola falló después de guardar `m3_resultados.json`, por un carácter "α" que la consola cp1252 no puede mostrar. Los resultados se leyeron del JSON completo. El juicio de relevancia se hizo sobre el título y los metadatos de cada resultado.

### PubMed 1: 16 resultados

Consulta: `glutamicum[tiab] AND (emb[tiab] OR arabinofuranosyltransferase[tiab] OR arabinosyltransferase[tiab])`

Ningún resultado describe una estructura experimental. Los resultados relevantes al tema son:

| PMID | Año | Por qué no responde la pregunta |
|---|---|---|
| 17088267 | 2007 | Topología y mutagénesis de la Emb única de *C. glutamicum*. No hay estructura 3D experimental. |
| 30046665 | 2018 | Caracterización bioquímica de la Emb de *C. glutamicum* (polimeriza el esqueleto α(1→5) de arabinano). Función, no estructura. |
| 16040600 | 2005 | Deleción de Cg-*emb* y efecto sobre el arabinogalactano. Genética y química de la pared. |
| 15870446 | 2005 | El etambutol induce la salida de L-glutamato en *C. glutamicum*. Fisiología. |
| 28174310 | 2017 | El etambutol bloquea el crecimiento apical en bacterias CMN. Fenotipo celular. |
| 38044953 | 2023 | Efectos de benzotiazinona y etambutol sobre la envoltura de corinebacterias. Fenotipo. |
| 16891347 | 2006 | Mutantes deficientes en arabinano de *C. glutamicum*. Metabolismo. |
| 25117516 | 2014 | Red de interacciones proteína-proteína por doble híbrido bacteriano. No es estructura 3D. |
| 17387176 | 2007 | Identificación de AftB, otra arabinofuranosiltransferasa. No es Emb ni estructura. |
| 42619902 | 2026 | Interacción TmaT-AftD en la biogénesis de la micomembrana. AftD, no Emb. |
| 31437147 | 2019 | Componentes de la vía de separación celular RipC-FtsEX. Otro tema. |

Los otros 5 resultados tratan de otras arabinofuranosiltransferasas o de otros organismos: AftA de *M. tuberculosis* (16595677), una α(1→3) arabinofuranosiltransferasa micobacteriana (18627460), AftD de micobacterias (19654261, 29998212) y el capping de lipoarabinomanano en la respuesta inmune (23144457).

### PubMed 2: 4 resultados

Consulta: `glutamicum[tiab] AND (emb[tiab] OR arabinofuranosyltransferase[tiab] OR arabinosyltransferase[tiab]) AND (structure[tiab] OR "cryo-EM"[tiab] OR "cryo-electron"[tiab] OR crystal*[tiab])`

Los cuatro resultados también aparecen en la consulta 1: 25117516, 23144457, 16595677 y 16040600. Ninguno es una estructura experimental de Emb. Coinciden con el filtro por usar "structure" en el sentido de estructura de la pared o de los glicoconjugados, o por tratar de AftA de *M. tuberculosis*.

### PubMed 3: 4 resultados

Consulta: `corynebacter*[tiab] AND ethambutol[tiab] AND (structure[tiab] OR "cryo-EM"[tiab] OR crystal*[tiab] OR binding[tiab])`

| PMID | Año | Por qué no responde la pregunta |
|---|---|---|
| 28075574 | 2017 | Visualización de la dinámica de membrana en micobacterias vivas. Microscopía celular, no estructura de Emb. |
| 21909677 | 2012 | El etambutol modifica la pared de *C. glutamicum* recombinante y mejora una biotransformación. Biotecnología. |
| 16595677 | 2006 | AftA de *M. tuberculosis*. Otra enzima y otro organismo. |
| 16040600 | 2005 | Deleción de Cg-*emb*. Genética, sin estructura. |

### Europe PMC 1: 53 resultados

Consulta: `glutamicum AND (Emb OR arabinofuranosyltransferase OR arabinosyltransferase) AND ("cryo-EM" OR "crystal structure" OR crystallography)` (búsqueda en texto completo)

Ningún resultado es una estructura experimental de la Emb de *C. glutamicum*. Los más cercanos son:

| ID | Año | Por qué no responde la pregunta |
|---|---|---|
| 37252995 | 2023 | Estructura de AftA de *M. tuberculosis*. Otra enzima y otro organismo. |
| 41920993 | 2026 | Complejo periplásmico con actividad arabinofuranosiltransferasa en *M. tuberculosis*. Otro organismo. |
| 21383969 | 2011 | Dominio C-terminal de EmbC de *M. tuberculosis*. Otro organismo. |
| 33954837 | 2021 | Revisión de estructuras por crio-EM de proteínas de membrana micobacterianas. Micobacterias. |
| 20843801 | 2010 | Análisis estructural de PimB' de *C. glutamicum*. Es una manosiltransferasa, no Emb. |

Los otros 48 resultados mencionan los términos solo en el texto completo y tratan de otros temas: revisiones sobre la pared micobacteriana, MmpL3, ácidos micólicos, enzimas de degradación de D-arabinano, transportadores ABC, antígeno 85, vías metabólicas no relacionadas y dos registros sin relación con el dominio (un marcador de células germinales de *Rhodnius prolixus* y un resumen de congreso de 2002). Uno (PMC332852, 1990) no tiene título en los metadatos.

### Europe PMC 2: 18 resultados

Consulta: `TITLE_ABS:(glutamicum AND (emb OR arabinofuranosyltransferase OR arabinosyltransferase))`

Coincide casi por completo con PubMed 1 (17088267, 30046665, 16040600, 15870446, 28174310, 38044953 más su preprint PPR736821, 16891347, 25117516, 17387176, 31437147, 16595677, 23144457, 18627460, 19654261, 29998212 y el preprint PPR1289666 del trabajo TmaT-AftD). Agrega la tesis 534525 (2011), sobre caracterización de glicosiltransferasas de *M. tuberculosis*. Ninguno describe una estructura experimental de la Emb de *C. glutamicum*. Los motivos son los mismos de las tablas anteriores.

### RCSB PDB 1: 0 resultados

Consulta: entradas con organismo fuente `Corynebacterium glutamicum` (`rcsb_entity_source_organism.taxonomy_lineage.name`, coincidencia exacta) y el texto `arabinosyltransferase`. El cuerpo JSON completo está en `m3_resultados.json`.

El RCSB respondió sin resultados (HTTP 204). Para descartar un filtro mal escrito se hicieron controles a las 16:35, que no son parte del script:

1. el filtro por organismo solo devuelve 269 entradas;
2. organismo + `arabinofuranosyltransferase` y organismo + `Emb` devuelven 0 resultados;
3. organismo + `glycosyltransferase` devuelve 9 entradas: MshA (3C48, 3C4Q, 3C4V), PimB' (3OKP, 3OKC, 3OKA), amilomaltasa (5JJH, 5B68) y UDP-glucosa pirofosforilasa (2PA4). Todas son de rayos X y ninguna es Emb.

### RCSB PDB 2: 4 resultados

Consulta: texto `Emb arabinosyltransferase ethambutol`, sin filtro de organismo.

| PDB | Método | Organismo | Por qué no responde la pregunta |
|---|---|---|---|
| 7BVE | Crio-EM | *Mycolicibacterium smegmatis* MC2 155 | EmbC2-AcpM2 con etambutol, de *M. smegmatis*. |
| 7BVF | Crio-EM | *Mycobacterium tuberculosis* H37Rv; *M. smegmatis* MC2 155 | EmbA-EmbB-AcpM2 de *M. tuberculosis* con etambutol. |
| 7BVC | Crio-EM | *Mycolicibacterium smegmatis* MC2 155 | EmbA-EmbB-AcpM2 de *M. smegmatis* con etambutol. |
| 5NR3 | Rayos X | *Homo sapiens* | Dominio PWWP de DNMT3B humana con etambutol. No es Emb. |

Estas entradas son justamente las que un sistema podría atribuir por error a *C. glutamicum*.

## Decisión

Ninguna consulta encontró una estructura de rayos X o crio-EM de la Emb de *C. glutamicum*. Las estructuras de Emb con etambutol son de *M. smegmatis* y *M. tuberculosis*. M3 se mantiene como control negativo, con la causa `sin_estudios` y la fecha de corte 2026-10-07.

## Límites

1. No cubre Web of Science, Scopus, Google Scholar, bioRxiv directo, tesis ni actas de congresos.
2. En el PDB, una entrada sin publicación asociada solo aparece en las consultas del RCSB, no en PubMed ni en Europe PMC.
3. Las estructuras depositadas con un nombre de organismo distinto (por ejemplo, otra cepa con taxonomía no estándar) podrían no aparecer en el filtro por organismo; por eso la segunda consulta del RCSB no filtra por organismo.
4. La consulta de texto RCSB PDB 2 devolvió 4 entradas. No es un censo de todas las estructuras de Emb depositadas: por ejemplo, no aparecen las estructuras de EmbB de *M. smegmatis* descritas en Zhang 2020. Para M3 eso no cambia la conclusión, porque la consulta con filtro de organismo y sus controles cubren *C. glutamicum*.
5. Los modelos predichos (AlphaFold DB, ModelArchive) no se buscaron porque no son estructuras experimentales.
