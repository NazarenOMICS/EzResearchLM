# Investigar con EZ

EZ es el nombre del agente que opera tu investigación. Puedes plantearle una
pregunta en lenguaje natural y mantener la conversación en tu idioma. El agente
organiza el trabajo; NotebookLM responde sobre las fuentes reunidas. Este candidato
está en validación interna y todavía no tiene aprobación de lanzamiento.

## Primer uso

Abre la carpeta de EZresearchLM con tu agente habitual, por ejemplo Codex o
Claude Code. Ahí conversas con EZ. Por ahora no hay una aplicación gráfica propia:
el programa `ez` ejecuta acciones y muestra el estado; la conversación la lleva tu
agente, que ya tiene que estar instalado y disponible.

Copia este primer mensaje en esa conversación:

> EZ, ayúdame a empezar. Prepara mi entorno y explícame cada paso.
> Quiero investigar [tu pregunta] para [tu objetivo].

El recorrido es:

1. **Preparar.** EZ comprueba qué está instalado y conserva la configuración
   existente. Si falta algo, prepara una instalación separada. Te dice dónde se
   guardará el trabajo y qué acceso falta.
2. **Conectar.** Cuando haga falta, completas el acceso a NotebookLM en tu navegador
   y vuelves a la conversación con «Ya inicié sesión». EZ comprueba el acceso.
3. **Delimitar.** Explicas tu pregunta y para qué necesitas la respuesta. EZ pregunta
   solo por datos que cambien el alcance: por ejemplo fechas, población o fuentes
   obligatorias. Puedes empezar sin conocer términos de búsqueda ni DOI.
4. **Investigar.** EZ resume qué va a buscar, conserva el contexto y consulta la
   evidencia en NotebookLM. Te avisa si necesita un documento o una decisión.
5. **Revisar el resultado.** Recibes la respuesta respaldada, sus citas, los límites
   y lo que quedó pendiente. Una búsqueda sin suficiente evidencia no se convierte
   en una respuesta inventada.

No necesitas preparar archivos de configuración, búsquedas ni contratos a mano.
Una carpeta nueva por sí sola no instala EZ ni conecta tu cuenta: el primer paso
lo realiza el agente con las instrucciones de instalación.

Si EZ ya está instalado, ejecutar `ez` muestra la bienvenida y `ez --guide` abre
esta guía como texto en la terminal. Ambas acciones funcionan sin consultar
NotebookLM ni modificar investigaciones. `ez --help` enumera las acciones.

## Qué puedes pedir durante el trabajo

| Tú dices | Qué hace EZ |
|---|---|
| «Guarda este proyecto como mi tesis» | Conserva el contexto para próximas investigaciones |
| «¿Cómo va y qué falta?» | Explica el último estado guardado y el siguiente paso |
| «Continuemos» | Retoma la investigación identificada en la conversación |
| «Tengo este PDF; incorpóralo» | Conserva su origen, comprueba el documento y continúa el alcance afectado |
| «Muéstrame lo que ya se puede responder» | Entrega la parte revisada si existe y señala lo pendiente |
| «Usa esas fuentes para otra pregunta» | Crea una nueva investigación con el material verificado |
| «Algo falló, ayúdame» | Diagnostica lo ocurrido y conserva el trabajo guardado |

Si vuelves en una conversación nueva, indica el proyecto o la carpeta de la
investigación. EZ consulta el historial; si hay varias candidatas, te pide elegir.
Cerrar la conversación no deja a EZ trabajando en segundo plano: para continuar,
vuelve al agente y pídeselo. Un servicio puede seguir procesando una fuente ya
enviada, pero eso no equivale a que EZ continúe toda la investigación solo.

## Dónde queda tu trabajo

EZ muestra la carpeta efectiva al preparar el entorno. Si no se configuró otra,
las investigaciones nuevas se guardan en `.ezresearch/runs` dentro de tu carpeta
de usuario. Cada investigación conserva pregunta, decisiones, documentos y
resultados; las preferencias del proyecto se guardan por separado.

Para ver la respuesta, pide «Muéstrame la respuesta con sus citas y límites».
Tu agente lee el resultado revisado y lo presenta en la conversación. La copia
estructurada queda en `answer.json`; los documentos y registros completos siguen
en la carpeta local y en el notebook correspondiente. Tener archivos guardados
todavía no significa que haya una respuesta revisada disponible.

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

Ejemplo ilustrativo de una respuesta parcial, no un resultado académico real:

> Ya puedo responder la primera parte con las fuentes revisadas. Falta el
> documento necesario para la comparación final. Esa comparación queda pendiente.
> Si lo tienes, puedes entregarme el PDF para continuar.

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
