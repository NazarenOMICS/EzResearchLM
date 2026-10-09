# Línea base del refactor EZ

Fecha: 2026-09-16. Rama: `codex/ez-refurbish`, desde `964fa4d`.

Antes de implementar se conservaron los 13 archivos modificados y todas las
entradas sin seguimiento del usuario. Una copia de 22 archivos de trabajo y su
manifiesto SHA-256 está en `runs/refurbish-baseline-20260916/`, ignorada por Git.
No contiene PDFs ni credenciales. No se hicieron commits, reset, clean ni stash.

La validación anterior al refactor pasó 18 pruebas de adquisición y 2 de
NotebookLM. Los 11 scripts PowerShell pasaron el parser. Python local: 3.11.15.
La autenticación actual y el funcionamiento E2E no se deducen de esos resultados.

Las reparaciones locales de trazabilidad, revisión previa y rutas son parte de
esta línea base. Las siguientes modificaciones se aplican sobre ellas, no sobre
una copia de HEAD que las omita. La copia local permite revisar/revertir cada
archivo sin descartar el trabajo anterior.

Estado de lanzamiento: E2E autenticado pendiente; beta y lanzamiento no aprobados.
