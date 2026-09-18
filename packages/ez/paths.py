import os
from pathlib import Path
import sys


def runtime_root():
    configured = os.environ.get('EZRESEARCH_ROOT')
    if configured:
        return Path(configured).resolve()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / 'scripts/run_hermes_pipeline.ps1').exists():
        return checkout
    return Path(sys.prefix) / 'share/ezresearchlm'


def data_root():
    return Path(os.environ.get('EZRESEARCH_RUNS_ROOT', str(Path.home() / '.ezresearch/runs'))).expanduser().resolve()


def load_environment():
    """Read checkout overrides without replacing explicit process configuration."""
    root = runtime_root()
    path = root / '.env'
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not value or not key.startswith(('EZRESEARCH_', 'PAPER_SEARCH_', 'NOTEBOOKLM_')) or key in os.environ:
            continue
        if key in ('EZRESEARCH_RUNS_ROOT', 'EZRESEARCH_SEARCH_ROOT', 'EZRESEARCH_VAULT', 'EZRESEARCH_PYTHON'):
            value = str((root / Path(value).expanduser()).resolve())
        os.environ[key] = value


def executable(name):
    import shutil
    explicit = os.environ.get('EZRESEARCH_' + name.upper() + '_EXE')
    if explicit:
        return str(Path(explicit).expanduser().resolve()) if Path(explicit).expanduser().is_file() else None
    found = shutil.which(name)
    if found:
        return found
    runtime = Path.home() / '.ezresearch/tools/notebooklm'
    path = runtime / ('Scripts/notebooklm.exe' if os.name == 'nt' else 'bin/notebooklm')
    return str(path) if name == 'notebooklm' and path.is_file() else None


def contained(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError('La ruta debe permanecer dentro de la carpeta de la corrida.')
    return candidate
