"""One interface for EZ. Natural-language planning is supplied by the host agent."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

from .contracts import ContractError, draft, validate, digest, now
from .audit import CURRENT_PROTOCOLS
from .engine import Engine
from .doctor import diagnose
from .legacy import inspect_run, preview, migrate
from .paths import data_root, contained, load_environment, runtime_root, load_user_config
from .imports import import_folder, import_pdf
from .state import Store, atomic_json, lock, read_json
from .setup import prepare
from .presenter import render, welcome
from . import __version__


# Repeated in every JSON answer: a host agent whose context was compacted, or a small model, still sees the rules on each call.
OPERATOR_REMINDER = ('Reglas de EZ: responde solo con afirmaciones de EZ y sus marcadores [EZ:<id>]. Una pregunta de seguimiento '
                     'se responde con esas afirmaciones o con ez ask; artículos nuevos, con ez research; un borrador, con ez draft '
                     'y ez draft --check. No uses búsqueda web ni tu memoria para afirmaciones bibliográficas; un dato externo que '
                     'el usuario pida explícitamente va rotulado «fuente externa, no del corpus». El plan se arma con ez plan y el '
                     'cribado con ez screen; no edites archivos de la corrida ni leas docs/history.')


def emit(value, machine=False):
    if machine and isinstance(value, dict):
        value = dict(value, operator_reminder=OPERATOR_REMINDER)
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
        from .workspace import ensure
        state = {'run_id': run_id, 'phase': 'plan', 'contract_hash': digest(value), 'execution': {'status': 'waiting_user'},
                 'answer': {'status': 'unavailable'}, 'next_action': 'El agente anfitrión arma el plan con ez plan y, con el visto bueno del usuario, continúa esta corrida.',
                 'workspace': ensure(root, value.get('context', {}).get('project') or 'general')}
        store = Store(folder)
        store.append('decision', {'actor': 'user', 'kind': 'research_requested', 'question': question, 'backend': 'host_agent'})
        state = store.commit(state, {'research-contract.json': value, 'contracts/1.json': value})
    request = ('# Solicitud para el agente anfitrión EZ\n\n'
               + 'Guía operativa: ' + str(runtime_root() / 'docs/ez-host-operator.md') + '\n\n'
               +
               'Arma el plan con ez plan <run> --qa "pregunta" (una por subpregunta, entre 3 y 5) y --query proveedor:texto '
               '(pubmed, europepmc, openalex, semantic, crossref); no escribas el contrato a mano. Muéstrale al usuario la '
               'estimación y, con su visto bueno, sigue el comando que indica. No inventes referencias ni respuestas. NotebookLM es el motor de evidencia. '
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
    if not args.import_pdf and not args.import_folder and not args.confirm_identity and not args.retry:
        contract = read_json(folder / 'research-contract.json')
        missing = [p for p in contract['source_policies'] if not any(s['source_id'] == p['source_id'] for s in sources)]
        return {'sources': sources, 'unresolved_requirements': missing,
                'next_action': 'Importa un PDF con --import y --source, o una carpeta entera con --import-folder; verifica '
                               'identidad con --confirm-identity (acepta varios IDs separados por comas) o reintenta con --retry.'}
    summary = None
    if args.import_folder:
        summary = import_folder(folder, store, sources, args.import_folder, args)
    ids = [x.strip() for x in (args.source or '').split(',') if x.strip()]
    if (args.import_pdf or args.retry) and len(ids) != 1:
        raise ContractError('--import y --retry requieren un solo --source.')
    for source_id in ids:
        source = next((s for s in sources if s['source_id'] == source_id), None)
        if not source:
            contract = read_json(folder / 'research-contract.json')
            policy = next((s for s in contract['source_policies'] if s['source_id'] == source_id), None)
            if not policy:
                raise ContractError(f'Selecciona un source_id registrado en fuentes o políticas: {source_id}.')
            source = {'source_id': source_id, 'title': policy.get('title', ''), 'doi': policy.get('doi', ''), 'notebook_status': 'pending',
                      'validation_status': 'unknown', 'identity_status': 'unknown', 'acquisition_status': 'pending'}
            sources.append(source)
        if args.import_pdf:
            import_pdf(folder, store, source, args.import_pdf, args)
        if args.confirm_identity:
            if source.get('validation_status') != 'valid':
                raise ContractError(f'Primero importa o recupera un PDF válido para {source_id}.')
            if sha256(Path(source['pdf_path']).read_bytes()).hexdigest() != source['content_sha256']:
                raise ContractError('El PDF cambió después de validarlo; importa la versión correcta.')
            source['identity_status'] = 'verified'
            store.append('decision', {'actor': args.reviewer, 'kind': 'identity_confirmed', 'source_id': source_id, 'sha256': source['content_sha256']})
        if args.retry:
            source['acquisition_status'] = 'pending'
    if args.confirm_identity and not ids:
        raise ContractError('--confirm-identity requiere --source con uno o varios IDs.')
    state.update(sources_hash=digest(sources), answer={'status': 'unavailable'}, execution={'status': 'waiting_user'},
                 integrity={'status': 'pending'}, phase='acquire', blockers=[], legacy_signals=[],
                 next_action='Fuente registrada. Continúa la corrida para reconciliar NotebookLM y QA.')
    validate(sources, 'source-manifest')
    state = store.commit(state, {'sources.json': sources})
    return dict(state, import_folder=summary) if summary is not None else state


def check_proposal(folder, args):
    """Dry run: report what an import would reject, without writing or calling services."""
    if sum(bool(x) for x in (args.contract, args.review, args.screening)) != 1:
        raise ContractError('Usa --check con --contract, --review o --screening.')
    if args.screening:
        result = Engine(folder).apply_screening(read_json(args.screening), dry_run=True)
        return {'kind': 'check', 'target': 'screening', 'valid': True, **result,
                'next_action': 'El cribado es válido. Aplícalo con el mismo comando sin --check.'}
    if args.contract:
        value = import_contract(folder, args.contract, args.accept_policy_change, dry_run=True)
        try:
            from .contracts import require_ready
            require_ready(value)
            pending = None
        except ContractError as exc:
            pending = str(exc)
        from .contracts import estimate
        guess = estimate(value, reused=bool(Store(folder).state().get('reused_from'))) if pending is None else None
        return {'kind': 'check', 'target': 'contract', 'valid': True, 'ready': pending is None, 'estimate': guess,
                'next_action': pending or ('La propuesta es válida y está lista. Antes de importarla, dile al usuario: '
                                           + guess['text'] + ' Luego impórtala con ez continue --contract.')}
    from .audit import check_review_version, load_answers, review_claims
    state = Store(folder).state()
    contract = read_json(folder / 'research-contract.json')
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    review = read_json(args.review)
    check_review_version(review, state)
    claims = review_claims(review, state, contract, sources, load_answers(folder, state, contract, sources))
    return {'kind': 'check', 'target': 'review', 'valid': True, 'claims': len(claims),
            'next_action': 'La revisión es válida. Impórtala con ez continue --review; EZ verificará cada afirmación con NotebookLM.'}


PROVIDERS = ('pubmed', 'europepmc', 'openalex', 'semantic', 'crossref')
DEFAULT_STOP_RULE = 'Detenerse cuando cada pregunta QA tenga respuesta con citas del corpus o quede declarada como laguna.'


def plan_command(folder, args):
    """Build the plan from flags, so the host agent never writes contract JSON; validate it and return the estimate."""
    contract = read_json(folder / 'research-contract.json')
    questions = [q.strip() for q in args.qa or [] if q.strip()]
    if not questions:
        raise ContractError('Indica las preguntas QA con --qa "texto", una por subpregunta (entre 3 y 5).')
    queries = []
    for raw in args.query or []:
        provider, _, text = raw.partition(':')
        if provider.strip().lower() not in PROVIDERS or not text.strip():
            raise ContractError(f'Cada --query va como proveedor:texto, con proveedor en {", ".join(PROVIDERS)}: {raw!r}.')
        queries.append((provider.strip().lower(), text.strip()))
    if not queries and not args.reuse_only:
        raise ContractError('Indica al menos una búsqueda con --query proveedor:texto, o usa --reuse-only para responder '
                            'solo con los PDFs ya verificados.')
    scopes = [{'id': f'sq{i}', 'question': text, 'central': True} for i, text in enumerate(questions, 1)]
    ids = [s['id'] for s in scopes]
    contract['scope'] = scopes
    contract['plan'] = dict(contract['plan'], status='ready', delivery=args.delivery or contract['plan'].get('delivery', 'direct'),
                            discovery_mode='reuse_only' if args.reuse_only else 'search',
                            citation_expansion=not args.reuse_only and not args.no_citations,
                            queries=[{'id': f'q{i}', 'provider': p, 'text': t, 'scope_ids': ids, 'max_results': args.max_results}
                                     for i, (p, t) in enumerate(queries, 1)],
                            notebook_questions=[{'id': f'qa{i}', 'scope_ids': [f'sq{i}'], 'text': t} for i, t in enumerate(questions, 1)],
                            stop_rule=args.stop_rule or DEFAULT_STOP_RULE)
    for policy in contract['source_policies']:
        policy['scope_ids'] = [i for i in policy['scope_ids'] if i in ids] or ids
    text = json.dumps(contract, ensure_ascii=False, indent=2)
    path = contained(folder, f'proposals/contract-{sha256(text.encode()).hexdigest()[:16]}.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    args.contract, args.review, args.screening = path, None, None
    result = check_proposal(folder, args)
    if result['ready']:
        result['next_action'] = ('Plan válido. Muéstrale al usuario en pocas líneas las preguntas, dónde se busca y esto: '
                                 + result['estimate']['text'] + ' Con su visto bueno, ez continue ' + str(folder)
                                 + ' --contract ' + str(path) + '. Para cambiarlo, vuelve a usar ez plan.')
        result['choices'] = [{'label': 'Empezar', 'action': f'ez continue {folder} --contract {path}'},
                             {'label': 'Cambiar las preguntas', 'action': 'ez plan'}]
    return dict(result, proposal=str(path))


def split_group(raw):
    """'s1,s2: razón' -> (['s1', 's2'], 'razón')."""
    ids, _, reason = raw.partition(':')
    return [i.strip() for i in ids.split(',') if i.strip()], reason.strip()


def screen_document(folder, args):
    """Screening decisions from flags, checked against the current screening-request.json."""
    request_path = folder / 'screening-request.json'
    if not request_path.exists():
        raise ContractError('Esta corrida no espera cribado: no hay screening-request.json.')
    request = read_json(request_path)
    candidates = [c['source_id'] for c in request['candidates']]
    decisions = {}
    for decision, groups in (('include', args.include), ('exclude', args.exclude), ('uncertain', args.uncertain)):
        for raw in groups or []:
            ids, reason = split_group(raw)
            if not ids or not reason:
                raise ContractError(f'Cada --{decision} va como "id1,id2: razón breve": {raw!r}.')
            for source_id in ids:
                if source_id not in candidates:
                    raise ContractError(f'{source_id} no es un candidato de screening-request.json.')
                if source_id in decisions:
                    raise ContractError(f'{source_id} tiene más de una decisión.')
                decisions[source_id] = {'source_id': source_id, 'decision': decision, 'reason': reason}
    if args.exclude_rest:
        for source_id in candidates:
            decisions.setdefault(source_id, {'source_id': source_id, 'decision': 'exclude', 'reason': args.exclude_rest.strip()})
    for source_id in [i.strip() for i in (args.key or '').split(',') if i.strip()]:
        if decisions.get(source_id, {}).get('decision') != 'include':
            raise ContractError(f'--key solo marca candidatos incluidos: {source_id}.')
        decisions[source_id]['key'] = True
    undecided = [i for i in candidates if i not in decisions]
    if undecided:
        raise ContractError(f'Faltan decidir {len(undecided)} candidatos: {", ".join(undecided[:20])}. Decídelos o usa '
                            '--exclude-rest "razón".')
    document = {'schema_version': '2.0', 'sources_hash': request['sources_hash'], 'decisions': list(decisions.values())}
    text = json.dumps(document, ensure_ascii=False, indent=2)
    path = contained(folder, f'proposals/screening-{sha256(text.encode()).hexdigest()[:16]}.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


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


def ask_command(root, args):
    """A follow-up question answered by NotebookLM from the project's verified PDFs: no search, no download."""
    from .library import project_sources
    if not project_sources(root, args.project):
        raise ContractError(f'El proyecto «{args.project}» todavía no tiene PDFs verificados. Empieza con ez research.')
    cpath = context_path(root, args.project)
    context = read_json(cpath) if cpath.exists() else {'language': 'es', 'project': args.project}
    contract = draft(args.question, dict(context, project=args.project))
    contract['plan'].update(status='ready', delivery='direct', discovery_mode='reuse_only', queries=[],
                            notebook_questions=[{'id': 'ask1', 'scope_ids': ['sq1'], 'text': args.question}],
                            stop_rule='Pregunta de seguimiento respondida solo con la biblioteca del proyecto.')
    folder, _ = create_run(root, args.question, contract['context'], contract)
    with lock(folder):
        engine = Engine(folder)
        code = engine.execute()
        state = engine.state
    answer = read_json(folder / 'answer.json') if (folder / 'answer.json').exists() else {}
    evidence = sufficiency(answer)
    extra = {}
    if evidence != 'sufficient':
        command = f'ez research "{args.question}" --project {args.project} --plan-only'
        extra['choices'] = [{'label': 'Buscar artículos nuevos sobre esto', 'action': command + ' y luego ez plan'},
                            {'label': 'Quedarme con lo que hay', 'action': 'ninguna'}]
        extra['next_action'] = (
            ('La biblioteca del proyecto no responde esta pregunta. ' if evidence == 'insufficient' else
             'La biblioteca responde solo en parte: NotebookLM dice que a sus fuentes les falta algo. ')
            + 'Dile al usuario qué responde el corpus (con marcadores) y qué no, sin completar con memoria ni búsqueda web, y '
            'ofrécele buscar artículos nuevos con las opciones de choices.')
    else:
        extra['next_action'] = ('La biblioteca del proyecto responde la pregunta. Responde solo con estas afirmaciones y sus '
                                'marcadores [EZ:<id>]; no hace falta buscar artículos nuevos.')
    emit(dict(state, path=str(folder), kind='ask', evidence=evidence,
              claims=[{'id': c['id'], 'text': c['text'], 'marker': f'[EZ:{c["id"]}]'} for c in answer.get('claims', [])],
              uncited_statements=answer.get('uncited_statements', []), **extra), args.json)
    return code


