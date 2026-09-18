# Preparación de lanzamiento de EZ

Estado: **candidato de prebeta; lanzamiento público pendiente de aceptación**.
Este documento permite preparar y evaluar el candidato sin confundir una
instalación correcta con una investigación válida o una experiencia fácil de usar.

## Producto que se evalúa

La interfaz es una conversación con EZ dentro de un agente anfitrión que puede
operar archivos y comandos locales. El programa `ez` muestra una bienvenida,
incluye una guía sin conexión y ejecuta siete acciones. No se distribuye una
aplicación gráfica ni un chat autónomo. El usuario aporta su acceso al agente y a
NotebookLM; no se contrata otra API para planificar la investigación.

El inicio recomendado está en [la guía de usuario](ez-user-guide.md). La información
técnica de instalación está en [SETUP](../SETUP.md), y el anfitrión sigue
[su guía operativa](ez-host-operator.md). El usuario no necesita editar contratos.

## Evidencia disponible y pendiente

| Condición | Evidencia / estado |
|---|---|
| Publicación aislada del candidato anterior | Rama `codex/ez-refurbish-ci`, commit `257cb28`; trabajo original conservado |
| CI del candidato anterior | [Cuatro trabajos aprobados](https://github.com/NazarenOMICS/EzResearchLM/actions/runs/35390317770); Windows/Linux, Python 3.10/3.12 |
| NotebookLM real | Dos investigaciones internas con citas y una recuperación con interrupciones; revisión del anfitrión, anteriores a esta revisión de UX |
| Bienvenida y guía de esta revisión | Deben comprobarse en el wheel y CI de su propio commit; registrar ese resultado en `refurbish-progress.md` |
| Primer uso en Windows limpio | Pendiente de una máquina/perfil adecuado y del login de su titular |
| Facilidad de uso | Pendiente de evaluación con personas nuevas; no inferirla de pruebas automáticas |
| Recuperación representativa | Pendiente del benchmark curado; las rutas probadas para una sola obra no acreditan ≥90% |
| Revisión científica independiente | Pendiente de designar revisor y registrar dictámenes |
| Beta y lanzamiento | Pendientes según [el protocolo de beta](beta-and-release.md) |

## Ensayo de primer uso

Usar el artefacto exacto, con su hash, en Windows limpio o un perfil separado
que no herede la configuración de desarrollo. No copiar cookies ni credenciales.
Una carpeta temporal o un entorno Python nuevo en el mismo perfil no acredita por
sí solo esa condición. El titular completa el acceso a NotebookLM.

Pedir al participante las tareas siguientes sin mostrarle comandos ni explicarle
internamente cómo funciona. El agente sí forma parte del producto y puede guiarlo;
registrar aparte cualquier ayuda directa del desarrollador.

| Tarea | Resultado observable |
|---|---|
| Abrir el proyecto y empezar | Encuentra el primer mensaje en README o la guía; sabe dónde conversar |
| Preparar acceso | Distingue instalación de login; completa el acceso sin compartir credenciales |
| Definir una investigación | Expresa pregunta y objetivo; EZ aclara lo necesario sin pedir JSON |
| Consultar avance | Puede explicar qué está hecho, qué falta y quién actúa ahora |
| Obtener una respuesta parcial | Reconoce qué conclusiones están respaldadas y qué parte sigue pendiente |
| Aportar un PDF autorizado | EZ registra origen, comprueba identidad y conserva el archivo original |
| Retomar en otra conversación | Localiza el proyecto/corrida y continúa sin repetir una investigación por error |
| Ver una respuesta final | Encuentra citas, límites y carpeta del resultado; no confunde diagnóstico con validez científica |

Preguntas al terminar: «¿Qué podés afirmar con lo que recibiste?», «¿Qué falta?»
y «¿Cómo continuarías mañana?». Guardar las respuestas literales solo con el
consentimiento del participante; el informe público usa conteos y motivos saneados.

Registrar cada tarea como aprobada, fallida u omitida con motivo. La prueba de
entorno limpio requiere el E2E real de `ez-refurbish-implementation-plan.md`, incluida
interrupción y rescate; este ensayo de comprensión no lo sustituye. La beta mide
los umbrales definidos previamente, incluidos abandonos y fallos.

## Ficha privada de aceptación

Crear una ficha por participante o caso dentro de `runs/`, fuera de Git:

- Fecha, identificador anónimo del caso, sistema, Python, versión del agente y CLI.
- Commit, nombre del wheel y SHA-256; resultado de instalación y CI de ese candidato.
- Entorno limpio: cómo se comprobó; configuración que existía antes y después.
- Tareas intentadas, resultado, minutos de trabajo y espera externa por separado.
- Ayuda del agente y ayuda del desarrollador por separado; fallos y abandonos.
- Investigación de prueba, revisión de citas, incidencia, responsable y resolución.
- Decisión: aceptado para el caso probado, requiere corrección o no evaluado.

Mantener fuera del repositorio PDFs, preguntas privadas, exportaciones, rutas
personales y sesiones. La ausencia de un informe significa «no evaluado».

## Secuencia para distribuir y revertir

1. Construir el wheel desde un commit identificado; guardar hash e informes locales
   y remotos. Una modificación posterior crea otro candidato y no hereda aceptación
   del artefacto anterior por tener el mismo número de versión.
2. Probar guía incluida, instalación fuera del checkout, los siete comandos y las
   restricciones de evidencia. Ejecutar el protocolo autenticado y el ensayo anterior.
3. Completar benchmark de recuperación, revisión independiente y beta. Registrar
   incidencias; no omitir casos desfavorables del denominador.
4. Preparar notas de versión con alcance soportado, requisitos, límites, instrucciones
   de acceso, soporte y cambios de migración. Revisar el manifiesto con responsables
   técnico y de producto; su aprobación debe identificar el candidato.
5. Publicar una versión solo después de esa aceptación. No fusionar ni etiquetar
   una release por el solo hecho de tener CI verde.
6. Ante un defecto, conservar el entorno anterior y los datos, detener nuevas
   investigaciones afectadas y volver al artefacto anterior comprobado en otro
   entorno. Las corridas nuevas quedan guardadas; no convertirlas a formatos viejos
   ni degradar políticas silenciosamente. Las corridas legacy conservan sus wrappers.

Para beta, distribuir versiones fijadas y registrar el canal de soporte elegido
antes de invitar participantes. No se envían invitaciones ni telemetría desde EZ.
La aprobación de lanzamiento queda pendiente hasta reunir la evidencia exigida.
