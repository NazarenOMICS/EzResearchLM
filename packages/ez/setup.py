"""Isolated optional tool installation and capability-based onboarding."""
import os
import json
import re
from pathlib import Path
import sys

from .contracts import now
from .paths import executable, isolated_notebooklm
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
        {'id': 'notebooklm_installed', 'done': checks.get('notebooklm_installed', False) and not checks.get('login_browser_missing')
                                     and not checks.get('notebooklm_foreign'),
         'who': 'EZ',
         'say': 'Voy a instalar la herramienta que conecta con NotebookLM; tarda uno o dos minutos y no toca tu configuración.',
         'command': 'ez setup --install-notebooklm'},
        {'id': 'projects_dir', 'done': checks.get('projects_dir_chosen', False), 'who': 'usuario',
         'say': 'Tus informes, tu bandeja de PDFs y tus notas van a una carpeta que puedas abrir. Propongo '
                'Documentos\\EZresearchLM\\projects, junto a EZ. ¿Te sirve o prefieres otra?',
         'command': 'ez setup --projects-dir <carpeta>'},
        {'id': 'notebooklm_login', 'done': checks.get('can_notebook_qa', False), 'who': 'usuario',
         'say': 'Se va a abrir NotebookLM en tu navegador. Entra con tu cuenta de Google y avísame cuando termines. '
                'EZ nunca ve tu contraseña.',
         'command': 'ez setup --login'},
        {'id': 'unpaywall_email', 'done': checks.get('unpaywall_configured', False), 'who': 'usuario', 'optional': True,
         'say': '¿Me das un correo de contacto? Unpaywall, el índice de artículos de acceso abierto, lo pide para '
                'consultarlo. Solo se envía a Unpaywall y ayuda a encontrar más PDFs gratuitos.',
         'command': 'ez setup --unpaywall-email <correo>'},
        {'id': 'first_question', 'done': False, 'who': 'usuario',
         'say': '¿Qué quieres investigar y para qué lo necesitas (tesis, artículo, clase)? Cuéntamelo con tus palabras.',
         'command': 'ez research "<pregunta>" --project <proyecto> --plan-only'},
    ]


LOGIN_SECONDS = 600
LOGIN_STATUS = Path.home() / '.ezresearch/login-status.json'


def valid_notebook_list(result):
    try:
        return result.returncode == 0 and valid_listing(json.loads(result.stdout), 'notebooks')
    except (ValueError, TypeError):
        return False


def notebooklm_python(command):
    """Python of the environment that holds notebooklm (and Playwright), or None for unknown layouts."""
    python = Path(command).parent / ('python.exe' if os.name == 'nt' else 'python')
    return python if python.is_file() else None


def login_outcome(wait_seconds):
    """The sign-in's state once it leaves «running», or «running» after wait_seconds."""
    import time
    deadline = time.monotonic() + wait_seconds
    while True:
        state = read_json(LOGIN_STATUS).get('state') if LOGIN_STATUS.is_file() else None
        if state != 'running' or time.monotonic() >= deadline:
            return state or 'running'
        time.sleep(0.5)


def renew_session(wait_seconds=90):
    """Renew NotebookLM's saved session without the person, when the sign-in profile still holds a Google session.

    NotebookLM's session expired overnight; EZ's own sign-in then finished in four seconds with no one at the window,
    but nothing ran it, and the agent spent the morning trying other windows (2026-10-13).
    """
    if os.environ.get('EZRESEARCH_NO_SESSION_RENEWAL'):
        return False  # Offline tests: never reach the real NotebookLM or open a window.
    try:
        started = start_login(wait_seconds=wait_seconds)
    except ValueError:
        return False
    return started['login_status'] == 'ready'


