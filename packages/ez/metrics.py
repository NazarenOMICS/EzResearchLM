"""Local aggregate metrics; no questions, source text, paths, URLs or credentials."""
from collections import Counter
from hashlib import sha256

from .doctor import diagnose
from .state import Store, read_json


def collect(folder):
    store = Store(folder)
    state = store.state()
    if not state:
        raise ValueError('No hay una corrida EZ registrada.')
    diagnosis = diagnose(folder)
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    events = store.events()
    failures = Counter(e['payload'].get('reason') or 'nonzero_exit' for e in events if e['kind'] == 'external_result' and e['payload'].get('exit_code'))
    claims = []
    if diagnosis['healthy'] and state.get('answer', {}).get('status') in ('complete', 'partial'):
        report = read_json(folder / 'answer.json')
        if report['contract_hash'] == state['contract_hash'] and report['corpus_hash'] == state['corpus_hash']:
            claims = report['claims']
    return {'schema_version': '2.0', 'kind': 'local_aggregate_metrics',
            'run_pseudonym': sha256(state['run_id'].encode()).hexdigest()[:20],
            'active_seconds': state.get('elapsed_seconds', 0), 'execution_status': state['execution']['status'],
            'answer_status': state['answer']['status'] if diagnosis['healthy'] else 'unavailable',
            'source_count': len(sources), 'valid_pdf_count': sum(s.get('validation_status') == 'valid' for s in sources),
            'verified_identity_count': sum(s.get('identity_status') == 'verified' for s in sources),
            'remote_ready_count': sum(s.get('notebook_status') == 'ready' for s in sources),
            'delivered_claim_count': len(claims),
            'claims_with_traceability': sum(bool(c.get('references') and c.get('verification', {}).get('sha256')) for c in claims),
            'external_calls': sum(e['kind'] == 'external_result' for e in events), 'external_failures': dict(failures),
            'local_integrity_verified': diagnosis['healthy'], 'unjustified_block': None,
            'human_citation_review': None, 'authenticated_e2e_verified': None, 'sent_remotely': False}
