"""Read-only legacy inventory. Historical false switches never weaken requirements."""
from hashlib import sha256
from pathlib import Path
from .contracts import ContractError, digest, draft
from .state import Store, lock, read_json


def inspect_run(path):
    path = Path(path)
    state = read_json(path / 'run-state.json') if (path / 'run-state.json').exists() else {}
    questions = [read_json(p) for p in sorted(path.glob('questions-*.json'))]
    if not isinstance(state, dict):
        raise ContractError('El estado legacy no es un objeto válido.')
    if state.get('schema_version') not in (None, 1, '1', '1.0'):
        raise ContractError('Estado con esquema no compatible o contrato ausente; no se interpreta como legacy.')
    if state.get('must_have_gate_version') not in (None, 2):
        raise ContractError('Versión de gate legacy desconocida; no se modifica su significado.')
    conflicts = []
    for field in ('vault_slug', 'notebook_id'):
        values = {str(p[field]) for p in [state, *questions] if isinstance(p, dict) and p.get(field)}
        if len(values) > 1:
            conflicts.append({'field': field, 'values': sorted(values)})
    gate = bool(state.get('stop_if_missing_must_have')) if state.get('must_have_gate_version') == 2 else True
    return {'format': 'legacy', 'run_dir': str(path.resolve()), 'state': state,
            'conflicts': conflicts, 'legacy_effective_gate': 'block_all_required' if gate else 'report_missing',
            'answer': {'status': 'unavailable'}, 'next_action': 'Revisar y migrar el contrato antes de continuar con EZ; los wrappers originales siguen disponibles.'}


def preview(path):
    path = Path(path).resolve()
    result = inspect_run(path)
    patterns = ('run-state.json', 'questions-*.json', 'source-rescue.json', 'candidate-sources.json', 'pdf-list-*.txt')
    files = sorted({p for pattern in patterns for p in path.glob(pattern) if p.is_file()})
    result['snapshot'] = {p.name: sha256(p.read_bytes()).hexdigest() for p in files}
    rescue = read_json(path / 'source-rescue.json') if (path / 'source-rescue.json').exists() else {}
    result['sources'] = rescue.get('sources', [])
    if not isinstance(result['sources'], list):
        raise ContractError('La cola legacy de fuentes no es válida.')
    result['next_action'] = 'La migración crea una corrida lateral y conserva los originales. El anfitrión revisa contrato e identidad antes de reanudar.'
    result['preview_hash'] = digest(result)
    return result


def migrate(path, root, expected_hash):
    """Sidecar migration; legacy bytes and references remain untouched."""
    from .cli import create_run
    from .pdf import validate_pdf_bounded
    plan = preview(path)
    if plan['preview_hash'] != expected_hash:
        raise ContractError('El origen cambió desde el preview; revisa un preview nuevo antes de migrar.')
    if plan['conflicts']:
        raise ContractError('Resuelve explícitamente los conflictos de notebook o vault antes de migrar.')
    old = plan['state']
    question = old.get('goal') or old.get('question')
    if not question:
        raise ContractError('El estado legacy no conserva la pregunta; crea una corrida con la pregunta explícita.')
    contract = draft(question, {'project': old.get('project', 'legacy'), 'language': 'es', 'legacy_vault_slug': old.get('vault_slug')})
    policies, sources = [], []
    for index, item in enumerate(plan['sources']):
        source_id = 'legacy-' + sha256(str(item.get('target_id') or index).encode()).hexdigest()[:20]
        source = {k: item.get(k) for k in ('title', 'doi', 'pmid', 'pmcid', 'pdf_source', 'notebook_source_id')}
        source.update(source_id=source_id, identity_status='needs_review', validation_status='unknown',
                      acquisition_status='manual_needed', notebook_status='pending', legacy_provenance=item)
        if item.get('required'):
            policies.append({'source_id': source_id, 'policy': 'hard_block' if plan['legacy_effective_gate'] == 'block_all_required' else 'soft_block',
                             'scope_ids': ['sq1'], 'rationale': 'Obligación heredada; se conserva el gate efectivo de la corrida original.',
                             'locked_by_user': True, **{k: item[k] for k in ('doi', 'pmid', 'pmcid', 'title') if item.get(k)}})
        if item.get('pdf_path'):
            original = Path(item['pdf_path']).expanduser()
            if not original.is_absolute():
                # Relative legacy paths have ambiguous roots. Do not guess.
                source['failure_code'] = 'legacy_relative_path_needs_review'
            elif original.is_file():
                report = validate_pdf_bounded(original)
                if report['status'] == 'valid':
                    source.update(pdf_path=str(original.resolve()), content_sha256=report['sha256'], validation_status='valid', acquisition_status='downloaded')
                else:
                    source['failure_code'] = report['reason']
        sources.append(source)
    contract['source_policies'] = policies
    source_ids = [s['source_id'] for s in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ContractError('El origen contiene fuentes duplicadas con el mismo identificador; revisa su correspondencia antes de migrar.')
    contract['migration'] = {'original_run': plan['run_dir'], 'preview_hash': expected_hash,
                             'effective_legacy_gate': plan['legacy_effective_gate'], 'old_anna_permission_inherited': False}
    # Recheck after validation: a concurrent legacy writer invalidates the preview.
    if preview(path)['preview_hash'] != expected_hash:
        raise ContractError('La corrida legacy cambió durante la migración; no se aplicó la propuesta.')
    folder, state = create_run(Path(root), question, contract['context'], contract)
    with lock(folder):
        state.update(legacy_origin=plan['run_dir'], discovery_complete=False, sources_hash=digest(sources),
                     next_action='Migración lateral creada. Revisa el contrato con el anfitrión y confirma la identidad de cada fuente antes de continuar.')
        if old.get('notebook_id'):
            state['notebook_id'] = old['notebook_id']
        Store(folder).commit(state, {'sources.json': sources, 'migration-preview.json': plan})
    return dict(state, path=str(folder))
