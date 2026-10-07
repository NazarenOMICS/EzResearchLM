# Notas sobre el corpus del proyecto

Estos puntos describen limitaciones de la carpeta de PDFs o de la extracción de texto. No son lagunas de la literatura: ningún sistema evaluado puede conocerlas, así que no entran en la métrica de honestidad de lagunas. Estaban en `lagunas_esperadas.csv` en la versión 1.

## Contenido de cinco PDFs de la carpeta: solo contienen material suplementario o checklists, sin el artículo (Blevins 2024, Greaves 2023, Garaeva 2026, Tan/Zhao 2020 EmbB y FtsB-PerM 2025).

Causa registrada en v1: `fuera_de_la_bibliografia`.

Evidencia: Primera página de cada PDF: 'Supplementary Figures', 'Supplementary Materials' o 'MDAR Checklist' (ver inventario).

## Concentraciones exactas de etambutol en Radmacher 2005 y en partes de Schubert 2017: la extracción de texto pierde el símbolo µ y las unidades son ambiguas.

Causa registrada en v1: `datos_contradictorios`.

Evidencia: Radmacher p. 3 dice '500 mg EMB ml 21' y p. 6 dice '500 mg EMB l 21' para el mismo experimento; Schubert p. 3 alterna '1 mg · ml' y '1 /H9262g·m l'. Hay que leerlas en el PDF original.

