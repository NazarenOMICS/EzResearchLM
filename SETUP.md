# EZresearchLM Setup

## Preparar una investigación con EZ

EZ usa el agente anfitrión que ya tienes abierto para planificar. NotebookLM
aporta la evidencia. No necesitas otra API de modelos ni escribir archivos JSON.
La aceptación de este candidato con usuarios nuevos y Windows limpio sigue
pendiente. Las pruebas internas y CI se registran en `docs/refurbish-progress.md`.

Pide al agente: «EZ, prepara el entorno y ayúdame a investigar esta pregunta».
Para ver el recorrido completo, empieza por la [guía de primer uso](docs/ez-user-guide.md).
El agente sigue [la guía operativa](docs/ez-host-operator.md): comprueba capacidades,
conserva tu configuración, prepara el contrato y explica el siguiente paso.
QMD es opcional. Anna está desactivado y requiere consentimiento específico;
no se instala un navegador para eludir restricciones de acceso.

Si partes de un clon sin instalar, el agente prepara un entorno separado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements.lock .
.\.venv\Scripts\ez.exe setup --check
.\.venv\Scripts\ez.exe setup
```

La bienvenida aparece con `.\.venv\Scripts\ez.exe`; la guía completa, con
`.\.venv\Scripts\ez.exe --guide`. No abren un chat separado: vuelve a tu agente
para plantear la pregunta. Si `ez` no se encuentra en la terminal, usa esa ruta
completa del entorno instalado; no hace falta modificar el PATH del sistema.

Si falta NotebookLM, `ez setup --install-notebooklm` permite instalar la versión
compatible en un entorno propio. `ez setup --check` muestra la ruta del comando de
login cuando hace falta autenticar. El titular completa ese acceso en su navegador;
el agente no lee ni copia cookies. Una comprobación de acceso no acredita el E2E.

Se puede elegir otra carpeta con `--root "D:\Mis investigaciones\runs"` en cada
comando o mediante `EZRESEARCH_RUNS_ROOT`. Sin esa opción ni un override de `.env`,
la interfaz nueva usa `~/.ezresearch/runs`. Conserva el mismo root al continuar.
Los wrappers legacy mantienen sus rutas anteriores.

Continúa con [la guía de usuario](docs/ez-user-guide.md). Lo que sigue documenta
**solo el flujo legacy**, para operar corridas antiguas; no es requisito para EZ.

## Referencia de instalación legacy

## 1. Install Prerequisites

Install:

- Python 3.10 or newer.
- Git.
- Claude Code or another local agent.
- `notebooklm` CLI.
- QMD if you want local evidence recall.

Optional:

- Unpaywall email.
- NCBI email/API key.

## 2. Create Environment

Recommended:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv -Install
```

This creates `.venv`, installs EZresearchLM, creates `.env` if needed, and sets
`EZRESEARCH_PYTHON`.

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

## 3. Configure `.env`

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
notepad .env
```

Or let the setup checker create/update it:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -InitEnv
```

Before a full NotebookLM QA run, require full readiness:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -RequireFullPipeline
```

To verify Claude Code itself:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -CheckClaude
```

If Claude is installed but not trusted for this repo, either open Claude Code
interactively and accept the trust dialog, or run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" -TrustClaudeWorkspace
```

To set custom output locations from the command line:

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\setup_ezresearch.ps1" `
  -InitEnv `
  -RunsRoot "D:\ezresearch-runs" `
  -SearchRoot "E:\ezresearch-paper-cache" `
  -Vault "D:\ezresearch-vault"
```

Recommended minimum:

```text
EZRESEARCH_PYTHON=.venv\Scripts\python.exe
PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=you@example.com
NCBI_EMAIL=you@example.com
```

Choose output locations:

```text
EZRESEARCH_RUNS_ROOT=D:\ezresearch-runs
EZRESEARCH_SEARCH_ROOT=E:\ezresearch-paper-cache
EZRESEARCH_VAULT=D:\ezresearch-vault
```

If these are blank, EZresearchLM writes to local folders inside the repo.

## 4. Authenticate NotebookLM

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\auto_login.ps1"
notebooklm list
```

## 5. Prepare Inputs

Queries file must be a JSON array of strings:

```json
[
  "ethambutol Mycobacterium smegmatis proteomics",
  "Mycobacterium smegmatis ethambutol response PMID 20686769"
]
```

Must-have file:

```json
{
  "must_have": [
    {
      "pmid": "20686769",
      "title": "Comparative proteome analysis of Mycobacterium smegmatis in response to ethambutol"
    }
  ],
  "nice_to_have": [],
  "allow_anna_fallback": false
}
```

## 6. Run Pipeline

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_pipeline.ps1" `
  -Slug "first-run" `
  -Project "general" `
  -Goal "Build a traceable evidence set for my research question" `
  -QueriesFile ".\examples\queries.example.json" `
  -NotebookTitle "EZresearchLM first run" `
  -Dashboard "EZresearchLM first run" `
  -MustHaveFile ".\examples\must-have.example.json" `
  -StopIfMissingMustHave
```

## 7. If It Stops

For the example above, `-StopIfMissingMustHave` stops dependent QA when a required
source is missing. New legacy runs without that switch report missing sources
without this global gate. Continuations inherit the recorded effective gate.
EZ v2 additionally allows scoped partial answers; the signal alone does not mean
that all QA stopped. Inspect the structured state and its next action.

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\run_hermes_doctor.ps1" `
  -Project "general" `
  -Slug "first-run"
```

The doctor prints missing sources, artifacts, and the exact resume command.

## 8. Claude Code Usage

Open Claude Code in the repo and run:

```text
/setup
```

The `/setup`, `/research` and `/doctor` commands now route to the same EZ host
operator guide. They prepare natural-language requests and preserve existing
configuration; they do not require the user to author query or must-have files.

If `/setup` cannot run because Claude is not logged in, run:

```powershell
claude auth login
```

Then address your research question to EZ. Use the wrappers above only when
continuing a legacy run or when explicitly choosing that compatibility workflow.

Claude should not answer literature questions from memory. It should operate the
pipeline, inspect `source-rescue.json`, and use NotebookLM outputs for cited
answers.

The current operator contract is `docs/ez-host-operator.md`; older operator guides
describe legacy runs and must not override the scoped policies of an EZ contract.