# NotebookLM says so in an uncited sentence when its sources lack what was asked.
MISSING_PHRASES = ('no se menciona', 'no mencionan', 'no menciona', 'no contiene', 'no contienen', 'no se describe',
                   'no describen', 'no hay información', 'no proporciona', 'no proporcionan', 'no se encontr', 'no incluye',
                   'no incluyen', 'no aborda', 'no abordan', 'not mention', 'no information', 'not described', 'not provide',
                   'do not contain', 'does not contain', 'not discussed', 'not addressed')


def sufficiency(answer):
    """insufficient: no cited claim; partial: claims, but NotebookLM states its sources lack part of it; else sufficient."""
    if not answer.get('claims'):
        return 'insufficient'
    notes = ' '.join(n.get('text', '') for n in answer.get('uncited_statements', [])).casefold()
    return 'partial' if any(phrase in notes for phrase in MISSING_PHRASES) else 'sufficient'


def export_command(folder, args):
    """Read-only: write bibliography.bib or bibliography.ris next to the report."""
    from .deliver import bibliography, export_bibliography
    sources = read_json(folder / 'sources.json') if (folder / 'sources.json').exists() else []
    if args.all:
        chosen = [s for s in sources if s.get('notebook_status') == 'ready']
    else:
        answer = read_json(folder / 'answer.json') if (folder / 'answer.json').exists() else {}
        by_id = {s['source_id']: s for s in sources}
        chosen = [by_id.get(key, source) for key, (_, source, _) in sorted(bibliography(answer).items(), key=lambda i: i[1][0])
                  if source or key in by_id]
    if not chosen:
        raise ContractError('Todavía no hay fuentes citadas para exportar; usa --all para exportar el corpus.')
    path = folder / ('bibliography.' + ('ris' if args.format == 'ris' else 'bib'))
    path.write_text(export_bibliography(chosen, args.format), encoding='utf-8')
    emit({'kind': 'export', 'path': str(path), 'format': args.format, 'sources': len(chosen),
          'next_action': 'Importa ese archivo en Zotero, Mendeley o tu gestor de referencias.'}, args.json)
    return 0