def start_login(wait_seconds=None):
    """Open the Google sign-in for NotebookLM in a process detached from the agent; wait a moment for it to finish alone.

    An agent's shell tool may end the processes it started when the call returns; the sign-in can
    take minutes, so it runs on its own and leaves its outcome in LOGIN_STATUS for ez setup --check.
    When the browser profile still holds a Google session the window closes by itself in seconds: that is success,
    and the person and the agent read it as a failure (2026-10-13).
    """
    import subprocess
    command = executable('notebooklm')
    if not command or not notebooklm_python(command):
        raise ValueError('Falta la instalación de NotebookLM de EZ; corre ez setup --install-notebooklm.')
    if valid_notebook_list(run([command, 'list', '--json'], timeout=60)):
        # Already signed in: opening the window again would only confuse the person.
        return {'login_started': False, 'login_status': 'ready',
                'next_action': 'NotebookLM ya tiene acceso; no hace falta volver a entrar.'}
    LOGIN_STATUS.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(LOGIN_STATUS, {'state': 'running', 'started_at': now()})
    argv = [sys.executable, '-m', 'ez.setup', '--run-login']
    if os.name == 'nt':
        detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            # Leave the agent's job object too, when it allows it, so closing the agent's call cannot end the login.
            subprocess.Popen(argv, creationflags=detached | subprocess.CREATE_BREAKAWAY_FROM_JOB, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        except OSError:
            subprocess.Popen(argv, creationflags=detached, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True)
    else:
        subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    outcome = login_outcome(float(os.environ.get('EZRESEARCH_LOGIN_WAIT_SECONDS', 12)) if wait_seconds is None else wait_seconds)
    if outcome == 'ready':
        return {'login_started': True, 'login_status': 'ready',
                'next_action': 'NotebookLM renovó el acceso sin que la persona tuviera que entrar: la ventana se cerró sola '
                               'porque la sesión de Google seguía activa. Sigue con lo que estabas haciendo.'}
    if outcome == 'browser_missing':
        return {'login_started': True, 'login_status': outcome,
                'next_action': 'Falta el navegador del inicio de sesión (Chromium). Corre ez setup --install-notebooklm, '
                               'que lo descarga (unos 200 MB, varios minutos; espera con tu espera más larga), y vuelve a '
                               'abrir el inicio de sesión con ez setup --login. No hace falta revisar el código de EZ.'}
    if outcome != 'running':
        return {'login_started': True, 'login_status': outcome,
                'next_action': 'El inicio de sesión terminó sin acceso (' + outcome + '). Vuelve a correr ez setup --login y '
                               'pide a la persona que complete el ingreso en la ventana de Google.'}
    return {'login_started': True, 'login_status': 'running', 'window_minutes': LOGIN_SECONDS // 60,
            'next_action': 'Se abrió una ventana de Google. Pide a la persona que entre con su cuenta y te avise; '
                           'después comprueba el acceso con ez setup --check.'}


def run_login():
    """Detached half of start_login: the sign-in window, then notebooklm login to save the session."""
    import subprocess
    command = executable('notebooklm')
    hidden = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    state = 'failed'
    try:
        window = subprocess.run([str(notebooklm_python(command)), '-I', str(Path(__file__).with_name('notebook_login.py')),
                                 str(LOGIN_SECONDS)], capture_output=True, text=True, timeout=LOGIN_SECONDS + 120, **hidden)
        try:
            state = json.loads(window.stdout.strip().splitlines()[-1])['outcome']
        except (ValueError, IndexError, KeyError):
            state = 'failed'
        if state == 'signed_in':
            # The profile now holds a real Google session: notebooklm finds it and saves NotebookLM's cookies.
            saved = subprocess.run([command, 'login'], capture_output=True, text=True, timeout=180, **hidden)
            listed = subprocess.run([command, 'list', '--json'], capture_output=True, text=True, timeout=60, **hidden)
            state = 'ready' if saved.returncode == 0 and valid_notebook_list(listed) else 'saved_session_invalid'
    except subprocess.TimeoutExpired:
        state = 'timeout'
    atomic_json(LOGIN_STATUS, {'state': state, 'finished_at': now()})
    return state


BROWSER_PATH = ('from playwright.sync_api import sync_playwright\n'
                'with sync_playwright() as p:\n'
                '    print(p.chromium.executable_path)')


def login_browser_missing(command):
    """True when the NotebookLM environment lacks Playwright or the Chromium build that Playwright version needs.

    Importing Playwright was not enough: a clean install had the module and no browser (2026-10-19).
    Unknown layouts (pipx, uv) are not flagged.
    """
    python = notebooklm_python(command)
    if not python:
        return False
    found = run([str(python), '-c', BROWSER_PATH], timeout=60)
    lines = found.stdout.strip().splitlines() if found.returncode == 0 else []
    return not lines or not Path(lines[-1].strip()).is_file()


def write_install_pointer(root):
    """~/.ezresearch/install.json: where this EZ lives, so an agent in a new chat finds it without asking the person."""
    import shutil
    from .paths import runtime_root
    script = Path(sys.executable).parent / ('ez.exe' if os.name == 'nt' else 'ez')
    checkout = runtime_root()
    pointer = {'ez': str(script) if script.is_file() else shutil.which('ez'), 'python': sys.executable,
               'install_dir': str(checkout) if (checkout / 'AGENTS.md').is_file() else None,
               'runs_root': str(root), 'updated_at': now()}
    atomic_json(root.parent / 'install.json', pointer)
    return pointer


def prepare(root, check=False, install_notebooklm=False, unpaywall_email=None, projects_dir=None):
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
            # The pinned Playwright needs its own Chromium; without it the sign-in window failed at once with a bare
            # «failed: Error» on a clean install (2026-10-19), and the agent spent minutes reading EZ's code to find it.
            browser = run([str(python), '-m', 'playwright', 'install', 'chromium'], timeout=900)
            receipt.update(browser_exit_code=browser.returncode, browser_reason=browser.reason)
            atomic_json(runtime / 'ez-install-receipt.json', receipt)
            if browser.returncode:
                raise OSError('NotebookLM quedó instalado, pero no se pudo descargar el navegador del inicio de sesión '
                              '(Chromium, unos 200 MB). Vuelve a correr ez setup --install-notebooklm: retoma lo que falta.')
    from .workspace import config_path, home, leave_moved_notes, projects_home, relocate_projects
    config = config_path(root)
    moved_from = None
    if not check:
        with lock(root.parent):
            root.mkdir(parents=True, exist_ok=True)
            # Resolve the configured source before writing or changing config. In particular,
            # a second --projects-dir A -> B must copy from A, not the default folder.
            previous_projects = projects_home(root)
            if not config.exists():
                atomic_json(config, {'schema_version': '2.0', 'operator': 'EZ', 'backend': 'host_agent',
                                     'runs_root': str(root), 'telemetry': False, 'anna_enabled': False, 'created_at': now()})
            if projects_dir:
                chosen = Path(projects_dir).expanduser().resolve()
                relocate_projects(previous_projects, chosen)
                atomic_json(config, dict(read_json(config), projects_dir=str(chosen)))
                if previous_projects.resolve() != chosen and leave_moved_notes(previous_projects, chosen):
                    moved_from = str(previous_projects.resolve())
            write_install_pointer(root)
            if unpaywall_email:
                if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', unpaywall_email):
                    raise ValueError('El correo para Unpaywall no parece válido.')
                atomic_json(config, dict(read_json(config), unpaywall_email=unpaywall_email))
                os.environ['PAPER_SEARCH_MCP_UNPAYWALL_EMAIL'] = unpaywall_email
    checks = {'python': sys.version.split()[0], 'operator': 'host_agent', 'can_plan': True, 'can_discover': True,
              'projects_dir': str(projects_home(root)),
              'projects_dir_chosen': projects_home(root) != home(root) / 'projects',
              'can_notebook_qa': False, 'configuration_exists': config.exists(),
              'runs_root': str(root), 'installation': receipt,
              'unpaywall_configured': bool(os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL') or os.environ.get('UNPAYWALL_EMAIL'))}
    command = executable('notebooklm')
    checks['notebooklm_installed'] = bool(command)
    if command and command != isolated_notebooklm():
        # Another program's notebooklm on PATH served the live test of 2026-10-12: EZ never installed its own
        # (pinned version, login browser) and the onboarding marked the step done.
        checks['notebooklm_foreign'] = command
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
        if 'missing required cookies' in (result.stdout + result.stderr).casefold():
            # A login that closed early leaves a browser profile without the session cookies; the
            # next login takes it as "already logged in" and closes at once unless it starts fresh.
            checks['notebooklm_failure'] = 'incomplete_login'
        # EZ's own sign-in window: notebooklm login alone takes NotebookLM's public page for a session.
        checks['login_command'] = [sys.executable, '-m', 'ez', 'setup', '--login']
        if LOGIN_STATUS.is_file():
            checks['login_status'] = read_json(LOGIN_STATUS).get('state')
            if checks['login_status'] == 'ready' and not checks['can_notebook_qa']:
                # The record of an old sign-in said «ready» the next day while NotebookLM refused every call (2026-10-13).
                checks['login_status'] = 'expired'
        if not checks['can_notebook_qa']:
            checks['login_browser_missing'] = login_browser_missing(command)
    if checks['can_notebook_qa']:
        checks['next_action'] = 'El entorno permite preparar corpus y consultar NotebookLM. Dime qué quieres investigar.'
    elif checks.get('notebooklm_failure') == 'invalid_notebooklm_output':
        checks['next_action'] = 'NotebookLM respondió con un formato no reconocido. EZ debe comprobar la versión compatible antes de iniciar una investigación.'
    elif checks.get('login_browser_missing'):
        checks['next_action'] = ('A la instalación de NotebookLM le falta el navegador del login (Playwright o su Chromium): sin él la ventana '
                                 'se cierra sola. Repárala con ez setup --install-notebooklm y después abre el login.')
    elif checks['notebooklm_installed']:
        checks['next_action'] = ('Puedes preparar el corpus. Para consultar la evidencia, abre el acceso con ez setup --login: '
                                 'se abre una ventana de Google que espera hasta 10 minutos a que la persona entre.')
    else:
        checks['next_action'] = 'Falta NotebookLM. EZ puede instalarlo en un entorno aislado con ez setup --install-notebooklm; después debes iniciar sesión.'
    checks['introduction'] = INTRODUCTION
    checks['onboarding'] = onboarding(checks)
    checks['next_step'] = next((step for step in checks['onboarding'] if not step['done']), None)
    if not checks['unpaywall_configured']:
        # Unpaywall is the widest open-access index; without a contact email EZ skips it and more PDFs fail.
        checks['next_action'] += (' Para encontrar más PDFs de acceso abierto, guarda un correo de contacto para Unpaywall con '
                                  'ez setup --unpaywall-email <correo>; solo se envía a Unpaywall.')
    if moved_from:
        checks['projects_moved_from'] = moved_from
        checks['next_action'] += (f' Los proyectos se copiaron a {checks["projects_dir"]}; la carpeta anterior ({moved_from}) '
                                  'queda como respaldo con una nota MOVED.md. Dile a la persona que deje los PDFs nuevos en '
                                  'la bandeja nueva y que puede borrar la anterior cuando revise la copia.')
    return checks


if __name__ == '__main__' and sys.argv[1:] == ['--run-login']:
    run_login()
