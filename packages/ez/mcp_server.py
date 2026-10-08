"""EZ as an MCP server for Claude Desktop: a thin adapter over the ez CLI.

Every tool runs the same `ez` command a host agent would run, so contracts,
screening, verification and integrity rules are identical. The agent in Claude
Desktop cannot read local files, so `ez_read` exposes a run's working files and
`ez_submit` writes the documents the agent prepares.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from .paths import contained, data_root, load_environment, runtime_root

INSTRUCTIONS = ('Eres EZ, un asistente de investigación bibliográfica que trabaja con NotebookLM. Antes de investigar, '
                'llama a ez_guide y sigue esa guía completa. Nunca afirmes nada de la literatura desde tu memoria: solo '
                'entrega afirmaciones verificadas por EZ, con su pasaje y su fuente. Prepara tú los documentos JSON '
                '(contrato, cribado, revisión) y envíalos con ez_submit; no pidas al usuario que escriba JSON.')
READABLE = ('research-contract.json', 'host-request.md', 'screening-request.json', 'review-request.json',
            'sources.json', 'answer.json', 'report.md', 'run-state.json', 'qa/manifest.json')
MAX_TEXT = 200_000


def root():
    load_environment()
    return Path(os.environ.get('EZRESEARCH_RUNS_ROOT') or data_root()).expanduser().resolve()


def ez(*arguments, seconds=3500):
    """Run one ez command and return its JSON result with the exit code."""
    command = [sys.executable, '-m', 'ez.cli', '--root', str(root()), *map(str, arguments), '--json']
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=seconds,
                                stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'error': 'timeout', 'next_action': 'La operación superó el tiempo de la herramienta; '
                'el trabajo quedó guardado. Consulta ez_status y continúa con ez_continue.'}
    try:
        value = json.loads(result.stdout)
    except ValueError:
        value = {'error': 'unreadable_output', 'stderr': result.stderr[-2000:]}
    return dict(value if isinstance(value, dict) else {'result': value}, exit_code=result.returncode)


def run_folder(run):
    path = Path(run)
    return path.resolve() if path.is_dir() else contained(root(), run)


def ez_guide():
    """Guía operativa de EZ para el agente. Léela completa antes de la primera investigación."""
    docs = runtime_root() / 'docs'
    parts = []
    for name in ('ez-host-operator.md', 'ez-user-guide.md'):
        path = docs / name
        if path.exists():
            parts.append(path.read_text(encoding='utf-8-sig'))
    return '\n\n---\n\n'.join(parts) or 'No se encontró la guía; instala EZ completo.'


def ez_setup(check: bool = True, install_notebooklm: bool = False):
    """Comprueba el entorno; con install_notebooklm instala la herramienta de NotebookLM en un entorno aislado."""
    arguments = ['setup'] + (['--check'] if check and not install_notebooklm else []) + (['--install-notebooklm'] if install_notebooklm else [])
    return ez(*arguments, seconds=900)


def ez_login():
    """Abre el inicio de sesión de NotebookLM en el navegador del usuario. EZ nunca lee ni copia cookies."""
    state = ez('setup', '--check', seconds=120)
    command = state.get('login_command')
    if not command:
        return dict(state, next_action='No hay un comando de inicio de sesión disponible; instala NotebookLM con ez_setup.')
    subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return {'started': True, 'next_action': 'Se abrió el inicio de sesión. Pide al usuario que lo complete en el navegador '
                                            'y después comprueba el acceso con ez_setup.'}


def ez_context(project: str = 'general', settings: dict | None = None):
    """Lee o guarda preferencias del proyecto (idioma, disciplina, objetivo, inclusiones, exclusiones, período)."""
    arguments = ['context', '--project', project]
    for key, value in (settings or {}).items():
        arguments += ['--set', key, str(value)]
    return ez(*arguments, seconds=60)


def ez_research(question: str, project: str = 'general', update_run: str | None = None):
    """Crea una investigación. Con update_run actualiza una anterior reutilizando su plan, PDFs y decisiones."""
    arguments = ['research', question, '--project', project]
    arguments += ['--update', update_run] if update_run else ['--plan-only']
    return ez(*arguments, seconds=600)


def ez_submit(run: str, kind: str, document: dict, check: bool = False):
    """Envía un documento preparado por el agente: kind = contract, screening o review. Con check solo lo valida."""
    if kind not in ('contract', 'screening', 'review'):
        return {'error': 'kind_invalid', 'next_action': 'Usa contract, screening o review.'}
    folder = run_folder(run)
    text = json.dumps(document, ensure_ascii=False, indent=2)
    path = contained(folder, f'proposals/{kind}-{sha256(text.encode()).hexdigest()[:16]}.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return ez('continue', str(folder), '--' + kind, str(path), *(['--check'] if check else []))


def ez_continue(run: str, verify: str | None = None):
    """Retoma la investigación. Con verify ("" o IDs separados por comas) verifica afirmaciones de la entrega directa."""
    return ez('continue', str(run_folder(run)), *(['--verify', verify] if verify else ['--verify'] if verify == '' else []))


def ez_status(run: str, answer: bool = False):
    """Estado y siguiente paso; con answer devuelve la respuesta verificada y la ruta del informe."""
    return ez('status', str(run_folder(run)), *(['--answer'] if answer else []), seconds=120)


def ez_read(run: str, name: str):
    """Lee un archivo de trabajo de la corrida (contrato, cribado, QA, revisión, respuesta o informe)."""
    folder = run_folder(run)
    allowed = name in READABLE or (name.startswith('qa/') and name.endswith('.json') and '/' not in name[3:])
    if not allowed:
        return {'error': 'not_readable', 'readable': list(READABLE) + ['qa/<archivo>.json']}
    path = contained(folder, name)
    if not path.exists():
        return {'error': 'missing', 'name': name}
    text = path.read_text(encoding='utf-8-sig')
    return {'name': name, 'truncated': len(text) > MAX_TEXT, 'text': text[:MAX_TEXT]}


def ez_rescue(run: str, source: str | None = None, import_pdf: str | None = None, confirm_identity: bool = False,
              retry: bool = False, origin: str | None = None, reviewer: str = 'host_agent', import_folder: str | None = None):
    """Lista fuentes pendientes; importa un PDF o una carpeta de PDFs del usuario (import_folder, se asignan solos por
    título e identificadores); confirma identidad (source admite varios IDs separados por comas) o reintenta la descarga."""
    arguments = ['rescue', str(run_folder(run))]
    if import_folder:
        arguments += ['--import-folder', import_folder]
    if source:
        arguments += ['--source', source]
    if import_pdf:
        arguments += ['--import', import_pdf, '--origin-provider', 'user_import'] + (['--origin', origin] if origin else [])
    if confirm_identity:
        arguments += ['--confirm-identity', '--reviewer', reviewer]
    if retry:
        arguments.append('--retry')
    return ez(*arguments, seconds=300)


def ez_draft(run: str, draft_text: str | None = None):
    """Sin texto: afirmaciones verificadas para redactar. Con texto: comprueba un borrador con marcas [EZ:<id>]."""
    folder = run_folder(run)
    if draft_text is None:
        return ez('draft', str(folder), seconds=60)
    path = contained(folder, f'drafts/draft-{sha256(draft_text.encode()).hexdigest()[:16]}.md')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(draft_text, encoding='utf-8')
    return ez('draft', str(folder), '--check', str(path), seconds=60)


def ez_verify(run: str, claim: str | None = None, judgement: str | None = None, note: str | None = None):
    """Revisión humana: sin claim muestra afirmaciones a revisar; con claim registra lo que el usuario concluyó."""
    arguments = ['verify', str(run_folder(run))]
    if claim and judgement not in ('supported', 'partial', 'unsupported'):
        return {'error': 'judgement_required', 'next_action': 'Indica judgement: supported, partial o unsupported.'}
    if claim:
        arguments += ['--claim', claim, '--judgement', judgement] + (['--note', note] if note else [])
    return ez(*arguments, seconds=600)


def ez_doctor(run: str):
    """Diagnóstico local de integridad de la corrida."""
    return ez('doctor', str(run_folder(run)), seconds=120)


TOOLS = (ez_guide, ez_setup, ez_login, ez_context, ez_research, ez_submit, ez_continue, ez_status, ez_read,
         ez_rescue, ez_draft, ez_verify, ez_doctor)


def build_server():
    from mcp.server.fastmcp import FastMCP
    server = FastMCP('EZ', instructions=INSTRUCTIONS)
    for tool in TOOLS:
        server.tool()(tool)
    return server


def main():
    build_server().run()


if __name__ == '__main__':
    main()