def draft_command(folder, args):
    """Read-only: the verified claims to write from, or a check of a draft that cites them as [EZ:<id>]."""
    from .deliver import check_draft
    state = Store(folder).state()
    if not state or state.get('answer', {}).get('status') not in ('complete', 'partial'):
        raise ContractError('Todavía no hay afirmaciones verificadas para redactar.')
    answer = read_json(folder / 'answer.json')
    if answer.get('contract_hash') != state['contract_hash'] or answer.get('corpus_hash') != state.get('corpus_hash') \
            or answer.get('support_protocol') not in CURRENT_PROTOCOLS:
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
    p.add_argument('--unpaywall-email', help='Correo de contacto que Unpaywall exige para consultar acceso abierto.')
    p = sub.add_parser('context', help='Guardar preferencias y consultar investigaciones anteriores.'); p.add_argument('--project', default='general'); p.add_argument('--set', nargs=2, action='append', metavar=('FIELD', 'VALUE'))
    p = sub.add_parser('research', help='Iniciar una investigación con una pregunta.'); p.add_argument('question'); p.add_argument('--project', default='general'); p.add_argument('--plan-only', action='store_true'); p.add_argument('--contract', type=Path); p.add_argument('--reuse'); p.add_argument('--require-complete', action='store_true')
    p.add_argument('--update', metavar='CORRIDA', help='Actualizar una investigación anterior: reutiliza sus PDFs verificados, su plan y sus decisiones.')
    p = sub.add_parser('continue', help='Retomar una investigación guardada.'); p.add_argument('run'); p.add_argument('--contract', type=Path); p.add_argument('--accept-policy-change', action='store_true'); p.add_argument('--review', type=Path); p.add_argument('--require-complete', action='store_true')
    p.add_argument('--screening', type=Path, help='Decisiones del anfitrión sobre los candidatos de screening-request.json.')
    p.add_argument('--check', action='store_true', help='Validar la propuesta o la revisión sin modificar la corrida ni consultar servicios.')
    p.add_argument('--skip-missing', action='store_true', help='Seguir sin los PDFs que no se pudieron descargar.')
    p.add_argument('--verify', nargs='?', const='', metavar='IDS', help='Verificar afirmaciones de la entrega directa: '
                   'sin IDS, las 10 respaldadas por más fuentes; o IDs separados por comas.')
    p = sub.add_parser('plan', help='Armar el plan de una corrida con preguntas QA y búsquedas, sin escribir JSON.'); p.add_argument('run')
    p.add_argument('--qa', action='append', metavar='PREGUNTA', help='Pregunta para NotebookLM, una por subpregunta (repetible).')
    p.add_argument('--query', action='append', metavar='PROVEEDOR:TEXTO', help='Búsqueda, p. ej. pubmed:"ethambutol glutamicum" (repetible).')
    p.add_argument('--delivery', choices=['direct', 'verified']); p.add_argument('--stop-rule')
    p.add_argument('--reuse-only', action='store_true', help='Responder solo con los PDFs ya verificados, sin buscar.')
    p.add_argument('--max-results', type=int, default=25, choices=range(1, 101), metavar='1-100',
                   help='Resultados por búsqueda y proveedor (25 por defecto).')
    p.add_argument('--no-citations', action='store_true', help='No ampliar con los artículos que citan a los incluidos o que ellos citan.')
    p.add_argument('--accept-policy-change', action='store_true')
    p = sub.add_parser('screen', help='Decidir los candidatos del cribado sin escribir JSON.'); p.add_argument('run')
    p.add_argument('--include', action='append', metavar='"IDS: RAZÓN"'); p.add_argument('--exclude', action='append', metavar='"IDS: RAZÓN"')
    p.add_argument('--uncertain', action='append', metavar='"IDS: RAZÓN"'); p.add_argument('--exclude-rest', metavar='RAZÓN')
    p.add_argument('--key', metavar='IDS', help='Incluidos centrales para responder, separados por comas.')
    p.add_argument('--check', action='store_true', help='Validar sin modificar la corrida.')
    p = sub.add_parser('status', help='Ver el avance y el siguiente paso.'); p.add_argument('run'); p.add_argument('--answer', action='store_true')
    p = sub.add_parser('draft', help='Ver las afirmaciones verificadas para redactar o comprobar un borrador.'); p.add_argument('run'); p.add_argument('--check', type=Path, metavar='BORRADOR')
    p = sub.add_parser('ask', help='Pregunta de seguimiento respondida solo con los PDFs ya verificados del proyecto.')
    p.add_argument('question'); p.add_argument('--project', default='general')
    p = sub.add_parser('projects', help='Ver los proyectos y cuál se relaciona con una pregunta.')
    p.add_argument('--suggest', metavar='PREGUNTA', help='Ordenar los proyectos según su relación con esta pregunta.')
    p = sub.add_parser('export', help='Exportar la bibliografía a BibTeX o RIS.'); p.add_argument('run')
    p.add_argument('--format', choices=['bibtex', 'ris'], default='bibtex'); p.add_argument('--all', action='store_true', help='Todo el corpus, no solo lo citado.')
    p = sub.add_parser('verify', help='Revisar en persona afirmaciones entregadas.'); p.add_argument('run'); p.add_argument('--claim'); p.add_argument('--judgement', choices=['supported', 'partial', 'unsupported']); p.add_argument('--note')
    p = sub.add_parser('doctor', help='Diagnosticar problemas de una investigación.'); p.add_argument('run'); p.add_argument('--migration-preview', action='store_true'); p.add_argument('--migrate', metavar='PREVIEW_HASH'); p.add_argument('--remote', action='store_true'); p.add_argument('--metrics', action='store_true')
    p = sub.add_parser('rescue', help='Ver documentos pendientes o incorporar un PDF.'); p.add_argument('run'); p.add_argument('--import', dest='import_pdf'); p.add_argument('--import-folder'); p.add_argument('--source'); p.add_argument('--confirm-identity', action='store_true'); p.add_argument('--retry', action='store_true')
    p.add_argument('--origin'); p.add_argument('--origin-provider', choices=['repository', 'institution', 'publisher', 'user_import']); p.add_argument('--license'); p.add_argument('--source-version')
    p.add_argument('--reviewer', choices=['user', 'host_agent'], default='user')
    for command_parser in sub.choices.values():
        command_parser.add_argument('--json', action='store_true', default=argparse.SUPPRESS)
        command_parser.add_argument('--root', type=Path, default=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    load_environment()
    root = (args.root or data_root()).expanduser().resolve()
    load_user_config(root)
    try:
        guide = runtime_root() / 'docs/ez-user-guide.md'
        if args.guide:
            emit({'kind': 'user_guide', 'path': str(guide), 'text': guide.read_text(encoding='utf-8-sig')}, args.json)
            return 0
        if not args.command:
            emit(welcome(root, guide), args.json)
            return 0
        if args.command == 'setup':
            emit(prepare(root, args.check, args.install_notebooklm, args.unpaywall_email), args.json)
            return 0
        if args.command == 'projects':
            from .workspace import projects
            rows = projects(root, args.suggest)
            related = [r for r in rows if r.get('relatedness', 0) >= 0.3]
            if not args.suggest:
                hint = 'Proyectos guardados.' if rows else 'Todavía no hay proyectos; la primera pregunta crea uno.'
            elif related:
                top = related[0]
                hint = (f'La pregunta parece parte del proyecto «{top["project"]}» ({top["researches"]} investigaciones, '
                        f'{top["library_pdfs"]} PDFs verificados). Pregúntale al usuario si la suma ahí, reutilizando su '
                        'notebook y sus PDFs, o si prefiere un proyecto nuevo.')
            else:
                hint = 'Ningún proyecto existente se parece a esta pregunta. Propón un proyecto nuevo con un nombre corto.'
            emit({'kind': 'projects', 'projects': rows, 'next_action': hint}, args.json)
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
            from .workspace import ensure
            emit(dict(context, research_history=history(root, args.project), workspace=ensure(root, args.project)), args.json)
            return 0
        if args.command == 'ask':
            return ask_command(root, args)
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
        if args.command == 'export':
            return export_command(folder, args)
        if args.command == 'plan':
            with lock(folder):
                emit(plan_command(folder, args), args.json)
            return 0
        if args.command == 'screen':
            with lock(folder):
                args.screening = screen_document(folder, args)
            args.contract = args.review = args.verify = None
            args.command, args.skip_missing, args.require_complete, args.accept_policy_change = 'continue', False, False, False
        if args.command in ('status', 'doctor'):
            if args.command == 'status' and not args.answer:
                state = Store(folder).state()
                validate(state, 'run-state')
                if state.get('answer', {}).get('status') in ('complete', 'partial'):
                    answer_path = folder / 'answer.json'
                    report = read_json(answer_path) if answer_path.exists() else {}
                    if report.get('support_protocol') not in CURRENT_PROTOCOLS:
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
                    if report.get('support_protocol') not in CURRENT_PROTOCOLS:
                        emit(pending_passage_review(state), args.json)
                        return 2
                    extra = {'report_path': str(folder / 'report.md')} if (folder / 'report.md').exists() else {}
                    emit(dict(report, **extra, **({'workspace': state['workspace']} if state.get('workspace') else {})), args.json)
                else:
                    emit(state, args.json)
                return 0
        with lock(folder):
            Store(folder).recover(repair=True)
            if args.command == 'continue' and args.skip_missing:
                store = Store(folder); state = store.state()
                # Acknowledges the pause in force: the key-work request before downloads, or the missing-PDF list after.
                key_stage = 'NEEDS_KEY_PDFS' in state.get('legacy_signals', []) and not state.get('key_pdfs_acknowledged')
                store.append('decision', {'kind': 'continue_without_key_pdfs' if key_stage else 'continue_without_missing_pdfs',
                                          'actor': 'user'})
                state['key_pdfs_acknowledged' if key_stage else 'missing_pdfs_acknowledged'] = True
                store.update(state)
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
            if args.command == 'continue' and args.verify is not None:
                review = engine.review_from_direct([x.strip() for x in args.verify.split(',') if x.strip()] or None)
            screening = read_json(args.screening) if args.command == 'continue' and args.screening else None
            result = engine.execute(review, screening)
            emit(engine.state, args.json)
            return result
    except (ContractError, ValueError, OSError, KeyError) as exc:
        emit({'error': type(exc).__name__, 'next_action': str(exc), 'answer': {'status': 'unavailable'}}, args.json)
        return 4 if isinstance(exc, ContractError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
