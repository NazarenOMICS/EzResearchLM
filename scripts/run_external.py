"""Checkout and installed-wheel entry point for bounded legacy CLI calls."""
import os
from pathlib import Path
import sys

packages = Path(__file__).resolve().parents[1] / 'packages'
if packages.is_dir():
    sys.path.insert(0, str(packages))
    os.environ['PYTHONPATH'] = str(packages) + os.pathsep + os.environ.get('PYTHONPATH', '')

from ez.process import main

if __name__ == '__main__':
    raise SystemExit(main())
