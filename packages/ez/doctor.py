"""Read-only diagnosis of checkpoints, evidence files and optional remote membership."""
from hashlib import sha256
import json
from pathlib import Path

from .audit import load_answers
from .contracts import ContractError, digest, validate
from .paths import executable
from .process import run
from .notebook_format import valid_response
from .state import Store, read_json


def diagnose(folder, remote=False):
    folder = Path(folder)
    findings = []
    state = None
    def add(code, message, severity='error'):
        findings.append({'code': code, 'severity': severity, 'message': message})
    store = Store(folder)
    try:
        pending = store.recover()
        state = store.state()
        if not state:
            raise ContractError('Falta un estado confirmado en el journal.')
        validate(state, 'run-state')
        if pending:
            add('interrupted_projection', 'La transacción está confirmada y puede recuperarse con ez continue.', 'warning')
        if store.journal.read_bytes() and not store.journal.read_bytes().endswith(b'\n'):
            add('interrupted_event', 'Hay un evento incompleto; ez continue conservará el fragmento y recuperará el último estado confirmado.', 'warning')
        contract = validate(read_json(folder / 'research-contract.json'))
        if digest(contract) != state['contract_hash']:
            if not pending:
                raise ContractError('El contrato no coincide con el journal.')
        sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
        validate(sources, 'source-manifest')
        if state.get('sources_hash') and digest(sources) != state['sources_hash'] and not pending:
            raise ContractError('El manifiesto de fuentes no coincide con el journal.')
        for source in sources:
            if source.get('validation_status') == 'valid':
                path = Path(source['pdf_path'])
                if not path.is_file() or sha256(path.read_bytes()).hexdigest() != source['content_sha256']:
                    add('pdf_changed', 'El documento ' + source['source_id'] + ' falta o cambió después de validarse.')
                if source.get('identity_status') != 'verified':
                    add('identity_review', 'Revisar la identidad de ' + source['source_id'] + ' antes de usarlo como evidencia.', 'warning')
            elif source.get('acquisition_status') == 'manual_needed':
                add('source_rescue', 'Falta recuperar o importar ' + source['source_id'] + '.', 'warning')
        if state.get('qa_manifest_hash'):
            load_answers(folder, state, contract, sources)
        for key, expected in state.get('verification_receipts', {}).items():
            path = folder / 'verification' / (key + '.json')
            if not path.exists() or sha256(path.read_bytes()).hexdigest() != expected:
                add('support_qa_changed', 'Una comprobación de respaldo falta o cambió después de registrarse.')
        for key, expected in state.get('citation_resolution_receipts', {}).items():
            path = folder / 'citation-resolution' / (key + '.json')
            if not path.exists() or sha256(path.read_bytes()).hexdigest() != expected:
                add('citation_resolution_changed', 'El cotejo de una cita o su texto indexado falta o cambió.')
        if state.get('pending_operation'):
            add('remote_operation_uncertain', 'Hay una operación remota pendiente de reconciliar antes de repetirla.', 'warning')
        if remote and state.get('notebook_id'):
            command = executable('notebooklm')
            if not command:
                add('notebooklm_missing', 'Instala NotebookLM con ez setup --install-notebooklm.', 'warning')
            else:
                result = run([command, 'source', 'list', '--notebook', state['notebook_id'], '--json'], timeout=30)
                if result.returncode:
                    add(result.reason or 'remote_unavailable', 'No se pudo consultar NotebookLM; comprueba acceso y conexión.', 'warning')
                else:
                    payload = json.loads(result.stdout)
                    if not valid_response(payload, ['source', 'list']):
                        raise ContractError('NotebookLM devolvió un esquema remoto desconocido.')
                    actual = {s['id'] for s in payload['sources']}
                    expected = {s['notebook_source_id'] for s in sources if s.get('notebook_source_id')}
                    if actual != expected:
                        add('remote_corpus_drift', 'La composición del notebook difiere del manifiesto local. Reconciliar antes de continuar.')
    except (ContractError, ValueError, OSError, KeyError) as exc:
        add('integrity_unverified', str(exc))
    failed = any(f['severity'] == 'error' for f in findings)
    return {'run_id': (state or {}).get('run_id'), 'format': 'ez_v2', 'healthy': not failed,
            'findings': findings, 'answer': (state or {}).get('answer', {'status': 'unavailable'}) if not failed else {'status': 'unavailable'},
            'next_action': findings[0]['message'] if findings else 'No se detectaron inconsistencias locales. Esto no acredita un E2E ni habilita lanzamiento.'}
