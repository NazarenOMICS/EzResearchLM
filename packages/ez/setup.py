"""Isolated optional tool installation and capability-based onboarding."""
import os
import json
import re
from pathlib import Path
import sys

from .contracts import now
from .paths import executable
from .process import run
from .notebook_format import valid_listing
from .state import atomic_json, lock, read_json

# The [browser] extra brings Playwright, which `notebooklm login` needs to open the sign-in window.
NOTEBOOKLM_SPEC = 'notebooklm-py[browser]==0.8.0'


# What the agent tells a new person before anything else, so they know what EZ does and what to ask.
# The examples avoid the benchmark's topics so that an agent under test gets no hint about the gold set.
INTRODUCTION = {
    'say': 'Soy EZ. Busco artículos científicos sobre tu pregunta, los cargo en tu NotebookLM y te entrego lo que '
           'dicen, con el pasaje y la página de cada cita. No respondo de memoria: si algo no está en los artículos, '
           'te lo digo. Una investigación tarda entre 5 y 10 minutos.',
    'you_can_ask': [
        'Una pregunta de investigación: «¿Qué se sabe del efecto del ayuno intermitente sobre la sensibilidad a la insulina?»',
        'Una pregunta de seguimiento sobre lo que ya encontré: «¿Cuánto duraron esos estudios y con cuántas personas?»',
        'Que busque un artículo o un tema que falta: «¿Hay estudios en personas mayores de 65 años?»',
        'Un párrafo para tu tesis con cada cita marcada, o la bibliografía para Zotero.',
        'Retomar otro día: «Quiero seguir con mi investigación».',
    ],
    'first_steps': 'Antes de la primera pregunta preparo dos cosas: instalo lo que falta y tú entras a NotebookLM '
                   'con tu cuenta de Google. Te voy guiando un paso por vez.',
}


def onboarding(checks):
    """First-use steps in order: who acts, whether it is done, and what the agent says to the user."""
    return [
        {'id': 'notebooklm_installed', 'done': checks.get('notebooklm_installed', False) and not checks.get('login_browser_missing'),
         'who': 'EZ',
         'say': 'Voy a instalar la herramienta que conecta con NotebookLM; tarda uno o dos minutos y no toca tu configuración.',
         'command': 'ez setup --install-notebooklm'},
        {'id': 'notebooklm_login', 'done': checks.get('can_notebook_qa', False), 'who': 'usuario',
         'say': 'Se va a abrir NotebookLM en tu navegador. Entra con tu cuenta de Google y avísame cuando termines. '
                'EZ nunca ve tu contraseña.',
         'command': ' '.join(checks.get('login_command') or ['notebooklm', 'login'])},
        {'id': 'unpaywall_email', 'done': checks.get('unpaywall_configured', False), 'who': 'usuario', 'optional': True,
         'say': '¿Me das un correo de contacto? Unpaywall, el índice de artículos de acceso abierto, lo pide para '
                'consultarlo. Solo se envía a Unpaywall y ayuda a encontrar más PDFs gratuitos.',
         'command': 'ez setup --unpaywall-email <correo>'},
        {'id': 'first_question', 'done': False, 'who': 'usuario',
         'say': '¿Qué quieres investigar y para qué lo necesitas (tesis, artículo, clase)? Cuéntamelo con tus palabras.',
         'command': 'ez research "<pregunta>" --project <proyecto> --plan-only'},
    ]


def login_browser_missing(command):
    """True when the NotebookLM environment lacks Playwright; unknown layouts (pipx, uv) are not flagged."""
    python = Path(command).parent / ('python.exe' if os.name == 'nt' else 'python')
    if not python.is_file():
        return False
    return run([str(python), '-c', 'import playwright'], timeout=30).returncode != 0


