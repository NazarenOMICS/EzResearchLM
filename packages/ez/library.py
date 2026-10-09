"""A project's library: the verified PDFs of its earlier researches, reusable without downloading again."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil

from .contracts import ContractError
from .state import read_json


def project_sources(runs_root, project, exclude_run=None):
    """Verified PDFs of the project's other runs, one per content hash, newest run first."""
    from .context import history
    found = {}
    for row in history(Path(runs_root), project, limit=500):
        if row['run_id'] == exclude_run:
            continue
        path = Path(row['path']) / 'sources.json'
        try:
            sources = read_json(path) if path.exists() else []
        except (OSError, ValueError):
            continue
        for source in sources:
            if source.get('validation_status') == 'valid' and source.get('identity_status') == 'verified' \
                    and source.get('content_sha256') and source['content_sha256'] not in found \
                    and Path(source.get('pdf_path') or '').is_file():
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
    blob = Path(run_folder) / 'reused' / (source['content_sha256'] + '.pdf')
    blob.parent.mkdir(exist_ok=True)
    if not blob.exists():
        shutil.copyfile(source['pdf_path'], blob)
    if sha256(blob.read_bytes()).hexdigest() != source['content_sha256']:
        blob.unlink()
        raise ContractError('Un PDF de la biblioteca del proyecto cambió después de verificarse; no se reutiliza.')
    for key in ('notebook_source_id', 'upload_pending', 'duplicate_of'):
        source.pop(key, None)
    source.update(keep or {})
    source.update(pdf_path=str(blob), notebook_status='pending', acquisition_status='downloaded',
                  reused_from={'run_id': entry['_run_id'], 'project_library': True})
    return source
