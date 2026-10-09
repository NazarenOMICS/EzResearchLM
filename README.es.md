# EZresearchLM

[Read in English](README.md)

**EZ busca artículos científicos sobre tu pregunta, los carga en tu NotebookLM y te entrega
lo que dicen, con el pasaje y la página de cada cita.** No responde de memoria: cada
afirmación sale de un PDF que puedes abrir.

> **Versión preliminar.** Funciona de punta a punta, pero falta la validación externa
> (comparación con otras herramientas e instalación en equipos limpios). Revisa cada
> pasaje en su PDF antes de citarlo en una tesis o un artículo.

## Empezar

Necesitas un agente en tu computadora, por ejemplo Codex o Claude Code, y una cuenta de
Google para NotebookLM. Pégale a tu agente este mensaje:

> Quiero usar esto para investigar: https://github.com/NazarenOMICS/EzResearchLM

El agente instala EZ y te guía paso a paso, con una pregunta por vez. No necesitas
escribir comandos.

Si no usas agentes en la terminal, hay una
[extensión experimental para Claude Desktop](desktop/README.md).

## Cómo es una investigación

1. **Preparar.** EZ instala lo que falta. Tú entras a NotebookLM con tu cuenta de Google
   en el navegador y, si quieres, das un correo de contacto para buscar más artículos
   gratuitos.
2. **Preguntar.** Cuentas qué quieres investigar y para qué. EZ te pregunta si es parte de
   un proyecto que ya tienes o si abre uno nuevo.
3. **Plan.** EZ te muestra en pocas líneas qué va a buscar y cuánto va a tardar, y espera tu
   visto bueno.
4. **Bibliografía.** EZ busca en PubMed, Europe PMC, OpenAlex y Crossref, elige los artículos
   relevantes y te avisa **antes de descargar nada** si alguno clave es pago. Te da el
   título y el enlace al DOI para que lo consigas por tu biblioteca o pidiéndolo a los
   autores. Lo dejas en la bandeja del proyecto y EZ lo toma solo.
5. **Respuesta.** EZ carga los PDFs en tu NotebookLM, le hace las preguntas y te entrega un
   informe: lo central primero, cada afirmación con su pasaje y su página, lo que no se pudo
   responder y por qué.
6. **Después.** Puedes pedir que verifique las afirmaciones una por una antes de redactar,
   exportar la bibliografía a Zotero o hacer otra pregunta en el mismo proyecto, que
   reutiliza los artículos ya cargados.

## Dónde queda todo

```
~/.ezresearch/projects/<tu proyecto>/
├── README.md     índice de tus investigaciones, con enlaces
├── inbox/        deja aquí tus PDFs
└── reports/      cada informe y su bibliografía (.bib)
```

Más detalle en [dónde queda cada cosa](docs/carpetas.md).

## Qué se midió

Corridas reales de octubre de 2026 sobre la pregunta de prueba del proyecto (efecto del
etambutol en *Corynebacterium glutamicum*):

| Medida | Resultado |
|---|---|
| Investigación desde cero (búsqueda, descarga, 4 preguntas) | 6,5 minutos |
| Pregunta en un proyecto con los PDFs ya cargados (5 preguntas) | entre 6 y 7 minutos |
| Afirmaciones respaldadas por su pasaje, en 20 revisadas a mano | 18 respaldadas, 2 parciales, 0 sin respaldo |

Cada pregunta a NotebookLM tarda alrededor de un minuto, igual que en su web. La muestra de
20 es chica: la precisión real está, con 95 % de confianza, entre 70 % y 97 %. El detalle
está en `gold_set_benchmark/` y el plan pendiente en la [hoja de ruta](docs/roadmap.md).

## Límites

1. **NotebookLM gratuito** admite 50 fuentes por notebook y tiene una cuota de uso; cada
   pregunta la consume.
2. **Tus PDFs se suben a tu cuenta de Google**, dentro de NotebookLM.
3. **EZ usa `notebooklm-py`, una librería no oficial.** Si Google cambia NotebookLM, EZ
   puede dejar de funcionar hasta que se actualice.
4. **Solo acceso abierto o PDFs tuyos.** EZ no usa Anna's Archive ni Sci-Hub ni evade
   controles de acceso.
5. **La comprobación es automática.** Las afirmaciones son oraciones de NotebookLM con los
   pasajes que él mismo citó; la verificación opcional también la hace NotebookLM. Ninguna
   de las dos es una revisión humana.

## Instalación (para el agente)

Si te pasaron solo el enlace de este repositorio, la persona quiere usar EZ y
probablemente no sabe de terminales. Hazlo tú, sin pedirle comandos:

1. Comprueba que estén Git y Python 3.10 o más nuevo (`git --version`, `python --version`).
   Si falta alguno, explícale cómo instalarlo en una frase (en Windows:
   `winget install Git.Git Python.Python.3.12`) y espera.
2. Clona el repositorio en su carpeta de documentos. Si el enlace apunta a una rama
   (`.../tree/<rama>`), clona esa rama.
3. Instala EZ en un entorno aislado dentro del repositorio:

   ```powershell
   cd $env:USERPROFILE\Documents\EZresearchLM
   python -m venv .venv
   .venv\Scripts\python -m pip install -c requirements.lock .
   .venv\Scripts\ez setup --check --json
   ```

   En macOS o Linux, `.venv/bin/python` y `.venv/bin/ez`. Usa siempre el `ez` del entorno.
4. Lee `AGENTS.md` y `docs/ez-host-operator.md` y empieza el onboarding de esa guía: un
   paso y una pregunta por vez, sin mostrarle comandos ni JSON. `ez setup --check` dice qué
   falta (instalar NotebookLM con `ez setup --install-notebooklm`, iniciar sesión, correo
   para Unpaywall).

## Documentación

1. [Guía de primer uso](docs/ez-user-guide.md): qué puedes pedirle a EZ.
2. [Guía del agente](docs/ez-host-operator.md): el recorrido completo que sigue el agente.
3. [Contratos y estados](docs/ez-contracts.md) y [configuración](docs/configuration.md):
   detalles técnicos.
4. [Hoja de ruta](docs/roadmap.md): qué está hecho, qué falta y en qué orden.

## Licencia

MIT.