def prepare(root, check=False, install_notebooklm=False, unpaywall_email=None):
    receipt = None
    if install_notebooklm:
        if check:
            raise ValueError('--check no modifica el entorno; quita --check para instalar.')
        runtime = Path.home() / '.ezresearch/tools/notebooklm'
        with lock(runtime.parent):
            python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            if not python.exists():
                created = run([sys.executable, '-m', 'venv', str(runtime)], timeout=120)
                if created.returncode:
                    raise OSError('No se pudo crear el entorno aislado de NotebookLM: ' + (created.reason or 'venv_failed'))
            installed = run([str(python), '-m', 'pip', 'install', NOTEBOOKLM_SPEC], timeout=600)
            receipt = {'at': now(), 'package': NOTEBOOKLM_SPEC, 'exit_code': installed.returncode, 'reason': installed.reason,
                       'environment': str(runtime), 'python': sys.version.split()[0]}
            atomic_json(runtime / 'ez-install-receipt.json', receipt)
            if installed.returncode:
                raise OSError('No se pudo instalar NotebookLM; el recibo conserva el diagnóstico y permite reintentar.')
    config = root.parent / 'ez-config.json'
    if not check:
        with lock(root.parent):
            root.mkdir(parents=True, exist_ok=True)
            if not config.exists():
                atomic_json(config, {'schema_version': '2.0', 'operator': 'EZ', 'backend': 'host_agent',
                                     'runs_root': str(root), 'telemetry': False, 'anna_enabled': False, 'created_at': now()})
            if unpaywall_email:
                if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', unpaywall_email):
                    raise ValueError('El correo para Unpaywall no parece válido.')
                atomic_json(config, dict(read_json(config), unpaywall_email=unpaywall_email))
                os.environ['PAPER_SEARCH_MCP_UNPAYWALL_EMAIL'] = unpaywall_email
    checks = {'python': sys.version.split()[0], 'operator': 'host_agent', 'can_plan': True, 'can_discover': True,
              'can_notebook_qa': False, 'configuration_exists': config.exists(),
              'runs_root': str(root), 'installation': receipt,
              'unpaywall_configured': bool(os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL') or os.environ.get('UNPAYWALL_EMAIL'))}
    command = executable('notebooklm')
    checks['notebooklm_installed'] = bool(command)
    if command:
        result = run([command, 'list', '--json'], timeout=30)
        recognized = True
        if result.returncode == 0:
            try:
                recognized = valid_listing(json.loads(result.stdout), 'notebooks')
            except ValueError:
                recognized = False
        checks['can_notebook_qa'] = result.returncode == 0 and recognized
        checks['notebooklm_failure'] = result.reason or ('auth_or_configuration_required' if result.returncode else None)
        if not recognized:
            checks['notebooklm_failure'] = 'invalid_notebooklm_output'
        checks['login_command'] = [command, 'login']
        if not checks['can_notebook_qa']:
            checks['login_browser_missing'] = login_browser_missing(command)
    if checks['can_notebook_qa']:
        checks['next_action'] = 'El entorno permite preparar corpus y consultar NotebookLM. Dime qué quieres investigar.'
    elif checks.get('notebooklm_failure') == 'invalid_notebooklm_output':
        checks['next_action'] = 'NotebookLM respondió con un formato no reconocido. EZ debe comprobar la versión compatible antes de iniciar una investigación.'
    elif checks.get('login_browser_missing'):
        checks['next_action'] = ('A la instalación de NotebookLM le falta el navegador del login (Playwright): sin él la ventana '
                                 'se cierra sola. Repárala con ez setup --install-notebooklm y después abre el login.')
    elif checks['notebooklm_installed']:
        checks['next_action'] = 'Puedes preparar el corpus. Para consultar la evidencia, abre el login de NotebookLM y completa el acceso en tu navegador.'
    else:
        checks['next_action'] = 'Falta NotebookLM. EZ puede instalarlo en un entorno aislado con ez setup --install-notebooklm; después debes iniciar sesión.'
    checks['introduction'] = INTRODUCTION
    checks['onboarding'] = onboarding(checks)
    checks['next_step'] = next((step for step in checks['onboarding'] if not step['done']), None)
    if not checks['unpaywall_configured']:
        # Unpaywall is the widest open-access index; without a contact email EZ skips it and more PDFs fail.
        checks['next_action'] += (' Para encontrar más PDFs de acceso abierto, guarda un correo de contacto para Unpaywall con '
                                  'ez setup --unpaywall-email <correo>; solo se envía a Unpaywall.')
    return checks
