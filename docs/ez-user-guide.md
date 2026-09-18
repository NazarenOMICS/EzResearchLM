# Investigar con EZ

EZ es el nombre del agente que opera tu investigación. Puedes plantearle una
pregunta en lenguaje natural y mantener la conversación en tu idioma. El agente
organiza el trabajo; NotebookLM responde sobre las fuentes reunidas. Este candidato
está en validación interna y todavía no tiene aprobación de lanzamiento.

## Primer uso

Pide: «EZ, prepara mi entorno y guarda el contexto de este proyecto».
Indica la pregunta, la disciplina y cualquier límite importante: fechas, población,
idioma, documentos obligatorios o presupuesto. EZ conserva ese contexto para las
siguientes investigaciones y pregunta por lo que realmente cambie el alcance.

Si necesitas instalar el programa, sigue [SETUP.md](../SETUP.md) con tu agente.
El acceso a NotebookLM lo completas tú en el navegador. No compartas cookies ni
tokens en la conversación. QMD es una ayuda opcional para encontrar material local.

## Las acciones disponibles

| Acción | Para qué sirve |
|---|---|
| `ez setup` | Preparar el entorno conservando la configuración existente |
| `ez context` | Consultar o guardar preferencias del proyecto y ver su historial |
| `ez research "pregunta"` | Abrir una investigación; el anfitrión prepara su plan |
| `ez continue <corrida>` | Seguir desde el último punto guardado |
| `ez status <corrida>` | Saber qué se hizo y cuál es el siguiente paso |
| `ez doctor <corrida>` | Revisar inconsistencias sin reescribir la investigación |
| `ez rescue <corrida>` | Ver fuentes pendientes o incorporar un PDF obtenido por ti |

No necesitas memorizar estas acciones: puedes pedirlas al agente. Abrir una
investigación desde la terminal deja un plan pendiente si el anfitrión todavía no
lo completó; el programa no simula haber entendido ni respondido tu pregunta.

## Entender el estado

- **Preparando o trabajando:** EZ busca, recupera, sube o consulta fuentes.
- **Esperando acceso o procesamiento:** el avance queda guardado; se continúa
  cuando el servicio o tu acceso estén disponibles.
- **Faltan documentos:** EZ explica qué parte de la pregunta depende de ellos.
  Otras partes pueden responderse si tienen respaldo independiente.
- **Revisión pendiente:** falta confirmar identidad, cobertura o una decisión
  concreta sobre las fuentes. No se considera una respuesta verificada todavía.
- **Respuesta parcial:** recibes únicamente conclusiones respaldadas, junto con
  sus citas y lo que falta. Una fuente ausente no equivale a evidencia negativa.
- **Problema de integridad:** se retiene la respuesta afectada porque cambió un
  archivo, una cita no se puede verificar o el corpus no corresponde al registro.

La ausencia de QMD no significa que falte evidencia académica. El número de PDFs
tampoco demuestra que la pregunta pueda responderse. La cobertura se revisa con QA.

## Recuperar documentos y retomar trabajo

Puedes entregar un PDF que hayas obtenido por una vía autorizada. EZ conserva el
origen informado, comprueba su estructura y pide o realiza un cotejo de identidad.
No reemplaza silenciosamente una versión ya usada por NotebookLM.

Anna es un último recurso opcional con consentimiento por fuente y procedencia
conservada. No se usa para contestar preguntas ni para evadir controles de acceso.

Para otra pregunta sobre material anterior, pide reutilizar la investigación.
EZ copia los PDFs verificados a una corrida nueva y vuelve a comprobar qué
respaldan; conserva intactos la investigación y el notebook originales.

Si ya trabajabas con los wrappers anteriores, sus corridas siguen disponibles.
La migración se previsualiza y crea una copia lateral. Los originales no se borran.

## Qué puedes esperar de una respuesta

Las afirmaciones entregadas deben conservar sus referencias y límites. EZ no
completa vacíos con recuerdos del modelo. La comprobación automática de citas
ayuda a detectar errores, pero no sustituye una revisión científica independiente.
Un reporte de investigación no es una certificación de lanzamiento del producto.
