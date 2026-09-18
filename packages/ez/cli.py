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
from .engine import Engine
from .doctor import diagnose
from .legacy import inspect_run, preview, migrate
from .paths import data_root, contained, load_environment, runtime_root
from .pdf import validate_pdf_bounded
from .process import run
from .state import Store, atomic_json, lock, read_json
from .setup import prepare


def emit(value, machine=False):
    if machine:
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if 'run_id' in value:
        print('Investigación:', value['run_id'])
    if 'phase' in value:
        phases = {'plan': 'Preparando la investigación', 'discover': 'Buscando fuentes', 'acquire': 'Recuperando documentos',
                  'upload': 'Enviando fuentes a NotebookLM', 'readiness': 'Esperando que se procesen las fuentes',
                  'qa': 'Consultando la evidencia', 'audit': 'Revisando citas y cobertura', 'done': 'Respuesta revisada'}
        print('Etapa:', phases.get(value['phase'], value['phase']))
    if value.get('answer'):
        labels = {'unavailable': 'Aún no hay una respuesta académica verificada.', 'partial': 'Hay una respuesta parcial, con límites explícitos.', 'complete': 'El alcance acordado tiene una respuesta verificada.'}
        print(labels.get(value['answer']['status'], value['answer']['status']))
    if value.get('next_action'):
        print(value['next_action'])
    if value.get('login_command') and not value.get('can_notebook_qa'):
        print('Acceso:', ' '.join('"' + x + '"' if ' ' in x else x for x in value['login_command']))
    if not value.get('next_action') and not any(k in value for k in ('phase', 'answer')):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    for claim in value.get('claims', []):
        print('\n' + claim['text'] + ' ' + ' '.join(f'[{claim["question_id"]}:{n}]' for n in claim['citation_numbers']))
    for row in value.get('coverage', []):
        if row['status'] != 'sufficient':
            print('\nPendiente (' + row['scope_id'] + '): ' + row['rationale'])
        for limitation in row['limitations']:
            print('Límite:', limitation)


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


