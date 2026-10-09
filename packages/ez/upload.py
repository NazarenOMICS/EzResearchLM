"""Legacy parallel uploader with bounded per-file and batch deadlines."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import time

from .paths import contained
from .pdf import validate_pdf_bounded
from .process import run


def upload(notebook, directory, filenames, workers=4, timeout=180, batch_timeout=1800, runner=run):
    deadline = time.monotonic() + batch_timeout
    root = Path(directory).resolve()
    def one(name):
        path = contained(root, name)
        if not path.is_file() or path.suffix.lower() != '.pdf':
            return name, False, 'missing_pdf'
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return name, False, 'batch_deadline_exceeded'
        report = validate_pdf_bounded(path, timeout=min(30, remaining))
        if report['status'] != 'valid':
            return name, False, report['reason']
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return name, False, 'batch_deadline_exceeded'
        try:
            result = runner(['notebooklm', 'source', 'add', '--notebook', notebook, '--type', 'file', '--mime-type', 'application/pdf', str(path)], timeout=min(timeout, remaining))
            return name, result.returncode == 0, result.reason or ('notebooklm_failed' if result.returncode else '')
        except (ValueError, OSError) as exc:
            return name, False, type(exc).__name__
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(one, name) for name in filenames]
        for future in as_completed(futures):
            yield future.result()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--notebook', required=True)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--list', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--batch-timeout', type=float, default=1800)
    args = parser.parse_args()
    filenames = list(dict.fromkeys(x.strip() for x in Path(args.list).read_text(encoding='utf-8-sig').splitlines() if x.strip()))
    log = Path(args.log); log.parent.mkdir(parents=True, exist_ok=True)
    ok = 0
    with log.open('w', encoding='utf-8') as stream:
        for name, success, reason in upload(args.notebook, args.directory, filenames, args.workers, args.timeout, args.batch_timeout):
            line = f'[{datetime.now():%H:%M:%S}] {"OK" if success else "FAIL"} - {name}' + (f' :: {reason}' if reason else '')
            stream.write(line + '\n'); stream.flush(); print(line, flush=True)
            ok += success
        summary = f'DONE: {ok} OK, {len(filenames) - ok} FAIL (of {len(filenames)})'
        stream.write(summary + '\n'); print(summary)
    return 0 if ok == len(filenames) else 3


if __name__ == '__main__':
    raise SystemExit(main())
