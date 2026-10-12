"""A project's library: the verified PDFs of its earlier researches, reusable without downloading again."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from .contracts import ContractError
from .state import link_or_copy, read_json


_DIGESTS, _STORED = {}, {}


def digest(path):
    """SHA-256 of a file, once per process for the same path, size and modification time.

    ez recall checked every passage of every claim: the same 15 PDFs were read and hashed some 650 times per call.
    """
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key not in _DIGESTS:
        _DIGESTS[key] = sha256(path.read_bytes()).hexdigest()
    return _DIGESTS[key]


def locate_pdf(source, runs_root=None):
    """The PDF a source records, if its bytes still have the recorded hash.

    Sources keep absolute paths; when the runs folder moves (a backup, another disk, a synced folder) the same bytes
    are looked up by hash under runs_root, where EZ stores every PDF as <run>/…/<sha256>.pdf.
    """
    expected = source.get('content_sha256')
    if not expected:
        return None
    candidates = [Path(source['pdf_path'])] if source.get('pdf_path') else []
    if runs_root is not None:
        key = (str(runs_root), expected)
        if key not in _STORED:
            root = Path(runs_root)
            _STORED[key] = sorted([*root.glob(f'*/*/{expected}.pdf'), *root.glob(f'*/*/*/{expected}.pdf')])
        candidates += _STORED[key]
    for path in candidates:
        try:
            if path.is_file() and digest(path) == expected:
                return path
        except OSError:
            continue
    return None


def check_pdf_integrity(source, runs_root=None):
    """A recorded identity is not proof that the bytes on disk are still that PDF; returns the checked bytes."""
    path = locate_pdf(source, runs_root)
    try:
        data = path.read_bytes() if path else None
    except OSError:
        data = None
    if data is None or sha256(data).hexdigest() != source.get('content_sha256'):
        raise ContractError('pdf_integrity_error: PDF ausente o cambiado; no se sirve evidencia ni caché.')
    return data


def verify_pdf(source, runs_root=None):
    """Like check_pdf_integrity, without reading the bytes again when this process already hashed that file."""
    if locate_pdf(source, runs_root) is None:
        raise ContractError('pdf_integrity_error: PDF ausente o cambiado; no se sirve evidencia ni caché.')


def project_sources(runs_root, project, exclude_run=None, runs=None):
    """Verified PDFs of the project's other runs, one per content hash, newest run first (runs: history already read)."""
    from .context import history
    found = {}
    for row in history(Path(runs_root), project, limit=500) if runs is None else runs:
        if row['run_id'] == exclude_run:
            continue
        path = Path(row['path']) / 'sources.json'
        try:
            sources = read_json(path) if path.exists() else []
        except (OSError, ValueError):
            continue
        for source in sources:
            if source.get('validation_status') == 'valid' and source.get('identity_status') == 'verified' \
                    and source.get('content_sha256') and source['content_sha256'] not in found:
                found[source['content_sha256']] = dict(source, _run_id=row['run_id'])
    return list(found.values())


def matching(library, source):
    """The library entry for the same work, by DOI, PMID or PMCID."""
    from .acquisition import normalize_doi
    for entry in library:
        if source.get('doi') and normalize_doi(entry.get('doi')) == normalize_doi(source['doi']):
            return entry
        for key in ('pmid', 'pmcid'):
            if source.get(key) and str(entry.get(key) or '').casefold() == str(source[key]).casefold():
                return entry
    return None


def adopt(run_folder, entry, keep=None):
    """Copy a library PDF into this run; the bytes are checked against their recorded hash."""
    source = deepcopy({k: v for k, v in entry.items() if k != '_run_id'})
    located = locate_pdf(source, Path(run_folder).parent)
    if located is None:
        raise ContractError('pdf_integrity_error: PDF ausente o cambiado; no se sirve evidencia ni caché.')
    blob = Path(run_folder) / 'reused' / (source['content_sha256'] + '.pdf')
    blob.parent.mkdir(exist_ok=True)
    if not blob.exists():
        link_or_copy(located, blob)
    if sha256(blob.read_bytes()).hexdigest() != source['content_sha256']:
        blob.unlink()
        raise ContractError('Un PDF de la biblioteca del proyecto cambió después de verificarse; no se reutiliza.')
    for key in ('notebook_source_id', 'upload_pending', 'duplicate_of'):
        source.pop(key, None)
    source.update(keep or {})
    source.update(pdf_path=str(blob), notebook_status='pending', acquisition_status='downloaded',
                  reused_from={'run_id': entry['_run_id'], 'project_library': True})
    return source
