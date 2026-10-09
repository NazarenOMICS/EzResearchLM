"""Incorporating the user's own PDFs: one file, a whole folder, or the project's inbox."""
from hashlib import sha256
from pathlib import Path
import shutil
from types import SimpleNamespace

from .contracts import ContractError, now
from .paths import contained
from .pdf import validate_pdf_bounded

INBOX_ORIGIN = SimpleNamespace(origin_provider='user_import', origin='project inbox', license=None, source_version=None)


def import_pdf(folder, store, source, path, args, actor='user'):
    """Copy a validated PDF into the run as the source's new version; identity still needs a check."""
    if source.get('notebook_source_id'):
        raise ContractError('Esta versión ya pertenece al corpus remoto. Crea una corrida nueva para sustituirla sin invalidar citas históricas.')
    if Path(path).is_symlink():
        raise ContractError('Selecciona el archivo original, no un enlace.')
    original = Path(path).resolve(strict=True)
    report = validate_pdf_bounded(original)
    if report['status'] != 'valid':
        raise ContractError('PDF rechazado: ' + report['reason'])
    destination = contained(folder, 'imports/' + report['sha256'] + '.pdf')
    destination.parent.mkdir(exist_ok=True)
    if not destination.exists():
        shutil.copyfile(original, destination)
    if sha256(destination.read_bytes()).hexdigest() != report['sha256']:
        raise ContractError('La copia importada no conserva el hash.')
    previous_versions = list(source.get('previous_versions', []))
    if source.get('content_sha256') and source['content_sha256'] != report['sha256']:
        previous_versions.append({k: source.get(k) for k in ('content_sha256', 'pdf_path', 'pdf_source', 'provenance')})
    provenance = {'method': 'user_import', 'origin_provider': args.origin_provider or 'unspecified',
                  'origin': args.origin or 'not_supplied', 'license': args.license or 'unknown',
                  'source_version': args.source_version or 'unknown', 'imported_at': now(),
                  'validation': report, 'original_filename': original.name}
    source.update(pdf_path=str(destination), content_sha256=report['sha256'], validation_status='valid',
                  identity_status='needs_review', pdf_source=args.origin_provider or 'user_import', acquisition_status='downloaded',
                  notebook_status='pending', provenance=provenance, previous_versions=previous_versions)
    source.pop('notebook_source_id', None)
    store.append('decision', {'actor': actor, 'kind': 'pdf_import', 'source_id': source['source_id'], 'sha256': report['sha256'], 'at': now()})


def likely_match(path, text, source):
    """Weaker evidence than identity: the PDF prints the complete title or the DOI, or its filename carries the DOI."""
    from .acquisition import normalize_doi, plain_words
    title = ''.join(plain_words(source.get('title')))
    doi = normalize_doi(source.get('doi'))
    name = path.name.casefold().replace('_', '/')
    return (len(title) >= 20 and title in ''.join(plain_words(text))) or \
        bool(doi and (doi in text.casefold() or doi.replace('/', '') in name.replace('/', '')))


def import_folder(folder, store, sources, directory, args):
    """Match each PDF of a folder to one missing source. Printed title and identifiers verify identity; a title,
    DOI or filename match alone imports the PDF but leaves its identity for a quick confirmation."""
    from .acquisition import verify_identity
    from PyPDF2 import PdfReader
    pending = [s for s in sources if s.get('validation_status') != 'valid' and s.get('screening', 'include') == 'include'
               and not s.get('notebook_source_id')]
    imported, to_confirm, unmatched, ambiguous = [], [], [], []
    from .workspace import pdfs
    if not Path(directory).is_dir():
        raise ContractError(f'No existe la carpeta {directory}.')
    for path in pdfs(directory):
        if path.is_symlink() or validate_pdf_bounded(path.resolve())['status'] != 'valid':
            unmatched.append(path.name)
            continue
        strong = [s for s in pending if verify_identity(path, s) == 'verified']
        if not strong:
            try:
                text = ' '.join((page.extract_text() or '') for page in list(PdfReader(str(path)).pages)[:2])
            except Exception:
                text = ''
            weak = [s for s in pending if likely_match(path, text, s)]
        matches = strong or weak
        if len(matches) != 1:
            (ambiguous if matches else unmatched).append(path.name)
            continue
        source = matches[0]
        import_pdf(folder, store, source, path, args, actor='ez')
        row = {'file': path.name, 'source_id': source['source_id'], 'title': source.get('title')}
        if strong:
            # The PDF prints this work's own title and identifiers: the same rule automatic downloads use.
            source['identity_status'] = 'verified'
            store.append('decision', {'actor': 'ez', 'kind': 'identity_confirmed', 'source_id': source['source_id'],
                                      'sha256': source['content_sha256'], 'method': 'printed_identifiers'})
            imported.append(row)
        else:
            to_confirm.append(row)
        pending.remove(source)
    return {'imported': imported, 'needs_identity_confirmation': to_confirm, 'unmatched_files': unmatched,
            'ambiguous_files': ambiguous,
            'still_missing': [{'source_id': s['source_id'], 'title': s.get('title'), 'doi': s.get('doi')} for s in pending],
            'next_action': 'Coteja título y autores de cada PDF en needs_identity_confirmation y confírmalos juntos con '
                           '--confirm-identity --source id1,id2.' if to_confirm else None}