def import_contract(folder, proposal, accept_policy_change=False):
    store = Store(folder)
    state = store.state()
    old = read_json(folder / 'research-contract.json')
    value = validate(read_json(proposal))
    if value['contract_id'] != old['contract_id']:
        raise ContractError('La propuesta debe conservar contract_id.')
    if value['context'] != old['context']:
        raise ContractError('El contexto conserva la revisión original. Para cambiarlo actualiza el contexto y crea una corrida nueva.')
    if state.get('discovery_complete') and (value['plan']['queries'] != old['plan']['queries'] or value['question'] != old['question']):
        raise ContractError('Una búsqueda o pregunta distinta requiere una corrida nueva; no se reutilizan resultados incompatibles.')
    for policy in old['source_policies']:
        replacement = next((p for p in value['source_policies'] if p['source_id'] == policy['source_id']), None)
        if state.get('discovery_complete') and replacement and replacement.get('pmc_version') != policy.get('pmc_version'):
            raise ContractError('Cambiar la versión PMC después del descubrimiento requiere una corrida nueva.')
        if policy.get('locked_by_user') and policy not in value['source_policies'] and not accept_policy_change:
            raise ContractError('Una obligación del usuario cambió. Requiere --accept-policy-change explícito.')
    value['revision'] = old['revision'] + 1
    value['parent_contract_hash'] = digest(old)
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
    if not args.import_pdf and not args.confirm_identity and not args.retry and not args.allow_anna:
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
    if args.allow_anna:
        from .consent import create_anna
        if not args.anna_url:
            raise ContractError('--allow-anna requiere --anna-url para la fuente concreta.')
        contract = read_json(folder / 'research-contract.json')
        receipt = create_anna(source, args.anna_url, state['run_id'])
        source.update(anna_consent=receipt, acquisition_status='pending')
        contract['parent_contract_hash'] = digest(contract)
        contract['revision'] += 1
        contract['acquisition'].update(anna_enabled=True, consent_id=receipt['consent_id'])
        store.append('decision', {'kind': 'anna_consent', 'actor': 'user', 'consent_id': receipt['consent_id'],
                                  'receipt_hash': digest(receipt), 'source_id': source['source_id']})
        state.update(contract_hash=digest(contract), sources_hash=digest(sources), answer={'status': 'unavailable'})
        store.commit(state, {'research-contract.json': contract, f'contracts/{contract["revision"]}.json': contract,
                             f'consents/{receipt["consent_id"]}.json': receipt, 'sources.json': sources})
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
        if args.origin_provider == 'anna_archive':
            from .consent import validate_anna
            receipt = validate_anna(source.get('anna_consent'), source)
            provenance.update(consent_id=receipt['consent_id'], acquisition_policy='non_oa_fallback')
        source.update(pdf_path=str(destination), content_sha256=report['sha256'], validation_status='valid',
                      identity_status='needs_review', pdf_source=args.origin_provider or 'user_import', acquisition_status='downloaded',
                      notebook_status='pending', provenance=provenance, previous_versions=previous_versions)
        if args.origin_provider == 'anna_archive':
            source.update(consent_id=receipt['consent_id'], acquisition_policy='non_oa_fallback', fallback_after=[])
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


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog='ez', description='EZ: investigación trazable con el agente anfitrión y NotebookLM.')
    parser.add_argument('--root', type=Path, default=None, help='Carpeta de corridas (o EZRESEARCH_RUNS_ROOT).')
    parser.add_argument('--json', action='store_true', help='Salida estructurada.')
    sub = parser.add_subparsers(dest='command')
    p = sub.add_parser('setup'); p.add_argument('--check', action='store_true'); p.add_argument('--install-notebooklm', action='store_true')
    p = sub.add_parser('context'); p.add_argument('--project', default='general'); p.add_argument('--set', nargs=2, action='append', metavar=('FIELD', 'VALUE'))
    p = sub.add_parser('research'); p.add_argument('question'); p.add_argument('--project', default='general'); p.add_argument('--plan-only', action='store_true'); p.add_argument('--contract', type=Path); p.add_argument('--reuse'); p.add_argument('--require-complete', action='store_true')
    p = sub.add_parser('continue'); p.add_argument('run'); p.add_argument('--contract', type=Path); p.add_argument('--accept-policy-change', action='store_true'); p.add_argument('--review', type=Path); p.add_argument('--require-complete', action='store_true')
    p = sub.add_parser('status'); p.add_argument('run'); p.add_argument('--answer', action='store_true')
    p = sub.add_parser('doctor'); p.add_argument('run'); p.add_argument('--migration-preview', action='store_true'); p.add_argument('--migrate', metavar='PREVIEW_HASH'); p.add_argument('--remote', action='store_true'); p.add_argument('--metrics', action='store_true')
    p = sub.add_parser('rescue'); p.add_argument('run'); p.add_argument('--import', dest='import_pdf'); p.add_argument('--source'); p.add_argument('--confirm-identity', action='store_true'); p.add_argument('--retry', action='store_true'); p.add_argument('--allow-anna', action='store_true'); p.add_argument('--anna-url')
    p.add_argument('--origin'); p.add_argument('--origin-provider', choices=['repository', 'institution', 'publisher', 'anna_archive', 'user_import']); p.add_argument('--license'); p.add_argument('--source-version')
    p.add_argument('--reviewer', choices=['user', 'host_agent'], default='user')
    for command_parser in sub.choices.values():
        command_parser.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        command_parser.add_argument('--root', type=Path, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    load_environment()
    root = (args.root or data_root()).expanduser().resolve()
    try:
        if not args.command:
            print('Soy EZ. Dime tu pregunta al agente anfitrión o usa ez research "tu pregunta".\nEmpieza con ez setup --check y ez context.')
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
            if proposal and proposal['question']['original'] != args.question:
                raise ContractError('La pregunta del contrato debe coincidir con la solicitada.')
            folder, state = create_run(root, args.question, context, proposal)
            if args.require_complete:
                with lock(folder):
                    state['require_complete'] = True
                    state = Store(folder).update(state)
            if args.reuse:
                from .context import reuse_sources
                origin = Path(args.reuse).resolve() if Path(args.reuse).is_dir() else contained(root, args.reuse)
                reuse_sources(origin, folder)
                state = Store(folder).state()
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
        if args.command in ('status', 'doctor'):
            if args.command == 'status' and not args.answer:
                state = Store(folder).state()
                validate(state, 'run-state')
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
                    emit(report, args.json)
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
            if args.command == 'continue' and args.contract:
                import_contract(folder, args.contract, args.accept_policy_change)
            if read_json(folder / 'research-contract.json')['plan']['status'] == 'needs_host_plan':
                state = Store(folder).state()
                emit(dict(state, legacy_signals=['NEEDS_PLAN'], next_action='El agente anfitrión debe completar e importar el plan antes de consultar servicios.'), args.json)
                return 2
            engine = Engine(folder)
            review = read_json(args.review) if args.command == 'continue' and args.review else None
            result = engine.execute(review)
            emit(engine.state, args.json)
            return result
    except (ContractError, ValueError, OSError, KeyError) as exc:
        emit({'error': type(exc).__name__, 'next_action': str(exc), 'answer': {'status': 'unavailable'}}, args.json)
        return 4 if isinstance(exc, ContractError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
