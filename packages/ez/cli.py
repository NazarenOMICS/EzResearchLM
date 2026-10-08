"""One interface for EZ. Natural-language planning is supplied by the host agent."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

from .contracts import ContractError, draft, validate, digest, now
from .audit import SUPPORT_PROTOCOL
from .engine import Engine
from .doctor import diagnose
from .legacy import inspect_run, preview, migrate
from .paths import data_root, contained, load_environment, runtime_root
from .pdf import validate_pdf_bounded
from .process import run
from .state import Store, atomic_json, lock, read_json
from .setup import prepare
from .presenter import render, welcome
from . import __version__


def emit(value, machine=False):
    print(json.dumps(value, ensure_ascii=False, indent=2) if machine else render(value))


def pending_passage_review(state):
    """Read-only view of a historical answer awaiting the current support check."""
    return dict(state, phase='audit', execution={'status': 'waiting_user'},
                answer={'status': 'unavailable'}, integrity={'status': 'pending'},
                legacy_signals=sorted(set(state.get('legacy_signals', [])) | {'NEEDS_QA_REVIEW'}),
                next_action='La respuesta histórica requiere verificar sus pasajes con el protocolo actual. Usa ez continue; se conservan sus registros.')


def context_path(root, project):
    return contained(root.parent / 'contexts', project + '.json')


def create_run(root, question, context, contract=None):
    run_id = 'ez-' + uuid4().hex[:16]
    folder = contained(root, run_id)
    folder.mkdir(parents=True, exist_ok=False)
    value = validate(contract or draft(question, context))
    with lock(folder):
        state = {'run_id': run_id, 'phase': 'plan', 'contract_hash': digest(value), 'execution': {'status': 'waiting_user'},
                 'answer': {'status': 'unavailable'}, 'next_action': 'El agente anfitrión debe completar el contrato y continuar esta corrida.'}
        store = Store(folder)
        store.append('decision', {'actor': 'user', 'kind': 'research_requested', 'question': question, 'backend': 'host_agent'})
        state = store.commit(state, {'research-contract.json': value, 'contracts/1.json': value})
    request = ('# Solicitud para el agente anfitrión EZ\n\n'
               + 'Guía operativa: ' + str(runtime_root() / 'docs/ez-host-operator.md') + '\n\n'
               +
               'Lee research-contract.json. Conserva la pregunta y el contexto. Completa plan.queries por proveedor, '
               'plan.notebook_questions por subpregunta y plan.stop_rule; usa plan.status="ready". '
               'Asigna las cinco políticas por alcance cuando corresponda, con razón y fuente verificable. '
               'No inventes referencias ni respuestas. NotebookLM es el motor de evidencia. '
               'Guarda la propuesta en otro archivo e impórtala con ez continue <run> --contract <archivo>. '
               'No edites los artefactos canónicos directamente. Tras QA revisa sus citas y límites antes de sintetizar.\n')
    (folder / 'host-request.md').write_text(request, encoding='utf-8')
    return folder, state


def import_contract(folder, proposal, accept_policy_change=False, dry_run=False):
    store = Store(folder)
    state = store.state()
    old = read_json(folder / 'research-contract.json')
    value = validate(read_json(proposal))
    if value['contract_id'] != old['contract_id']:
        raise ContractError('La propuesta debe conservar contract_id.')
    if value['context'] != old['context']:
        raise ContractError('El contexto conserva la revisión original. Para cambiarlo actualiza el contexto y crea una corrida nueva.')
    old_scopes = {s['id']: s for s in old['scope']}
    new_scopes = {s['id']: s for s in value['scope']}
    if state.get('discovery_complete') and new_scopes != old_scopes:
        raise ContractError('Cambiar el alcance después del descubrimiento requiere una corrida nueva.')
    if state.get('discovery_complete') and (value['plan']['queries'] != old['plan']['queries'] or value['question'] != old['question']):
        raise ContractError('Una búsqueda o pregunta distinta requiere una corrida nueva; no se reutilizan resultados incompatibles.')
    for policy in old['source_policies']:
        replacement = next((p for p in value['source_policies'] if p['source_id'] == policy['source_id']), None)
        if state.get('discovery_complete') and replacement and replacement.get('pmc_version') != policy.get('pmc_version'):
            raise ContractError('Cambiar la versión PMC después del descubrimiento requiere una corrida nueva.')
        scope_changed = any(new_scopes.get(scope_id) != old_scopes[scope_id] for scope_id in policy['scope_ids'])
        if policy.get('locked_by_user') and (policy not in value['source_policies'] or scope_changed) and not accept_policy_change:
            raise ContractError('Una obligación del usuario cambió. Requiere --accept-policy-change explícito.')
    value['revision'] = old['revision'] + 1
    value['parent_contract_hash'] = digest(old)
    if dry_run:
        return value
    store.append('decision', {'actor': 'host_agent', 'kind': 'contract_revision', 'before': digest(old), 'after': digest(value),
                              'policy_change_authorized': accept_policy_change})
    state.update(contract_hash=digest(value), answer={'status': 'unavailable'})
    store.commit(state, {'research-contract.json': value, f'contracts/{value["revision"]}.json': value})


def rescue(folder, args):
    store = Store(folder)
    state = store.state()
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    if state.get('sources_hash') and digest(sources) != state['sources_hash']:
        raise ContractError('El manifiesto de fuentes no coincide con el registro.')
    if not args.import_pdf and not args.confirm_identity and not args.retry:
        contract = read_json(folder / 'research-contract.json')
        missing = [p for p in contract['source_policies'] if not any(s['source_id'] == p['source_id'] for s in sources)]
        return {'sources': sources, 'unresolved_requirements': missing,
                'next_action': 'Importa un PDF con --import y --source, verifica identidad con --confirm-identity o reintenta con --retry.'}
    source = next((s for s in sources if s['source_id'] == args.source), None)
    if not source:
        contract = read_json(folder / 'research-contract.json')
        policy = next((s for s in contract['source_policies'] if s['source_id'] == args.source), None)
        if not policy:
            raise ContractError('Selecciona un source_id registrado en fuentes o políticas.')
        source = {'source_id': args.source, 'title': policy.get('title', ''), 'doi': policy.get('doi', ''), 'notebook_status': 'pending',
                  'validation_status': 'unknown', 'identity_status': 'unknown', 'acquisition_status': 'pending'}
        sources.append(source)
    if args.import_pdf:
        if source.get('notebook_source_id'):
            raise ContractError('Esta versión ya pertenece al corpus remoto. Crea una corrida nueva para sustituirla sin invalidar citas históricas.')
        if Path(args.import_pdf).is_symlink():
            raise ContractError('Selecciona el archivo original, no un enlace.')
        original = Path(args.import_pdf).resolve(strict=True)
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
        store.append('decision', {'actor': 'user', 'kind': 'pdf_import', 'source_id': args.source, 'sha256': report['sha256'], 'at': now()})
    if args.confirm_identity:
        if source.get('validation_status') != 'valid':
            raise ContractError('Primero importa o recupera un PDF válido.')
        if sha256(Path(source['pdf_path']).read_bytes()).hexdigest() != source['content_sha256']:
            raise ContractError('El PDF cambió después de validarlo; importa la versión correcta.')
        source['identity_status'] = 'verified'
        store.append('decision', {'actor': args.reviewer, 'kind': 'identity_confirmed', 'source_id': args.source, 'sha256': source['content_sha256']})
    if args.retry:
        source['acquisition_status'] = 'pending'
    state.update(sources_hash=digest(sources), answer={'status': 'unavailable'}, execution={'status': 'waiting_user'},
                 integrity={'status': 'pending'}, phase='acquire', blockers=[], legacy_signals=[],
                 next_action='Fuente registrada. Continúa la corrida para reconciliar NotebookLM y QA.')
    validate(sources, 'source-manifest')
    state = store.commit(state, {'sources.json': sources})
    return state


def check_proposal(folder, args):
    """Dry run: report what an import would reject, without writing or calling services."""
    if sum(bool(x) for x in (args.contract, args.review, args.screening)) != 1:
        raise ContractError('Usa --check con --contract, --review o --screening.')
    if args.screening:
        result = Engine(folder).apply_screening(read_json(args.screening), dry_run=True)
        return {'kind': 'check', 'target': 'screening', 'valid': True, **result,
                'next_action': 'El cribado es válido. Impórtalo con ez continue --screening.'}
    if args.contract:
        value = import_contract(folder, args.contract, args.accept_policy_change, dry_run=True)
        try:
            from .contracts import require_ready
            require_ready(value)
            pending = None
        except ContractError as exc:
            pending = str(exc)
        return {'kind': 'check', 'target': 'contract', 'valid': True, 'ready': pending is None,
                'next_action': pending or 'La propuesta es válida y está lista. Impórtala con ez continue --contract.'}
    from .audit import check_review_version, load_answers, review_claims
    state = Store(folder).state()
    contract = read_json(folder / 'research-contract.json')
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    review = read_json(args.review)
    check_review_version(review, state)
    claims = review_claims(review, state, contract, sources, load_answers(folder, state, contract, sources))
    return {'kind': 'check', 'target': 'review', 'valid': True, 'claims': len(claims),
            'next_action': 'La revisión es válida. Impórtala con ez continue --review; EZ verificará cada afirmación con NotebookLM.'}


def update_proposal(previous, question, context):
    """A new contract that keeps the previous plan, scope and source policies for the same question."""
    from copy import deepcopy
    old = read_json(previous / 'research-contract.json')
    if old['question']['original'] != question:
        raise ContractError('--update conserva la pregunta. Para otra pregunta usa ez research --reuse.')
    value = deepcopy(old)
    value.update(contract_id=str(uuid4()), revision=1, created_at=now(), context=context)
    value.pop('parent_contract_hash', None)
    return value


def verify_command(folder, args):
    """A person reads delivered claims against their passages; EZ records the judgement."""
    from .contracts import digest as hash_value
    state = Store(folder).state()
    answer = read_json(folder / 'answer.json') if (folder / 'answer.json').exists() else {}
    if not answer.get('claims'):
        raise ContractError('No hay afirmaciones entregadas para revisar.')
    if args.claim:
        if not args.judgement:
            raise ContractError('Indica --judgement supported, partial o unsupported.')
        with lock(folder):
            code = Engine(folder).apply_human_check(args.claim, args.judgement, args.note)
            emit(dict(Store(folder).state(), next_action='Revisión registrada. ' + ('La afirmación se retiró de la respuesta.'
                      if args.judgement == 'unsupported' else 'La afirmación conserva su lugar con tu revisión.')), args.json)
        return 0 if code in (0, 2) else code
    checked = state.get('human_checks', {})
    pending = sorted((c for c in answer['claims'] if c['id'] not in checked), key=lambda c: hash_value(c['id']))[:5]
    emit({'kind': 'verify_sample', 'checked': len(checked), 'claims': pending,
          'next_action': 'Lee cada pasaje en su PDF y registra: ez verify <corrida> --claim <id> --judgement supported|partial|unsupported.'},
         args.json)
    return 0


def draft_command(folder, args):
    """Read-only: the verified claims to write from, or a check of a draft that cites them as [EZ:<id>]."""
    from .deliver import check_draft
    state = Store(folder).state()
    if not state or state.get('answer', {}).get('status') not in ('complete', 'partial'):
        raise ContractError('Todavía no hay afirmaciones verificadas para redactar.')
    answer = read_json(folder / 'answer.json')
    if answer.get('contract_hash') != state['contract_hash'] or answer.get('corpus_hash') != state.get('corpus_hash') \
            or answer.get('support_protocol') != SUPPORT_PROTOCOL:
        raise ContractError('La respuesta guardada no corresponde a la versión vigente; usa ez continue.')
    if args.check:
        result = check_draft(answer, Path(args.check).read_text(encoding='utf-8-sig'))
        emit(result, args.json)
        return 0 if result['valid'] else 4
    emit({'kind': 'draft_material', 'report_path': str(folder / 'report.md'),
          'claims': [{'id': c['id'], 'marker': f'[EZ:{c["id"]}]', 'text': c['text'], 'scope_ids': c['scope_ids']}
                     for c in answer['claims']],
          'next_action': 'Redacta solo con estas afirmaciones, marca cada una con su marcador y comprueba el borrador con '
                         'ez draft <corrida> --check <archivo>.'}, args.json)
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog='ez', description='EZ: investigación trazable con el agente anfitrión y NotebookLM.')
    parser.add_argument('--version', action='version', version='EZ ' + __version__)
    parser.add_argument('--guide', action='store_true', help='Leer la guía de primer uso, sin conexión ni cambios.')
    parser.add_argument('--root', type=Path, default=None, help='Carpeta de corridas (o EZRESEARCH_RUNS_ROOT).')
    parser.add_argument('--json', action='store_true', help='Salida estructurada.')
    sub = parser.add_subparsers(dest='command')
    p = sub.add_parser('setup', help='Preparar el entorno y comprobar el acceso.'); p.add_argument('--check', action='store_true'); p.add_argument('--install-notebooklm', action='store_true')
    p = sub.add_parser('context', help='Guardar preferencias y consultar investigaciones anteriores.'); p.add_argument('--project', default='general'); p.add_argument('--set', nargs=2, action='append', metavar=('FIELD', 'VALUE'))
    p = sub.add_parser('research', help='Iniciar una investigación con una pregunta.'); p.add_argument('question'); p.add_argument('--project', default='general'); p.add_argument('--plan-only', action='store_true'); p.add_argument('--contract', type=Path); p.add_argument('--reuse'); p.add_argument('--require-complete', action='store_true')
    p.add_argument('--update', metavar='CORRIDA', help='Actualizar una investigación anterior: reutiliza sus PDFs verificados, su plan y sus decisiones.')
    p = sub.add_parser('continue', help='Retomar una investigación guardada.'); p.add_argument('run'); p.add_argument('--contract', type=Path); p.add_argument('--accept-policy-change', action='store_true'); p.add_argument('--review', type=Path); p.add_argument('--require-complete', action='store_true')
    p.add_argument('--screening', type=Path, help='Decisiones del anfitrión sobre los candidatos de screening-request.json.')
    p.add_argument('--check', action='store_true', help='Validar la propuesta o la revisión sin modificar la corrida ni consultar servicios.')
    p = sub.add_parser('status', help='Ver el avance y el siguiente paso.'); p.add_argument('run'); p.add_argument('--answer', action='store_true')
    p = sub.add_parser('draft', help='Ver las afirmaciones verificadas para redactar o comprobar un borrador.'); p.add_argument('run'); p.add_argument('--check', type=Path, metavar='BORRADOR')
    p = sub.add_parser('verify', help='Revisar en persona afirmaciones entregadas.'); p.add_argument('run'); p.add_argument('--claim'); p.add_argument('--judgement', choices=['supported', 'partial', 'unsupported']); p.add_argument('--note')
    p = sub.add_parser('doctor', help='Diagnosticar problemas de una investigación.'); p.add_argument('run'); p.add_argument('--migration-preview', action='store_true'); p.add_argument('--migrate', metavar='PREVIEW_HASH'); p.add_argument('--remote', action='store_true'); p.add_argument('--metrics', action='store_true')
    p = sub.add_parser('rescue', help='Ver documentos pendientes o incorporar un PDF.'); p.add_argument('run'); p.add_argument('--import', dest='import_pdf'); p.add_argument('--source'); p.add_argument('--confirm-identity', action='store_true'); p.add_argument('--retry', action='store_true')
    p.add_argument('--origin'); p.add_argument('--origin-provider', choices=['repository', 'institution', 'publisher', 'user_import']); p.add_argument('--license'); p.add_argument('--source-version')
    p.add_argument('--reviewer', choices=['user', 'host_agent'], default='user')
    for command_parser in sub.choices.values():
        command_parser.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        command_parser.add_argument('--root', type=Path, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    load_environment()
    root = (args.root or data_root()).expanduser().resolve()
    try:
        guide = runtime_root() / 'docs/ez-user-guide.md'
        if args.guide:
            emit({'kind': 'user_guide', 'path': str(guide), 'text': guide.read_text(encoding='utf-8-sig')}, args.json)
            return 0
        if not args.command:
            emit(welcome(root, guide), args.json)
            return 0
        if args.command == 'setup':
            emit(prepare(root, args.check, args.install_notebooklm), args.json)
            return 0
        if args.command == 'context':
            path = context_path(root, args.project)
            context = read_json(path) if path.exists() else {'schema_version': '2.0', 'project': args.project, 'language': 'es', 'revision': 0}
            if args.set:
                allowed = {'language', 'discipline', 'goal', 'preferences', 'inclusions', 'exclusions', 'date_range', 'budget'}
                if any(k not in allowed for k, _ in args.set):
                    raise ContractError('Campo de contexto no reconocido.')
                with lock(path.parent):
                    if path.exists():
                        context = read_json(path)
                        atomic_json(path.parent / 'history' / args.project / f'{context["revision"]}.json', context)
                    context.update(dict(args.set)); context['revision'] += 1
                    atomic_json(path, context)
            from .context import history
            emit(dict(context, research_history=history(root, args.project)), args.json)
            return 0
        if args.command == 'research':
            cpath = context_path(root, args.project)
            context = read_json(cpath) if cpath.exists() else {'language': 'es', 'project': args.project}
            proposal = read_json(args.contract) if args.contract else None
            previous = None
            if args.update:
                if args.contract or args.reuse:
                    raise ContractError('--update ya reutiliza el plan y las fuentes; no lo combines con --contract ni --reuse.')
                previous = Path(args.update).resolve() if Path(args.update).is_dir() else contained(root, args.update)
                proposal = update_proposal(previous, args.question, context)
            if proposal and proposal['question']['original'] != args.question:
                raise ContractError('La pregunta del contrato debe coincidir con la solicitada.')
            folder, state = create_run(root, args.question, context, proposal)
            if args.require_complete:
                with lock(folder):
                    state['require_complete'] = True
                    state = Store(folder).update(state)
            if args.reuse or previous:
                from .context import reuse_sources
                origin = previous or (Path(args.reuse).resolve() if Path(args.reuse).is_dir() else contained(root, args.reuse))
                reuse_sources(origin, folder)
                state = Store(folder).state()
            if previous:
                with lock(folder):
                    store = Store(folder); state = store.state()
                    old_state = Store(previous).state()
                    state['previous_run'] = {'run_id': old_state['run_id'], 'path': str(previous)}
                    documents = {}
                    if (previous / 'answer.json').exists():
                        documents['previous-answer.json'] = read_json(previous / 'answer.json')
                    state = store.commit(state, documents)
                emit(dict(state, path=str(folder), next_action='Actualización creada con el plan y las fuentes verificadas de '
                          + old_state['run_id'] + '. Ajusta el plan con ez continue --contract si hace falta, o continúa.'), args.json)
                return 0
            if args.plan_only or not proposal:
                emit(dict(state, path=str(folder)), args.json)
                return 0 if args.plan_only else 2
        else:
            folder = Path(args.run).resolve() if Path(args.run).is_dir() else contained(root, args.run)
            if not folder.is_dir():
                raise ContractError('No se encontró la corrida. Usa su identificador o ruta.')
            if not (folder / 'research-contract.json').exists():
                if args.command == 'doctor' and args.migrate:
                    emit(migrate(folder, root, args.migrate), args.json)
                else:
                    emit(preview(folder) if args.command == 'doctor' and args.migration_preview else inspect_run(folder), args.json)
                return 0 if args.command in ('status', 'doctor') else 2
        if args.command == 'draft':
            return draft_command(folder, args)
        if args.command == 'verify':
            return verify_command(folder, args)
        if args.command in ('status', 'doctor'):
            if args.command == 'status' and not args.answer:
                state = Store(folder).state()
                validate(state, 'run-state')
                if state.get('answer', {}).get('status') in ('complete', 'partial'):
                    answer_path = folder / 'answer.json'
                    report = read_json(answer_path) if answer_path.exists() else {}
                    if report.get('support_protocol') != SUPPORT_PROTOCOL:
                        emit(dict(pending_passage_review(state), snapshot_only=True), args.json)
                        return 2
                emit(dict(state, snapshot_only=True), args.json)
                return 0
            with lock(folder):
                if args.command == 'doctor':
                    if args.metrics:
                        from .metrics import collect
                        emit(collect(folder), args.json)
                        return 0
                    diagnosis = diagnose(folder, args.remote)
                    emit(diagnosis, args.json)
                    return 0 if diagnosis['healthy'] else 4
                store = Store(folder)
                pending = store.recover()
                state = store.state()
                if not state:
                    raise ContractError('La corrida no tiene un journal válido.')
                if pending:
                    emit(dict(state, next_action='Hay una escritura interrumpida; ez continue recuperará la transacción confirmada.', pending_projections=pending), args.json)
                    return 2
                if digest(read_json(folder / 'research-contract.json')) != state['contract_hash']:
                    raise ContractError('El contrato difiere del registro canónico.')
                if args.command == 'status' and args.answer and state.get('answer', {}).get('status') in ('complete', 'partial'):
                    diagnosis = diagnose(folder)
                    if not diagnosis['healthy']:
                        emit(diagnosis, args.json)
                        return 4
                    report = read_json(folder / 'answer.json')
                    if report['contract_hash'] != state['contract_hash'] or report['corpus_hash'] != state['corpus_hash']:
                        raise ContractError('La respuesta guardada pertenece a otra versión.')
                    if report.get('support_protocol') != SUPPORT_PROTOCOL:
                        emit(pending_passage_review(state), args.json)
                        return 2
                    emit(dict(report, report_path=str(folder / 'report.md')) if (folder / 'report.md').exists() else report, args.json)
                else:
                    emit(state, args.json)
                return 0
        with lock(folder):
            Store(folder).recover(repair=True)
            if args.command == 'continue' and args.require_complete:
                state = Store(folder).state()
                state['require_complete'] = True
                Store(folder).update(state)
            if args.command == 'rescue':
                emit(rescue(folder, args), args.json)
                return 0
            if args.command == 'continue' and args.check:
                emit(check_proposal(folder, args), args.json)
                return 0
            if args.command == 'continue' and args.contract:
                import_contract(folder, args.contract, args.accept_policy_change)
            if read_json(folder / 'research-contract.json')['plan']['status'] == 'needs_host_plan':
                state = Store(folder).state()
                emit(dict(state, legacy_signals=['NEEDS_PLAN'], next_action='El agente anfitrión debe completar e importar el plan antes de consultar servicios.'), args.json)
                return 2
            engine = Engine(folder)
            review = read_json(args.review) if args.command == 'continue' and args.review else None
            screening = read_json(args.screening) if args.command == 'continue' and args.screening else None
            result = engine.execute(review, screening)
            emit(engine.state, args.json)
            return result
    except (ContractError, ValueError, OSError, KeyError) as exc:
        emit({'error': type(exc).__name__, 'next_action': str(exc), 'answer': {'status': 'unavailable'}}, args.json)
        return 4 if isinstance(exc, ContractError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
