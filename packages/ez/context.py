"""Research context links point to verifiable runs, never to memory-only claims."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil

from .contracts import ContractError, digest
from .doctor import diagnose
from .state import Store, lock, read_json


def history(root, project, limit=20):
    results = []
    for path in Path(root).glob('ez-*/research-contract.json'):
        try:
            contract = read_json(path)
            if contract.get('context', {}).get('project') != project:
                continue
            state = Store(path.parent).state()
            if not state or digest(contract) != state.get('contract_hash'):
                continue
            results.append({'run_id': state['run_id'], 'question': contract['question']['original'],
                            'saved_answer_status': state['answer']['status'], 'updated_at': state['updated_at'],
                            'path': str(path.parent.resolve()), 'evidence_must_be_rechecked': True})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(results, key=lambda r: r['updated_at'], reverse=True)[:limit]


def reuse_sources(origin, destination):
    """Copy verified bytes into a new run; do not mutate/reuse the old remote notebook."""
    origin, destination = Path(origin).resolve(), Path(destination).resolve()
    if origin == destination:
        raise ContractError('La reutilización requiere dos corridas distintas.')
    with lock(origin):
        if Store(origin).recover():
            raise ContractError('Completa la recuperación de la corrida anterior con ez continue antes de reutilizarla.')
        diagnosis = diagnose(origin)
        if not diagnosis['healthy']:
            raise ContractError('La corrida de origen necesita reparación antes de reutilizar evidencia.')
        old_state = Store(origin).state()
        old_sources = read_json(origin / 'sources.json') if (origin / 'sources.json').exists() else []
        sources = []
        for old in old_sources:
            if old.get('validation_status') != 'valid' or old.get('identity_status') != 'verified':
                continue
            source = deepcopy(old)
            path = Path(source['pdf_path'])
            blob = destination / 'reused' / (source['content_sha256'] + '.pdf')
            blob.parent.mkdir(exist_ok=True)
            if not blob.exists():
                shutil.copyfile(path, blob)
            if sha256(blob.read_bytes()).hexdigest() != source['content_sha256']:
                raise ContractError('La copia de evidencia no conserva el hash original.')
            source['reused_from'] = {'run_id': old_state['run_id'], 'sources_hash': old_state['sources_hash'],
                                     'notebook_source_id': source.get('notebook_source_id')}
            for key in ('notebook_source_id', 'upload_pending', 'anna_consent'):
                source.pop(key, None)
            source.update(pdf_path=str(blob), notebook_status='pending')
            sources.append(source)
    if not sources:
        raise ContractError('La corrida anterior no tiene PDFs con identidad verificada para reutilizar.')
    with lock(destination):
        store = Store(destination); state = store.state()
        if state.get('sources_hash') or state.get('notebook_id'):
            raise ContractError('La reutilización requiere una corrida nueva sin corpus previo.')
        state.update(sources_hash=digest(sources), reused_from=old_state['run_id'])
        store.append('decision', {'kind': 'reuse_verified_evidence', 'actor': 'host_agent', 'origin_run_id': old_state['run_id'],
                                  'origin_sources_hash': old_state['sources_hash'], 'source_count': len(sources)})
        store.commit(state, {'sources.json': sources})
