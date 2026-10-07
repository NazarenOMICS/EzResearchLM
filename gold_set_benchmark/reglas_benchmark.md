# Reglas del benchmark

Estas reglas se fijan antes de correr cualquier sistema. Cambiarlas después de ver resultados invalida la comparación.

## 1. Congelado del gold set

1. El gold set se congela cuando la validación humana de `validacion.md` está completa y M3 tiene su búsqueda ejecutada.
2. Al congelarlo se registran la fecha y el hash del commit.
3. Cualquier corrección posterior crea una versión nueva, documentada en `CAMBIOS.md`. Los resultados se reportan siempre junto con la versión del gold set que usaron.

## 2. Fuentes sin acceso abierto (Radmacher 2005)

Radmacher et al. 2005 (DOI 10.1099/mic.0.27804-0) aporta 4 de las 10 afirmaciones de referencia de M2 y no es de acceso abierto. EZresearchLM solo adquiere PDFs abiertos, así que sin una regla quedaría penalizado por diseño.

1. En la condición EZresearchLM, el operador puede importar el PDF que ya tiene con `ez rescue <corrida> --source <id> --import <pdf>`, como haría un tesista con su propia bibliografía.
2. La importación se registra en la planilla de resultados: qué archivo, en qué momento y con qué identidad confirmada.
3. Los resultados de M2 se informan dos veces: con la importación y sin ella. Así se ve cuánto depende el resultado de la intervención del usuario.
4. En las condiciones que admiten adjuntar archivos (IA con PDFs adjuntos y NotebookLM manual), se usa el mismo conjunto de PDFs que terminó en el corpus de EZresearchLM, incluido Radmacher 2005 si se importó.
5. En las condiciones sin archivos (IA generalista con o sin búsqueda web), no se adjunta nada.

## 3. Puntuación

1. Cada afirmación de cada sistema se puntúa de 0 a 3:
   - 0: sin fuente o fuente inexistente;
   - 1: fuente real que no respalda la afirmación;
   - 2: respaldo parcial o exagerado;
   - 3: respaldo completo y alcance correcto.
2. La evaluación es ciega: las respuestas se anonimizan y se ordenan al azar antes de puntuar.
3. Una semana después se repuntúa el 20 % de las afirmaciones sin mirar el puntaje anterior. Si la coincidencia es menor al 80 %, se precisa la rúbrica antes de seguir.

## 4. Artículos que no cuentan como clave

Los distractores (artículos que un sistema no debería usar como evidencia para la pregunta) no figuran en `articulos_clave.csv`. Se evalúan a través de las afirmaciones prohibidas. Ejemplo: Devlin et al. 2025 (ayuno de carbono en *M. tuberculosis*), cubierto por M2-P01.
