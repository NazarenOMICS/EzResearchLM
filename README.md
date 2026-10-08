# EZresearchLM

> **Versión preliminar en validación.** No uses sus resultados en una tesis o un artículo
> sin revisar cada cita contra el PDF original. La verificación de respaldo la hace el
> mismo NotebookLM que genera la respuesta: es una comprobación automática, no una
> revisión humana.

EZ es un asistente de investigación bibliográfica para quien necesita afirmaciones que
pueda defender: cada afirmación que entrega viene con el pasaje exacto, el artículo
(título, DOI o PMID) y el PDF del que salió. Busca artículos en PubMed, Europe PMC,
OpenAlex, Crossref y Semantic Scholar, descarga los de acceso abierto, los carga en
tu NotebookLM y le pregunta solo sobre esos documentos. Al final recibes un informe
de evidencia (`report.md`) con lo que se pudo responder, lo que no y por qué.

## Cómo se usa

Se opera conversando con un agente que ya uses en tu computadora (Claude Code o
Codex), abierto en esta carpeta. No hay una aplicación gráfica todavía.

1. Escribe: «EZ, ayúdame a empezar. Prepara mi entorno. Quiero investigar [tu pregunta]
   para [tu objetivo]».
2. Inicia sesión en NotebookLM en tu navegador cuando EZ te lo pida.
3. EZ arma la búsqueda, elige qué artículos son relevantes y te consulta solo los dudosos.
4. Si un artículo importante es pago, EZ te lo dice: puedes entregarle tu PDF.
5. Recibes el informe de evidencia. Si pides un texto, EZ redacta solo con las
   afirmaciones verificadas y marca de dónde sale cada una.

Más detalle en la [guía de primer uso](docs/ez-user-guide.md).

## Qué tienes que saber antes de usarlo

- **NotebookLM gratuito:** admite hasta 50 fuentes por notebook. EZ usa 40 como máximo
  por investigación. Cada pregunta a NotebookLM consume tu cuota de uso.
- **Tus PDFs se suben a tu cuenta de Google**, dentro de NotebookLM.
- **EZ usa `notebooklm-py`, una librería no oficial.** Si Google cambia NotebookLM, EZ
  puede dejar de funcionar hasta que se actualice.
- **Solo acceso abierto o PDFs tuyos.** EZ no usa Anna's Archive, Sci-Hub ni evade
  controles de acceso. Un artículo pago queda pendiente hasta que importes tu copia.
- **La verificación es automática.** Revisa los pasajes en el PDF antes de citarlos.

## Instalación (para el agente)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -c requirements.lock .
ez setup --check
ez setup --install-notebooklm
```

El agente sigue [la guía operativa](docs/ez-host-operator.md). Comandos principales:
`ez setup`, `ez context`, `ez research`, `ez continue`, `ez status`, `ez rescue`,
`ez draft` y `ez doctor`. Detalles técnicos en [contratos y estados](docs/ez-contracts.md)
y [configuración](docs/configuration.md); estado de validación en
[preparación de lanzamiento](docs/release-readiness.md).

Las corridas creadas con los wrappers PowerShell anteriores siguen documentadas en la
[referencia legacy](docs/legacy-reference.md).


## License

MIT.
