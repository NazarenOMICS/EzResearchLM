"""Checkpointed research execution. The host plans; NotebookLM answers."""
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import shutil
import sys
import time

from .audit import ReviewError
from .contracts import ContractError, digest, require_ready, now, validate
from .paths import contained, executable
from .policies import evaluate
from .process import run
from .notebook_format import valid_response
from .state import Store, atomic_json, read_json


def numbers_missing(text, passages):
    """Numbers stated in a claim that appear in none of its passages (decimal comma or point)."""
    def numbers(value):
        return {n.replace(',', '.') for n in re.findall(r'(?<![\w.])\d+(?:[.,]\d+)?(?![\w])', value)}
    found = set().union(*(numbers(p) for p in passages)) if passages else set()
    return sorted(numbers(text) - found)


# NotebookLM's free plan accepts 50 sources per notebook.
NOTEBOOK_SOURCE_LIMIT = 50
# Local searches and downloads that run at the same time; each one is a separate process.
PARALLEL_WORKERS = 4
# How long EZ waits inside one call for NotebookLM to finish processing new PDFs.
READINESS_WAIT_SECONDS = 240
READINESS_POLL_SECONDS = 10


def notebook_reuse_enabled():
    return os.environ.get('EZ_NOTEBOOK_REUSE', '1').strip().lower() not in ('0', 'false', 'no')


def upload_title(source):
    return source['source_id'] + '-' + source['content_sha256'][:12] + '.pdf'


def same_content(remote, source):
    """Remote titles end with the first 12 hex characters of the PDF's SHA-256."""
    return remote.get('title', '').endswith('-' + source['content_sha256'][:12] + '.pdf')


def routes_tried(source):
    """Each provider EZ tried for a failed download, with the last reason it gave."""
    last = {}
    for attempt in source.get('attempts') or []:
        if isinstance(attempt, dict) and attempt.get('provider') and attempt.get('result') in ('failed', 'skipped'):
            last[attempt['provider']] = attempt.get('failure_code') or attempt['result']
    for provider, offered in (source.get('routes_consulted') or {}).items():
        if not offered and provider not in last:
            last[provider] = 'no_open_access_location'
    return [{'provider': provider, 'failure_code': code} for provider, code in last.items()]


class Pause(Exception):
    def __init__(self, reason, message, code=2, choices=None):
        self.reason, self.message, self.code, self.choices = reason, message, code, choices or []


# Answers the user can pick with one click when the agent's interface offers options.
PDF_CHOICES = [{'label': 'Ya dejé los PDFs en la bandeja', 'action': 'ez continue'},
               {'label': 'Seguir sin ellos', 'action': 'ez continue --skip-missing'},
               {'label': 'Abrir la bandeja', 'action': 'open the inbox_link'}]
DELIVERY_CHOICES = [{'label': 'Verificar lo central para redactar', 'action': 'ez continue --verify'},
                    {'label': 'Exportar la bibliografía a Zotero', 'action': 'ez export'},
                    {'label': 'Redactar un párrafo con estas citas', 'action': 'ez draft'},
                    {'label': 'Hacer otra pregunta en este proyecto', 'action': 'ez ask'}]


def doi_link(doi):
    return f'[{doi}](https://doi.org/{doi})' if doi else 'sin DOI registrado'



class Engine:
    def __init__(self, folder, runner=run):
        self.folder = Path(folder).resolve()
        self.store = Store(self.folder)
        self.store.recover(repair=True)
        self.state = self.store.state()
        if not self.state:
            raise ContractError('No hay estado EZ verificable para esta corrida.')
        validate(self.state, 'run-state')
        self.contract = read_json(self.folder / 'research-contract.json')
        if digest(self.contract) != self.state['contract_hash']:
            raise ContractError('El contrato cambió fuera del registro. Importa una revisión explícita.')
        require_ready(self.contract)
        self.runner = runner
        self.started = time.monotonic()
        self.used_before = self.state.get('elapsed_seconds', 0)
        self.sources = read_json(self.folder / 'sources.json') if (self.folder / 'sources.json').exists() else []
        validate(self.sources, 'source-manifest')

    def checkpoint(self, phase=None, **updates):
        if phase:
            self.state['phase'] = phase
        self.state.update(updates)
        self.state['elapsed_seconds'] = self.used_before + time.monotonic() - self.started
        self.state = self.store.update(self.state)

    def call(self, argv, seconds):
        remaining = self.contract['budgets']['run_seconds'] - self.used_before - (time.monotonic() - self.started)
        if remaining <= 0:
            raise Pause('budget_exhausted', 'Se agotó el presupuesto de tiempo de la corrida.', 3)
        result = self.runner(argv, timeout=min(seconds, remaining), cwd=self.folder)
        self.store.append('external_result', {'operation': str(argv[0]), 'command': str(argv[1]) if len(argv) > 1 else None,
                                              'exit_code': result.returncode, 'reason': result.reason})
        return result

    def call_many(self, commands, seconds):
        """Run independent local processes in parallel; the journal records them in order from this thread."""
        from concurrent.futures import ThreadPoolExecutor
        remaining = self.contract['budgets']['run_seconds'] - self.used_before - (time.monotonic() - self.started)
        if remaining <= 0:
            raise Pause('budget_exhausted', 'Se agotó el presupuesto de tiempo de la corrida.', 3)
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
            results = list(pool.map(lambda argv: self.runner(argv, timeout=min(seconds, remaining), cwd=self.folder), commands))
        for argv, result in zip(commands, results):
            self.store.append('external_result', {'operation': str(argv[0]), 'command': str(argv[1]) if len(argv) > 1 else None,
                                                  'exit_code': result.returncode, 'reason': result.reason})
        return results

    def notebook(self, args, seconds=60):
        # Every question starts a fresh conversation (--new): answers never depend on
        # earlier turns, including other runs' turns in a shared project notebook.
        command = executable('notebooklm')
        if not command:
            raise Pause('notebooklm_missing', 'Instala NotebookLM y ejecuta ez setup --check.')
        result = self.call([command, *args, '--json'], seconds)
        if result.returncode:
            output = (result.stdout + result.stderr).lower()
            if not result.reason and re.search(r'too large|too long|over-long|size limit', output):
                raise Pause('question_too_long', 'NotebookLM rechazó la pregunta por su tamaño. Acórtala o divídela en preguntas más breves.', 2)
            if not result.reason and re.search(r'quota|rate.?limit|too many requests|resource.?exhausted|usage limit|daily limit|\b429\b', output):
                raise Pause('quota_exhausted', 'NotebookLM alcanzó el límite de uso de tu cuenta. El trabajo quedó guardado; '
                            'continúa más tarde con ez continue.', 3)
            auth = not result.reason and bool(re.search(r'authentication|not authenticated|unauthorized|accounts\.google|login required|session expired',
                                                       output))
            raise Pause('auth_required' if auth else (result.reason or 'notebooklm_failed'),
                        'Renueva el acceso con notebooklm login.' if auth else 'NotebookLM no completó la operación; la corrida conserva su checkpoint.', 2 if auth else 3)
        try:
            value = json.loads(result.stdout)
        except ValueError as exc:
            raise Pause('invalid_notebooklm_output', 'NotebookLM devolvió un formato no reconocido. Si se repite, puede que NotebookLM '
                        'haya cambiado: actualiza EZ y notebooklm-py. El trabajo quedó guardado.', 3) from exc
        if not valid_response(value, args):
            raise Pause('invalid_notebooklm_output', 'La respuesta de NotebookLM no tiene el formato esperado. Si se repite, puede que '
                        'NotebookLM haya cambiado: actualiza EZ y notebooklm-py. El trabajo quedó guardado.', 3)
        return self.resolve_citations(value) if args[0] == 'ask' else value

    def resolve_citations(self, response):
        from .citation_resolution import quoted_candidates, resolve_quotes
        candidates = quoted_candidates(response)
        if not candidates:
            return response
        key = digest({'raw': response, 'corpus_hash': self.state['corpus_hash']})
        path = self.folder / 'citation-resolution' / (key + '.json')
        cached = self.state.get('citation_resolution_receipts', {}).get(key)
        if cached:
            if not path.exists() or sha256(path.read_bytes()).hexdigest() != cached:
                raise ContractError('La resolución de citas no coincide con su recibo.')
            return read_json(path)['resolved_response']
        known = {s['notebook_source_id'] for s in self.sources if s.get('notebook_status') == 'ready'}
        ids = {r['source_id'] for r in response['references'] if r.get('citation_number') in candidates}
        if not ids.issubset(known) or len(ids) > 20:
            return response
        fulltexts = {source_id: self.notebook(['source', 'fulltext', source_id, '--notebook', self.state['notebook_id']], 30)
                     for source_id in sorted(ids)}
        resolved = resolve_quotes(response, fulltexts)
        atomic_json(path, {'raw_response': response, 'source_snapshots': fulltexts, 'resolved_response': resolved,
                           'corpus_hash': self.state['corpus_hash'], 'method': 'unique_literal_quote'})
        receipts = dict(self.state.get('citation_resolution_receipts', {}))
        receipts[key] = sha256(path.read_bytes()).hexdigest()
        self.checkpoint(citation_resolution_receipts=receipts)
        return resolved

    def save_sources(self):
        validate(self.sources, 'source-manifest')
        self.state['sources_hash'] = digest(self.sources)
        self.state['elapsed_seconds'] = self.used_before + time.monotonic() - self.started
        self.state = self.store.commit(self.state, {'sources.json': self.sources})

    def discover(self):
        if self.state.get('discovery_complete'):
            return
        if self.contract['plan'].get('discovery_mode') == 'reuse_only':
            if not self.sources:
                # Answer from what the project already has: every verified PDF of its earlier researches.
                from .library import adopt
                for entry in self.library():
                    if not any(s.get('content_sha256') == entry['content_sha256'] for s in self.sources):
                        self.sources.append(adopt(self.folder, entry, {'screening': 'include',
                                                                       'screening_reason': 'Biblioteca del proyecto.'}))
                if self.sources:
                    self.save_sources()
            if not self.sources:
                raise ContractError('El plan requiere evidencia reutilizada, pero el proyecto todavía no tiene PDFs verificados.')
            self.checkpoint(discovery_complete=True)
            return
        self.checkpoint('discover')
        import search_topic
        records = []
        failures = []
        pending = {}
        for index, query in enumerate(self.contract['plan']['queries']):
            dest = self.folder / 'discovery' / str(index)
            dest.mkdir(parents=True, exist_ok=True)
            queries_file = dest / 'queries.json'
            atomic_json(queries_file, query)
            candidate_file = dest / 'candidate-sources.json'
            receipt_file = dest / 'receipt.json'
            receipt = read_json(receipt_file) if receipt_file.exists() else {}
            if receipt.get('query_hash') == digest(query):
                if not candidate_file.exists() or receipt.get('candidates_hash') != digest(read_json(candidate_file)):
                    raise Pause('NEEDS_TRACEABILITY_REPAIR', 'Los resultados de búsqueda no coinciden con su recibo.', 4)
            else:
                pending[index] = [sys.executable, '-m', 'ez.discovery', '--query', str(queries_file), '--output', str(candidate_file)]
        # One retry: providers often fail transiently (e.g. HTTP 429).
        reasons = {}
        for _ in range(2):
            retry = {}
            for index, result in zip(pending, self.call_many(list(pending.values()), 180) if pending else []):
                if result.returncode or not (self.folder / 'discovery' / str(index) / 'candidate-sources.json').exists():
                    retry[index] = pending[index]
                    reasons[index] = result.reason
                else:
                    query = self.contract['plan']['queries'][index]
                    candidate_file = self.folder / 'discovery' / str(index) / 'candidate-sources.json'
                    atomic_json(self.folder / 'discovery' / str(index) / 'receipt.json',
                                {'query_hash': digest(query), 'candidates_hash': digest(read_json(candidate_file)), 'at': now()})
            pending = retry
        for index in pending:
            # One provider down must not stop the research; record it and continue with the others.
            query = self.contract['plan']['queries'][index]
            failures.append({'query_id': query.get('id'), 'provider': query.get('provider'), 'reason': reasons.get(index) or 'provider_error'})
        for index, query in enumerate(self.contract['plan']['queries']):
            if index not in pending:
                records.extend(read_json(self.folder / 'discovery' / str(index) / 'candidate-sources.json')['candidates'])
        if failures and len(failures) == len(self.contract['plan']['queries']):
            raise Pause('discovery_failed', 'Ningún proveedor completó la búsqueda. Se conservaron los resultados anteriores; '
                        'reintenta con ez continue.', 3)
        self.checkpoint(discovery_failures=failures)
        # Rescue imports and migrated sources may precede discovery. Never erase
        # their identity decisions or existing remote IDs when merging results.
        for record in search_topic.dedupe_records(records):
            key = record.get('doi') or record.get('pmid') or record['title']
            source_id = 'src-' + sha256(key.lower().encode()).hexdigest()[:20]
            for policy in self.contract['source_policies']:
                if search_topic.same_identity(policy, record):
                    source_id = policy['source_id']
                    if policy.get('pmc_version') is not None:
                        record['pmc_version'] = policy['pmc_version']
            existing = next((s for s in self.sources if search_topic.same_identity(s, record)), None)
            if existing is None:
                existing = next((s for s in self.sources if s['source_id'] == source_id), None)
            if existing and not search_topic.same_identity(existing, record):
                conflict = {k: record.get(k) for k in ('title', 'doi', 'pmid', 'pmcid')}
                existing.setdefault('identifier_conflicts', []).append(conflict)
                existing['identity_status'] = 'needs_review'
                record['identifier_conflicts'] = [{k: existing.get(k) for k in ('title', 'doi', 'pmid', 'pmcid')}]
                source_id = source_id[:90] + '-' + digest(conflict)[:8]
                existing = None
            if existing:
                for key in ('pdf_url', 'pdf_urls', 'url'):
                    if not existing.get(key) and record.get(key):
                        existing[key] = record[key]
                continue
            self.sources.append(dict(record, source_id=source_id, acquisition_status='pending', identity_status='unknown',
                                     validation_status='unknown', notebook_status='pending', screening='pending'))
        # Explicitly identified obligations remain acquisition candidates even
        # when the discovery provider returned no match for the broad queries.
        for policy in self.contract['source_policies']:
            if any(s['source_id'] == policy['source_id'] for s in self.sources):
                continue
            if not any(policy.get(k) for k in ('doi', 'pmid', 'pmcid', 'title')):
                continue
            source = {k: policy[k] for k in ('source_id', 'title', 'doi', 'pmid', 'pmcid', 'pmc_version') if policy.get(k)}
            source.update(acquisition_status='pending', identity_status='unknown', validation_status='unknown', notebook_status='pending',
                          discovery_origin='explicit_contract_requirement', screening='include',
                          screening_reason='Fuente obligatoria del contrato.')
            self.sources.append(source)
        self.save_sources()
        self.checkpoint(discovery_complete=True)

    def project(self):
        return self.contract.get('context', {}).get('project') or 'general'

    def library(self):
        """Verified PDFs of the project's earlier researches (cached for this execution)."""
        if '_library' not in self.__dict__:
            from .library import project_sources
            self._library = project_sources(self.folder.parent, self.project(), self.state['run_id'])
        return self._library

    def reuse_library(self):
        """Included works already verified in another research of the project are copied, not downloaded again."""
        from .library import adopt, matching
        changed = False
        for index, source in enumerate(self.sources):
            if source.get('validation_status') == 'valid' or source.get('screening', 'include') != 'include':
                continue
            entry = matching(self.library(), source)
            if not entry or any(s.get('content_sha256') == entry['content_sha256'] for s in self.sources):
                continue
            keep = {k: source[k] for k in ('source_id', 'screening', 'screening_reason', 'key', 'open_access', 'queries', 'sources')
                    if k in source}
            self.sources[index] = adopt(self.folder, entry, keep)
            changed = True
        if changed:
            self.save_sources()

    def max_sources(self):
        from .contracts import DEFAULT_MAX_SOURCES
        return self.contract['budgets'].get('max_sources', DEFAULT_MAX_SOURCES)

    def screen(self, screening=None):
        """Only candidates the host includes are acquired; every decision keeps its reason as provenance."""
        if screening is not None:
            self.apply_screening(screening)
        pending = [s for s in self.sources if s.get('screening') == 'pending']
        if not pending:
            return
        self.open_access(pending)
        request = {'schema_version': '2.0', 'sources_hash': self.state['sources_hash'], 'max_sources': self.max_sources(),
                   'already_included': sum(s.get('screening', 'include') == 'include' for s in self.sources),
                   'candidates': [{k: s.get(k) for k in ('source_id', 'title', 'authors', 'year', 'journal', 'doi', 'pmid',
                                                         'pmcid', 'sources', 'queries', 'open_access') if s.get(k)}
                                  | ({'in_project': True} if self.in_library(s) else {})
                                  | ({'linked_to_included': len({l['seed'] for l in s['citation_links']})} if s.get('citation_links') else {})
                                  | ({'abstract': s['abstract'][:800]} if s.get('abstract') else {}) for s in pending],
                   'decisions': []}
        atomic_json(self.folder / 'screening-request.json', request)
        round_note = ('Segunda ronda: son artículos que citan a los incluidos o que ellos citan (linked_to_included dice a '
                      'cuántos). ') if all(s.get('discovery_origin') == 'citations' for s in pending) else ''
        raise Pause('NEEDS_SCREENING', round_note + f'Hay {len(pending)} candidatos por decidir en screening-request.json. Decídelos con '
                    'ez screen <run> --include "ids: razón" --exclude "ids: razón" (o --exclude-rest "razón") y --key con los '
                    'incluidos centrales para responder; no escribas el JSON a mano.', 2)

    CITATION_SEEDS = 15
    CITATION_CANDIDATES = 40

    def expand_citations(self):
        """Second screening round with the works the included sources cite or are cited by. Runs once per run."""
        plan = self.contract['plan']
        if not plan.get('citation_expansion') or plan.get('discovery_mode') == 'reuse_only' or self.state.get('citation_expansion'):
            return
        included = [s for s in self.sources if s.get('screening', 'include') == 'include' and (s.get('pmid') or s.get('doi'))]
        seeds = ([s for s in included if s.get('key')] + [s for s in included if not s.get('key')])[:self.CITATION_SEEDS]
        if not seeds:
            self.checkpoint(citation_expansion={'status': 'skipped', 'seeds': 0})
            return
        request, output = self.folder / 'discovery' / 'citations-request.json', self.folder / 'discovery' / 'citations.json'
        request.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(request, [{k: s.get(k) for k in ('source_id', 'doi', 'pmid')} for s in seeds])
        result = self.call([sys.executable, '-m', 'ez.citations', '--input', str(request), '--output', str(output)], 300)
        if result.returncode or not output.exists():
            # Expansion improves recall; its failure must not stop the research.
            self.checkpoint(citation_expansion={'status': 'failed', 'seeds': len(seeds), 'reason': result.reason or 'provider_error'})
            return
        import search_topic
        from .acquisition import normalize_doi
        from .workspace import topic_words
        found = read_json(output)
        words = topic_words(' '.join([self.contract['question']['original']] + [q['text'] for q in plan['queries']]
                                     + [q['text'] for q in plan['notebook_questions']]))
        merged = []
        for record in found.get('records', []):
            record['doi'] = normalize_doi(record.get('doi'))
            if any(search_topic.same_identity(s, record) for s in self.sources):
                continue
            match = next((m for m in merged if search_topic.same_identity(m, record)), None)
            if match is None:
                merged.append(record)
                continue
            match['links'] += record['links']
            for key, value in record.items():
                if value and not match.get(key):
                    match[key] = value
        ranked = []
        for record in merged:
            linked = len({link['seed'] for link in record['links']})
            overlap = len(words & topic_words(record['title'] + ' ' + (record.get('abstract') or '')))
            # Pointed to by two relevant papers, or about the same topic as the question.
            if linked >= 2 or overlap >= 2:
                ranked.append((linked * 2 + overlap, record))
        ranked.sort(key=lambda item: -item[0])
        chosen = [record for _, record in ranked[:self.CITATION_CANDIDATES]]
        for record in chosen:
            key = record.get('doi') or record.get('pmid') or record['title']
            links = record.pop('links')
            self.sources.append(dict(record, source_id='src-' + sha256(key.lower().encode()).hexdigest()[:20],
                                     discovery_origin='citations', citation_links=links, acquisition_status='pending',
                                     identity_status='unknown', validation_status='unknown', notebook_status='pending',
                                     screening='pending'))
        if chosen:
            self.save_sources()
        self.checkpoint(citation_expansion={'status': 'complete', 'seeds': len(seeds), 'found': len(merged), 'added': len(chosen),
                                            'failed_requests': found.get('failures', 0)})
        self.screen()

    def in_library(self, source):
        from .library import matching
        return matching(self.library(), source) is not None

    def open_access(self, pending):
        """Mark each candidate as open access or not, so screening can prefer PDFs EZ will be able to download."""
        unknown = [s for s in pending if 'open_access' not in s and s.get('doi')]
        if unknown:
            dois = self.folder / 'discovery' / 'open-access-request.json'
            output = self.folder / 'discovery' / 'open-access.json'
            atomic_json(dois, [s['doi'] for s in unknown])
            result = self.call([sys.executable, '-m', 'ez.openaccess', '--input', str(dois), '--output', str(output)], 120)
            status = read_json(output)['status'] if result.returncode == 0 and output.exists() else {}
            from .acquisition import normalize_doi
            for source in unknown:
                found = status.get(normalize_doi(source['doi']))
                source['open_access'] = ('yes' if found['is_oa'] else 'no') if found else 'unknown'
        for source in pending:
            if 'open_access' not in source:
                source['open_access'] = 'yes' if source.get('pdf_url') or source.get('pmcid') else 'unknown'
        self.save_sources()

    def apply_screening(self, screening, dry_run=False):
        from .audit import ReviewError
        if not isinstance(screening, dict) or screening.get('schema_version') != '2.0' or not isinstance(screening.get('decisions'), list):
            raise ReviewError('screening_invalid', 'El cribado debe tener schema_version 2.0 y una lista decisions.')
        if screening.get('sources_hash') != self.state.get('sources_hash'):
            raise ReviewError('screening_outdated', 'El cribado corresponde a otra versión de las fuentes. Usa el screening-request.json vigente.')
        by_id = {s['source_id']: s for s in self.sources}
        decided = {}
        for row in screening['decisions']:
            if not isinstance(row, dict) or row.get('source_id') not in by_id or row['source_id'] in decided:
                raise ReviewError('screening_invalid', f'Decisión inválida o repetida: {row!r:.120}')
            if row.get('key') not in (None, True, False):
                raise ReviewError('screening_invalid', f'key debe ser true o false en {row["source_id"]}.')
            if row.get('decision') not in ('include', 'exclude', 'uncertain') or not str(row.get('reason') or '').strip():
                raise ReviewError('screening_invalid', f'La fuente {row["source_id"]} necesita decision include, exclude o uncertain y una razón.')
            source = by_id[row['source_id']]
            if source.get('notebook_source_id') and row['decision'] != 'include':
                raise ReviewError('screening_invalid', f'{row["source_id"]} ya está en NotebookLM; excluirla requiere una corrida nueva.')
            decided[row['source_id']] = row
        included = {s['source_id'] for s in self.sources if s.get('screening', 'include') == 'include'}
        included = (included - {i for i, r in decided.items() if r['decision'] != 'include'}) | \
            {i for i, r in decided.items() if r['decision'] == 'include'}
        if len(included) > self.max_sources():
            raise ReviewError('screening_invalid', f'Se incluirían {len(included)} fuentes y el límite es {self.max_sources()}. '
                              'Excluye las menos relevantes o sube budgets.max_sources si tu plan de NotebookLM lo permite.')
        if dry_run:
            return {'decisions': len(decided), 'included': len(included)}
        for source_id, row in decided.items():
            by_id[source_id].update(screening=row['decision'], screening_reason=row['reason'].strip())
            if row['decision'] == 'include' and row.get('key') is True:
                by_id[source_id]['key'] = True
        self.store.append('decision', {'kind': 'screening', 'actor': 'host_agent', 'screening_hash': digest(screening),
                                       'decisions': len(decided)})
        self.save_sources()

    def acquire(self):
        self.checkpoint('acquire')
        budgets = self.contract['budgets']
        todo = [s for s in self.sources if not (s.get('validation_status') == 'valid' or s.get('acquisition_status') == 'manual_needed'
                                                or s.get('screening', 'include') != 'include')]
        commands = []
        for source in todo:
            dest = contained(self.folder, 'acquisition/' + source['source_id'])
            dest.mkdir(parents=True, exist_ok=True)
            atomic_json(dest / 'record.json', source)
            commands.append([sys.executable, '-m', 'ez.acquisition', '--record', str(dest / 'record.json'), '--output', str(dest / 'result.json'),
                             '--seconds', str(budgets['source_seconds']), '--attempts', str(budgets['attempts_per_route'])])
        for source, result in zip(todo, self.call_many(commands, budgets['source_seconds']) if commands else []):
            index = self.sources.index(source)
            result_path = contained(self.folder, 'acquisition/' + source['source_id']) / 'result.json'
            if result.returncode == 0 and result_path.exists():
                acquired = read_json(result_path)
                if acquired.get('source_id') != source['source_id'] or acquired.get('acquisition_input_hash') != digest(source):
                    raise ContractError('El resultado de adquisición no pertenece al intento actual.')
                twin = next((s for s in self.sources if s['source_id'] != acquired['source_id'] and acquired.get('content_sha256')
                             and s.get('content_sha256') == acquired['content_sha256']), None)
                if twin:
                    # The same bytes for two records usually means a landing page served another work's PDF.
                    acquired.update(identity_status='needs_review', duplicate_of=twin['source_id'])
                self.sources[index] = acquired
            else:
                source.update(acquisition_status='manual_needed', failure_code=result.reason or 'acquisition_failed')
            self.save_sources()

    def workspace(self):
        from .workspace import ensure
        return ensure(self.folder.parent, self.contract.get('context', {}).get('project') or 'general')

    def import_inbox(self):
        """Take PDFs the user left in the project's inbox for any included work still without one."""
        from .imports import INBOX_ORIGIN, import_folder
        paths = self.workspace()
        from .workspace import pdfs
        if not pdfs(paths['inbox']):
            return paths
        summary = import_folder(self.folder, self.store, self.sources, paths['inbox'], INBOX_ORIGIN)
        if summary['imported'] or summary['needs_identity_confirmation']:
            self.save_sources()
            self.checkpoint(inbox_import={k: summary[k] for k in ('imported', 'needs_identity_confirmation')})
        unconfirmed = [s for s in self.sources if s.get('validation_status') == 'valid' and s.get('identity_status') != 'verified'
                       and (s.get('provenance') or {}).get('origin') == INBOX_ORIGIN.origin and s.get('screening', 'include') == 'include']
        if unconfirmed:
            names = '; '.join(f'{s["source_id"]} ({s.get("title") or "sin título"})' for s in unconfirmed)
            raise Pause('NEEDS_IDENTITY_CONFIRMATION', 'EZ tomó de la bandeja PDFs que parecen corresponder a estos artículos, pero '
                        f'no pudo confirmar su identidad: {names}. Coteja título y autores de cada PDF y confírmalos con ez rescue '
                        '--confirm-identity --source id1,id2; luego continúa.', 2)
        return paths

    def request_key_pdfs(self):
        """Before downloading anything, name the key works with no open-access copy so the user can obtain them."""
        if self.state.get('key_pdfs_acknowledged'):
            return
        paths = self.import_inbox()
        required = {p['source_id'] for p in self.contract['source_policies'] if (p.get('effective_policy') or p['policy']) == 'hard_block'}
        closed = [s for s in self.sources if (s.get('key') or s['source_id'] in required) and s.get('screening', 'include') == 'include'
                  and s.get('open_access') == 'no' and s.get('validation_status') != 'valid']
        if not closed:
            return
        rows = [{k: v for k, v in (('source_id', s['source_id']), ('title', s.get('title')), ('year', s.get('year')),
                                   ('journal', s.get('journal')), ('doi', s.get('doi'))) if v} for s in closed]
        lines = ['# Artículos clave sin acceso abierto', '',
                 'Estos artículos son centrales para tu pregunta y no tienen una copia gratuita legal que EZ pueda descargar. '
                 'Conviene conseguirlos antes de seguir: sin ellos, la respuesta puede quedar incompleta.', '',
                 'Vías honestas para obtenerlos: el acceso de tu universidad o institución (entrando desde su red o su '
                 'proxy), el préstamo interbibliotecario de tu biblioteca, o pedírselo por correo a los autores, que '
                 'suelen enviarlo.', '']
        for row in rows:
            detail = ', '.join(str(row[k]) for k in ('journal', 'year') if row.get(k))
            lines.append(f'- **{row.get("title") or row["source_id"]}**' + (f' ({detail})' if detail else '') + f' — DOI {doi_link(row.get("doi"))}')
        lines += ['', f'Cuando los tengas, guárdalos en la bandeja de tu proyecto: [{paths["inbox"]}]({paths["inbox_link"]}) y dile '
                  'a EZ que siga. Si no puedes conseguirlos, dile que siga sin ellos.']
        atomic_json(self.folder / 'key-pdfs.json', {'schema_version': '1.0', 'closed_access': rows})
        (self.folder / 'key-pdfs.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.checkpoint(missing_pdfs=[dict(r, doi_url=f'https://doi.org/{r["doi"]}' if r.get('doi') else None) for r in rows])
        raise Pause('NEEDS_KEY_PDFS', f'{len(closed)} artículos clave no tienen acceso abierto. Muéstrale al usuario la lista de '
                    'key-pdfs.md tal cual: título completo sin traducir ni resumir y el DOI de cada uno como enlace. Agrega el '
                    f'enlace a su bandeja ({paths["inbox_link"]}). Cuando deje los PDFs ahí, continúa: EZ los toma solo. Si '
                    'no los consigue, continúa con ez continue --skip-missing.', 2, PDF_CHOICES)

    def request_pdfs(self):
        """Ask once, before anything is uploaded, for the included works EZ could not download."""
        if self.state.get('missing_pdfs_acknowledged'):
            return
        paths = self.import_inbox()
        missing = [s for s in self.sources if s.get('screening', 'include') == 'include' and s.get('acquisition_status') == 'manual_needed'
                   and s.get('validation_status') != 'valid']
        if not missing:
            return
        rows = [{k: v for k, v in (('source_id', s['source_id']), ('title', s.get('title')), ('year', s.get('year')),
                                   ('doi', s.get('doi')), ('reason', s.get('failure_code'))) if v} for s in missing]
        lines = ['# PDFs que EZ no pudo descargar', '',
                 'Estos artículos entraron en la investigación pero no tienen una copia de acceso abierto que EZ pueda '
                 'bajar. Si tienes alguno (de tu biblioteca, tu institución o pedido a los autores), guárdalo en la bandeja '
                 f'de tu proyecto: [{paths["inbox"]}]({paths["inbox_link"]}) y dile a EZ que siga. Si no, EZ sigue sin '
                 'ellos y lo dice en el informe.', '']
        for row in rows:
            lines.append(f'- **{row.get("title") or row["source_id"]}**' + (f' ({row["year"]})' if row.get('year') else '')
                         + f' — DOI {doi_link(row.get("doi"))}')
        atomic_json(self.folder / 'pdf-request.json', {'schema_version': '1.0', 'missing': rows})
        (self.folder / 'pdf-request.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.checkpoint(missing_pdfs=[dict(r, doi_url=f'https://doi.org/{r["doi"]}' if r.get('doi') else None) for r in rows])
        raise Pause('NEEDS_USER_PDFS', f'{len(missing)} artículos incluidos no tienen PDF de acceso abierto. Muéstrale al usuario la '
                    'lista de pdf-request.md tal cual: título completo sin traducir ni resumir y el DOI de cada uno como enlace. '
                    f'Agrega el enlace a su bandeja ({paths["inbox_link"]}). Si los consigue y los deja ahí, continúa: EZ los toma '
                    'solo. Si no, continúa con ez continue --skip-missing.', 2, PDF_CHOICES)

    def upload(self):
        verified = [s for s in self.sources if s.get('validation_status') == 'valid' and s.get('identity_status') == 'verified'
                    and s.get('screening', 'include') == 'include']
        if len(verified) > self.max_sources():
            raise Pause('corpus_limit', f'El corpus tendría {len(verified)} fuentes y el límite es {self.max_sources()}. '
                        'Excluye fuentes con ez continue --screening antes de subirlas.', 2)
        if not verified:
            raise Pause('NEEDS_SOURCE_REVIEW' if any(s.get('validation_status') == 'valid' for s in self.sources) else 'NEEDS_CORPUS',
                        'Faltan PDFs validados y con identidad verificada. Usa ez rescue para revisar o importar fuentes.')
        self.checkpoint('upload')
        if not self.state.get('notebook_id'):
            shared = self.project_notebook(verified) if notebook_reuse_enabled() else None
            if shared:
                self.store.append('decision', {'kind': 'reuse_project_notebook', 'actor': 'ez', 'notebook_id': shared})
                self.checkpoint(notebook_id=shared, notebook_shared=True)
            else:
                self.create_notebook()
        notebook_id = self.state['notebook_id']
        shared = bool(self.state.get('notebook_shared'))
        remote = self.notebook(['source', 'list', '--notebook', notebook_id]).get('sources', [])
        known_ids = {s.get('notebook_source_id') for s in self.sources if s.get('notebook_source_id')}
        known_titles = {upload_title(s) for s in self.sources if s.get('content_sha256')}
        # A project notebook holds other runs' sources; queries pass --source, so they never mix.
        if not shared and any(s.get('id') not in known_ids and s.get('title') not in known_titles for s in remote):
            raise Pause('remote_corpus_drift', 'El notebook contiene fuentes sin reconciliar. Revisa el corpus antes de añadir documentos.', 4)
        for source in verified:
            # Verify local bytes again before sending them outside the machine.
            path = Path(source['pdf_path'])
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != source['content_sha256']:
                raise Pause('NEEDS_TRACEABILITY_REPAIR', 'Un PDF cambió después de validarlo.', 4)
            title = upload_title(source)
            if shared:
                matches = sorted((s for s in remote if s.get('id') == source.get('notebook_source_id') or same_content(s, source)),
                                 key=lambda s: (str(s.get('status', '')).lower() not in ('ready', 'completed', 'available'), s['id']))[:1]
            else:
                matches = [s for s in remote if s.get('id') == source.get('notebook_source_id') or s.get('title') == title]
            if len(matches) > 1:
                raise Pause('remote_reconciliation', 'NotebookLM tiene fuentes duplicadas; revisa antes de continuar.')
            if matches:
                source['notebook_source_id'] = matches[0]['id']
            elif source.get('upload_pending') or source.get('notebook_source_id'):
                raise Pause('remote_reconciliation', 'Una subida previa no aparece en NotebookLM. Revisa antes de repetirla.')
            else:
                # File uploads can ignore --title. Give the actual upload file
                # its deterministic reconciliation name while preserving the PDF.
                staged = contained(self.folder, 'upload/' + title)
                staged.parent.mkdir(exist_ok=True)
                if not staged.exists():
                    shutil.copyfile(path, staged)
                if sha256(staged.read_bytes()).hexdigest() != source['content_sha256']:
                    raise Pause('NEEDS_TRACEABILITY_REPAIR', 'La copia preparada para subida cambió.', 4)
                source['upload_pending'] = True
                self.save_sources()
                try:
                    data = self.notebook(['source', 'add', '--notebook', notebook_id, '--type', 'file', '--mime-type', 'application/pdf', '--title', title, str(staged)], 180)
                except Pause as exc:
                    if exc.reason in ('auth_required', 'notebooklm_missing', 'quota_exhausted'):
                        source['upload_pending'] = False
                        self.save_sources()
                    raise
                source_id = data.get('id') or data.get('source', {}).get('id')
                if not source_id:
                    raise Pause('remote_reconciliation', 'NotebookLM no devolvió un ID de fuente verificable.')
                source['notebook_source_id'] = source_id
            source['upload_pending'] = False
            self.save_sources()
        self.register_notebook(verified)
        self.checkpoint('readiness')
        expected = {s['notebook_source_id'] for s in verified}
        # A source that already outlasted one full wait is checked again but never waited for.
        stuck_before = {s['notebook_source_id'] for s in verified if s.get('notebook_status') == 'processing_stuck'}
        deadline = time.monotonic() + READINESS_WAIT_SECONDS
        while True:
            # Wait here for NotebookLM to process new PDFs instead of handing the wait back to the agent.
            remote = self.notebook(['source', 'list', '--notebook', notebook_id]).get('sources', [])
            actual = {s.get('id') for s in remote}
            if (not expected <= actual) if shared else actual != expected:
                raise Pause('remote_corpus_drift', 'El corpus remoto incluye fuentes ausentes o no registradas. Revisa su composición.', 4)
            ready = {s['id'] for s in remote if str(s.get('status', '')).lower() in ('ready', 'completed', 'available')} & expected
            if expected - stuck_before <= ready or time.monotonic() + READINESS_POLL_SECONDS > deadline:
                break
            time.sleep(READINESS_POLL_SECONDS)
        waiting = expected - ready
        # A few PDFs stuck in NotebookLM's processing must not hold the whole research:
        # they leave the corpus with their reason and are checked again on the next continue.
        if not ready or len(waiting) > max(1, len(expected) // 5):
            for source in verified:
                source['notebook_status'] = 'ready' if source['notebook_source_id'] in ready else 'processing'
            self.save_sources()
            raise Pause('waiting_on_processing', 'NotebookLM todavía procesa fuentes. Ejecuta ez continue más adelante.', 3)
        for source in verified:
            source['notebook_status'] = 'ready' if source['notebook_source_id'] in ready else 'processing_stuck'
        self.save_sources()
        corpus = [s for s in verified if s['notebook_status'] == 'ready']
        self.checkpoint(corpus_hash=digest(sorted((s['source_id'], s['content_sha256'], s['notebook_source_id']) for s in corpus)),
                        corpus_exclusions=self.exclusions())

    def create_notebook(self):
        title = 'EZ ' + self.state['run_id']
        if self.state.get('pending_operation') == 'create_notebook':
            notebooks = self.notebook(['list']).get('notebooks', [])
            matches = [n for n in notebooks if n.get('title') == title]
            if len(matches) != 1:
                raise Pause('remote_reconciliation', 'La creación anterior no tiene resultado inequívoco. Revisa el notebook antes de repetir.')
            self.checkpoint(notebook_id=matches[0]['id'], pending_operation=None)
            return
        self.checkpoint(pending_operation='create_notebook')
        try:
            data = self.notebook(['create', title])
        except Pause as exc:
            if exc.reason in ('auth_required', 'notebooklm_missing', 'quota_exhausted'):
                self.checkpoint(pending_operation=None)
            raise
        notebook_id = data.get('id') or data.get('notebook', {}).get('id')
        if not notebook_id:
            raise Pause('remote_reconciliation', 'No se pudo identificar el notebook creado.')
        self.checkpoint(notebook_id=notebook_id, pending_operation=None, notebook_shared=notebook_reuse_enabled())

    def library_path(self):
        project = re.sub(r'[^A-Za-z0-9_-]+', '-', str(self.contract.get('context', {}).get('project') or 'general')).strip('-') or 'general'
        return self.folder.parent / 'projects' / project / 'notebooks.json'

    def project_notebook(self, verified):
        """The project's latest notebook when this corpus still fits in it; uploads then cover only new PDFs."""
        path = self.library_path()
        library = read_json(path) if path.exists() else {}
        notebooks = library.get('notebooks', [])
        if not notebooks:
            return None
        notebook_id = notebooks[-1]['notebook_id']
        try:
            remote = self.notebook(['source', 'list', '--notebook', notebook_id]).get('sources', [])
        except Pause as exc:
            if exc.reason in ('auth_required', 'notebooklm_missing', 'quota_exhausted'):
                raise
            return None  # The notebook was deleted or is unreadable: start a new one.
        missing = [s for s in verified if not any(same_content(r, s) for r in remote)]
        return notebook_id if len(remote) + len(missing) <= NOTEBOOK_SOURCE_LIMIT else None

    def register_notebook(self, verified):
        if not self.state.get('notebook_shared'):
            return
        from .state import lock
        path = self.library_path()
        with lock(path.parent):
            library = read_json(path) if path.exists() else {'schema_version': '1.0', 'notebooks': []}
            entry = next((n for n in library['notebooks'] if n['notebook_id'] == self.state['notebook_id']), None)
            if entry is None:
                entry = {'notebook_id': self.state['notebook_id'], 'created_by_run': self.state['run_id'], 'runs': [], 'sources': {}}
                library['notebooks'].append(entry)
            if self.state['run_id'] not in entry['runs']:
                entry['runs'].append(self.state['run_id'])
            entry['sources'].update({upload_title(s): s['notebook_source_id'] for s in verified})
            atomic_json(path, library)

    def exclusions(self):
        """Sources that stayed outside the corpus, with the reason the user can act on."""
        result = []
        for source in self.sources:
            screening = source.get('screening', 'include')
            if screening == 'include' and source.get('validation_status') == 'valid' and source.get('identity_status') == 'verified' \
                    and source.get('notebook_status') != 'processing_stuck':
                continue
            if screening != 'include':
                reason = {'exclude': 'excluded_by_screening', 'uncertain': 'screening_uncertain'}.get(screening, 'not_screened')
            elif source.get('notebook_status') == 'processing_stuck':
                reason = 'processing_stuck'
            elif source.get('duplicate_of'):
                reason = 'duplicate_content'
            elif source.get('validation_status') == 'valid':
                reason = 'identity_unconfirmed'
            elif source.get('acquisition_status') == 'manual_needed':
                reason = source.get('failure_code') or 'acquisition_failed'
            else:
                reason = 'not_acquired'
            result.append({k: v for k, v in (('source_id', source['source_id']), ('title', source.get('title')),
                                              ('doi', source.get('doi')), ('reason', reason),
                                              ('detail', source.get('screening_reason') if screening != 'include' else None),
                                              ('routes', routes_tried(source) if source.get('acquisition_status') == 'manual_needed'
                                               else None)) if v})
        return result

    def blocking_policies(self, question):
        return [p for p in self.contract['source_policies'] if set(p['scope_ids']) & set(question['scope_ids']) and
                (p.get('effective_policy') or p['policy']) in ('hard_block', 'contextual') and
                not any(s['source_id'] == p['source_id'] and s.get('notebook_status') == 'ready' for s in self.sources)]

    def page_of(self, source, passage):
        from .pages import find_page, page_texts
        path = source.get('pdf_path')
        if not path or not Path(path).is_file():
            return None
        cache = self.__dict__.setdefault('_pages', {})
        if path not in cache:
            cache[path] = page_texts(path)
        return find_page(passage, cache[path])

    def bibliography(self, refs):
        by_remote = {s.get('notebook_source_id'): s for s in self.sources if s.get('notebook_source_id')}
        result = []
        for ref in refs:
            source = by_remote.get(ref['source_id'])
            if not source:
                result.append(ref)
                continue
            provenance = source.get('provenance') or {}
            fields = {'source_id': source['source_id'], 'title': source.get('title'), 'authors': source.get('authors'),
                      'year': source.get('year'), 'journal': source.get('journal'), 'doi': source.get('doi'),
                      'pmid': source.get('pmid'), 'pmcid': source.get('pmcid'), 'content_sha256': source.get('content_sha256'),
                      'pdf_path': source.get('pdf_path'), 'pdf_source': source.get('pdf_source'),
                      'origin_url': provenance.get('final_url') or provenance.get('origin'),
                      'source_version': provenance.get('source_version')}
            page = self.page_of(source, ref.get('cited_text') or '')
            result.append(dict(ref, source={k: v for k, v in fields.items() if v not in (None, '', [])}, **({'page': page} if page else {})))
        return result

    def qa(self, review=None):
        self.checkpoint('qa')
        qa_dir = self.folder / 'qa'
        qa_dir.mkdir(exist_ok=True)
        manifest = read_json(qa_dir / 'manifest.json') if (qa_dir / 'manifest.json').exists() else {}
        if manifest and digest(manifest) != self.state.get('qa_manifest_hash'):
            raise ContractError('El manifiesto QA cambió fuera del registro.')
        if manifest.get('corpus_hash') != self.state['corpus_hash']:
            if manifest:
                atomic_json(qa_dir / ('manifest-' + manifest['corpus_hash'] + '.json'), manifest)
            manifest = {'corpus_hash': self.state['corpus_hash'], 'answers': []}
        remote_ids = [s['notebook_source_id'] for s in self.sources if s.get('notebook_status') == 'ready']
        for question in self.contract['plan']['notebook_questions']:
            qhash = digest(question)
            existing = next((q for q in manifest['answers'] if q['question_hash'] == qhash), None)
            if existing:
                old_path = contained(self.folder, existing['path'])
                if sha256(old_path.read_bytes()).hexdigest() != existing['sha256']:
                    raise ContractError('Una respuesta QA cambió antes de resolver sus citas.')
                original = read_json(old_path)
                resolved = self.resolve_citations(original)
                if resolved != original:
                    path = qa_dir / ('resolved-' + digest(resolved) + '.json')
                    atomic_json(path, resolved)
                    existing.update(raw_path=existing.get('raw_path', existing['path']), path=str(path.relative_to(self.folder)),
                                    sha256=sha256(path.read_bytes()).hexdigest())
                    self.state['qa_manifest_hash'] = digest(manifest)
                    self.state = self.store.commit(self.state, {'qa/manifest.json': manifest})
                continue
            if self.blocking_policies(question):
                continue
            pending = sum(1 for q in self.contract['plan']['notebook_questions']
                          if not any(a['question_hash'] == digest(q) for a in manifest['answers']))
            self.checkpoint(next_action=f'Consultando NotebookLM: quedan {pending} preguntas. Cada una tarda alrededor de un '
                                        'minuto, lo mismo que en la web de NotebookLM.')
            args = ['ask', '--notebook', self.state['notebook_id'], '--new']
            for source_id in remote_ids:
                args += ['--source', source_id]
            args += [question['text'] + '\nCita las fuentes que respaldan cada afirmación y declara explícitamente lo que el corpus no permite responder.']
            response = self.notebook(args, 180)
            path = qa_dir / (self.state['corpus_hash'][:12] + '-' + qhash[:12] + '.json')
            atomic_json(path, response)
            manifest['answers'].append({'question_id': question['id'], 'question_hash': qhash, 'scope_ids': question['scope_ids'],
                                        'path': str(path.relative_to(self.folder)), 'sha256': sha256(path.read_bytes()).hexdigest()})
            self.state['qa_manifest_hash'] = digest(manifest)
            self.store.commit(self.state, {'qa/manifest.json': manifest})
        if not manifest['answers']:
            # A valid empty manifest is a record of withheld work, never a PASS.
            self.state['qa_manifest_hash'] = digest(manifest)
            self.store.commit(self.state, {'qa/manifest.json': manifest})
        if review is not None:
            return self.finalize(review)
        prior_review = self.state.get('review_hash')
        if prior_review:
            prior = read_json(self.folder / 'reviews' / (prior_review + '.json'))
            if prior['contract_hash'] == self.state['contract_hash'] and prior['corpus_hash'] == self.state['corpus_hash']:
                return self.finalize(prior)
        # Host must inspect NotebookLM exports before making a coverage/support claim.
        template = {'schema_version': '2.0', 'contract_hash': self.state['contract_hash'], 'corpus_hash': self.state['corpus_hash'],
                    'reviewer': {'kind': 'host_agent', 'name': 'EZ'},
                    'coverage': [{'scope_id': s['id'], 'status': 'unknown', 'rationale': 'Pendiente de revisión QA',
                                  'limitations': ['La cobertura todavía no fue evaluada.']} for s in self.contract['scope']], 'claims': []}
        request_path = self.folder / 'review-request.json'
        # This is a proposal workspace, not a canonical artifact: preserve edits
        # while it still matches the corpus, archive it once the corpus changes.
        current = read_json(request_path) if request_path.exists() else None
        if current is not None and (current.get('contract_hash'), current.get('corpus_hash')) != (template['contract_hash'], template['corpus_hash']):
            atomic_json(self.folder / ('review-request-' + str(current.get('corpus_hash') or 'unknown')[:12] + '.json'), current)
            current = None
        if current is None:
            atomic_json(request_path, template)
        if self.contract['plan'].get('delivery') == 'direct':
            return self.finalize_direct()
        excluded = len(self.state.get('corpus_exclusions', []))
        note = f' {excluded} fuentes quedaron fuera del corpus; ez rescue muestra cuáles y por qué.' if excluded else ''
        self.checkpoint('audit', execution={'status': 'waiting_user'}, legacy_signals=['NEEDS_QA_REVIEW'],
                        integrity={'status': 'pending'}, answer={'status': 'unavailable'},
                        next_action='El agente anfitrión debe revisar QA y completar una copia de review-request.json; luego usar ez continue --review. Aún no hay respuesta aprobada.' + note)
        return 2

    def verification_batches(self, claims):
        from .audit import VERIFICATION_BATCH_SIZE, VERIFICATION_PROMPT_LIMIT, verification_prompt
        batches, current = [], []
        for claim in claims:
            candidate = current + [claim]
            if current and (len(candidate) > VERIFICATION_BATCH_SIZE or len(verification_prompt(candidate)) > VERIFICATION_PROMPT_LIMIT):
                batches.append(current)
                candidate = [claim]
            current = candidate
        return batches + ([current] if current else [])

    def verify(self, batch):
        """One NotebookLM verdict question per batch, cached by receipt; oversized questions are split."""
        from .audit import SUPPORT_PROTOCOL, batch_verdicts, verification_prompt
        key = digest({'claims': batch, 'contract_hash': self.state['contract_hash'], 'corpus_hash': self.state['corpus_hash'],
                      'support_protocol': SUPPORT_PROTOCOL})
        path = self.folder / 'verification' / (key + '.json')
        cached = self.state.get('verification_receipts', {}).get(key)
        if cached:
            if not path.exists() or sha256(path.read_bytes()).hexdigest() != cached:
                raise ContractError('La QA de respaldo no coincide con su recibo.')
            response = read_json(path)
        else:
            args = ['ask', '--notebook', self.state['notebook_id'], '--new']
            for source_id in sorted({r['source_id'] for c in batch for r in c['references']}):
                args += ['--source', source_id]
            try:
                response = self.notebook([*args, verification_prompt(batch)], 180)
            except Pause as exc:
                if exc.reason != 'question_too_long':
                    raise
                if len(batch) == 1:
                    return {batch[0]['id']: {'verdict': 'unverified', 'stated_verdict': None, 'batch_size': 1,
                                             'reason': 'verification_question_too_long'}}
                half = len(batch) // 2
                return {**self.verify(batch[:half]), **self.verify(batch[half:])}
            atomic_json(path, response)
            receipts = dict(self.state.get('verification_receipts', {}))
            receipts[key] = sha256(path.read_bytes()).hexdigest()
            self.checkpoint(verification_receipts=receipts)
        receipt = {'path': str(path.relative_to(self.folder)), 'sha256': self.state['verification_receipts'][key]}
        return {claim_id: dict(verdict, **receipt) for claim_id, verdict in batch_verdicts(response, self.sources, batch).items()}

    def fulltexts(self, source_ids):
        """NotebookLM's indexed text of each source, kept with a receipt for literal checks."""
        result = {}
        receipts = dict(self.state.get('fulltext_receipts', {}))
        for source_id in sorted(source_ids):
            key = digest({'source_id': source_id, 'corpus_hash': self.state['corpus_hash']})
            path = self.folder / 'verification' / ('fulltext-' + key + '.json')
            if receipts.get(key):
                if not path.exists() or sha256(path.read_bytes()).hexdigest() != receipts[key]:
                    raise ContractError('El texto indexado de una fuente no coincide con su recibo.')
                result[source_id] = read_json(path)
                continue
            snapshot = self.notebook(['source', 'fulltext', source_id, '--notebook', self.state['notebook_id']], 30)
            atomic_json(path, snapshot)
            receipts[key] = sha256(path.read_bytes()).hexdigest()
            self.checkpoint(fulltext_receipts=receipts)
            result[source_id] = snapshot
        return result

    def evidence(self, claim, verdict):
        """QA passages plus the passages the verification cited, each with bibliography and a literal check."""
        from .audit import found_in
        from .audit import normalize_text
        refs = [dict(r, role='qa') for r in claim['references']]
        seen = {(r['source_id'], normalize_text(r['cited_text'])) for r in refs}
        for ref in verdict.get('passages', []):
            if (ref['source_id'], normalize_text(ref['cited_text'])) not in seen:
                seen.add((ref['source_id'], normalize_text(ref['cited_text'])))
                refs.append(dict(ref, role='verification'))
        if verdict.get('grounding') == 'quote_in_fulltext':
            refs.append({'source_id': verdict['quote']['source_id'], 'citation_number': None,
                         'cited_text': verdict['quote']['quote'], 'role': 'verification_quote'})
        try:
            texts = self.fulltexts({r['source_id'] for r in refs})
        except Pause as exc:
            if exc.reason in ('auth_required', 'quota_exhausted', 'notebooklm_missing'):
                raise
            texts = {}  # The literal check is extra transparency; its absence is recorded, not fatal.
        for ref in refs:
            snapshot = texts.get(ref['source_id'])
            ref['found_in_fulltext'] = found_in(ref['cited_text'], snapshot['content']) if snapshot else None
        return self.bibliography(refs)

    def human_check(self, claim):
        """A person's judgement binds the claim only while its text is unchanged."""
        check = self.state.get('human_checks', {}).get(claim['id'])
        return check if check and check.get('claim_hash') == digest(claim['text']) else None

    def changes(self, delivered):
        """What an update added, kept or dropped compared with the previous run's delivered claims."""
        path = self.folder / 'previous-answer.json'
        if not path.exists():
            return None
        from .audit import normalize_text
        previous = read_json(path)
        key = lambda claim: normalize_text(claim['text']).casefold()
        before = {key(c): c for c in previous.get('claims', [])}
        now = {key(c): c for c in delivered}
        new_sources = sorted({s.get('title') or s['source_id'] for s in self.sources if s.get('notebook_status') == 'ready'
                              and not s.get('reused_from')})
        return {'previous_run': self.state.get('previous_run', {}).get('run_id'),
                'new': [c['id'] for k, c in now.items() if k not in before],
                'kept': [c['id'] for k, c in now.items() if k in before],
                'dropped': [{'id': c['id'], 'text': c['text']} for k, c in before.items() if k not in now],
                'new_sources': new_sources}

    def apply_human_check(self, claim_id, judgement, note=None):
        """Record a person's reading of a delivered claim; an unsupported judgement withdraws it."""
        answer = read_json(self.folder / 'answer.json')
        claim = next((c for c in answer.get('claims', []) if c['id'] == claim_id), None)
        if claim is None:
            raise ContractError('Solo se pueden revisar afirmaciones entregadas en la respuesta vigente.')
        check = {'judgement': judgement, 'note': note or '', 'actor': 'user', 'at': now(), 'claim_hash': digest(claim['text'])}
        checks = dict(self.state.get('human_checks', {}), **{claim_id: check})
        self.store.append('decision', {'kind': 'human_check', 'actor': 'user', 'claim_id': claim_id, 'judgement': judgement})
        self.state['human_checks'] = checks
        if answer.get('delivery') == 'direct':
            return self.finalize_direct()
        review = read_json(self.folder / 'reviews' / (self.state['review_hash'] + '.json'))
        return self.finalize(review)

    NO_ACCESS = {'paywall', 'access_denied', 'auth_required', 'captcha_or_challenge', 'no_open_access_location'}

    def gaps(self, result, review, withheld):
        """Why each unanswered scope is unanswered: no access, failed download, unverified claims or thin evidence."""
        by_id = {s['source_id']: s for s in self.sources}
        rows = {r['scope_id']: r for r in review['coverage']}
        answered = set(result['answer']['scope_ids'])
        report = []
        for scope in self.contract['scope']:
            if scope['id'] in answered:
                continue
            causes = []
            for blocker in result['blockers']:
                if scope['id'] not in blocker['scope_ids']:
                    continue
                source = by_id.get(blocker['source_id'], {})
                if blocker['reason'] == 'policy_review':
                    cause = 'policy_review_pending'
                elif not source:
                    cause = 'required_source_not_found'
                elif source.get('screening', 'include') != 'include':
                    cause = 'excluded_by_screening'
                elif source.get('validation_status') == 'valid':
                    cause = 'identity_unconfirmed'
                elif source.get('failure_code') in self.NO_ACCESS:
                    cause = 'no_access'
                else:
                    cause = 'acquisition_failed'
                causes.append({'cause': cause, 'source_id': blocker['source_id'], 'title': source.get('title'),
                               'failure_code': source.get('failure_code')})
            unverified = [c['id'] for c in withheld if scope['id'] in c['scope_ids'] and c['reason'] != 'scope_withheld_by_policy']
            if unverified:
                causes.append({'cause': 'claims_not_verified', 'claim_ids': unverified})
            if not causes:
                causes.append({'cause': 'insufficient_evidence_in_corpus',
                               'limitations': rows.get(scope['id'], {}).get('limitations', [])})
            report.append({'scope_id': scope['id'], 'question': scope['question'],
                           'causes': [{k: v for k, v in c.items() if v not in (None, '', [])} for c in causes]})
        return report

    def finalize(self, review):
        from .audit import SUPPORT_PROTOCOL, UNGROUNDED, check_review_version, load_answers, quote_grounding, review_claims
        check_review_version(review, self.state)
        answers = load_answers(self.folder, self.state, self.contract, self.sources)
        adjustments = []
        claims = review_claims(review, self.state, self.contract, self.sources, answers, adjustments)
        review_key = digest(review)
        self.store.append('decision', {'kind': 'qa_review_submitted', 'actor': review['reviewer'], 'review_hash': review_key})
        self.store.commit(self.state, {f'reviews/{review_key}.json': review})
        coverage = {r['scope_id']: r['status'] for r in review['coverage']}
        verdicts = {}
        batches = self.verification_batches(claims)
        self.checkpoint(next_action=f'Verificando {len(claims)} afirmaciones en {len(batches)} consultas a NotebookLM, '
                                    'de alrededor de un minuto cada una.')
        for batch in batches:
            verdicts.update(self.verify(batch))
        for claim in claims:
            verdict = verdicts[claim['id']]
            if verdict.get('reason') in UNGROUNDED and verdict.get('batch_size', 1) > 1:
                # Batch answers may lose native citations; ask about the claim alone.
                verdicts.update(self.verify([claim]))
        for claim in claims:
            verdict = verdicts[claim['id']]
            if verdict.get('reason') in UNGROUNDED and verdict.get('stated_verdict') == 'supported':
                allowed = {r['source_id'] for r in claim['references']}
                try:
                    texts = self.fulltexts(allowed)
                except Pause as exc:
                    if exc.reason in ('auth_required', 'quota_exhausted', 'notebooklm_missing'):
                        raise
                    texts = {}
                grounding = quote_grounding(verdict.get('rationale'), allowed, texts)
                if grounding:
                    verdict.update(verdict='supported', reason=None, grounding='quote_in_fulltext', quote=grounding)
        verified, withheld = [], []
        for claim in claims:
            verdict = verdicts[claim['id']]
            summary = {k: claim[k] for k in ('id', 'text', 'scope_ids', 'question_id', 'citation_numbers')}
            human = self.human_check(claim)
            if human and human['judgement'] == 'unsupported':
                withheld.append(dict(summary, reason='human_rejected', verification=verdict, human_check=human))
                for scope in claim['scope_ids']:
                    coverage[scope] = 'insufficient'
            elif verdict['verdict'] == 'supported' and not verdict.get('reason'):
                references = self.evidence(claim, verdict)
                extra = {'human_check': human} if human else {}
                missing = numbers_missing(claim['text'], [r['cited_text'] for r in references])
                if missing:
                    extra['warnings'] = [{'code': 'numbers_not_in_passages', 'values': missing}]
                verified.append(dict(claim, references=references, verification=verdict, **extra))
            else:
                withheld.append(dict(summary, reason=verdict.get('reason') or 'verdict_' + verdict['verdict'], verification=verdict))
                for scope in claim['scope_ids']:
                    coverage[scope] = 'insufficient'
        # Each claim stands on its own evidence. A failed claim marks its scopes as
        # incomplete but never withholds other verified claims; only source policies
        # (a missing hard_block source, a pending policy review) hold whole scopes.
        result = evaluate(self.contract, self.sources, coverage, 'pass')
        held_by_policy = {s for b in result['blockers'] if b['reason'] == 'policy_review' or b.get('policy') == 'hard_block'
                          for s in b['scope_ids']}
        delivered = [c for c in verified if not set(c['scope_ids']) & held_by_policy]
        withheld += [dict({k: c[k] for k in ('id', 'text', 'scope_ids', 'question_id', 'citation_numbers')},
                          reason='scope_withheld_by_policy', verification=c['verification']) for c in verified if c not in delivered]
        delivered_scope = {s for c in delivered for s in c['scope_ids']}
        for scope in set(coverage) - delivered_scope:
            coverage[scope] = 'insufficient'
        result = evaluate(self.contract, self.sources, coverage, 'pass')
        if delivered and result['answer']['status'] == 'unavailable':
            result['answer']['status'] = 'partial'
        partial = sorted(delivered_scope - set(result['answer']['scope_ids']))
        if partial:
            result['answer']['partial_scope_ids'] = partial
        skipped = self.skipped_questions(answers)
        report = {'schema_version': '2.1', 'contract_hash': self.state['contract_hash'], 'corpus_hash': self.state['corpus_hash'],
                  'review_hash': review_key, 'reviewer': review['reviewer'], **result, 'claims': delivered,
                  'withheld_claims': withheld, 'skipped_questions': skipped,
                  'gaps': self.gaps(result, review, withheld),
                  'changes': self.changes(delivered),
                  'corpus_exclusions': self.state.get('corpus_exclusions', []),
                  'review_adjustments': adjustments,
                  'coverage': [dict(r, status=coverage[r['scope_id']]) for r in review['coverage']],
                  'audit_kind': 'mechanical_traceability_and_notebooklm_support', 'support_protocol': SUPPORT_PROTOCOL,
                  'release_validation': False}
        return self.publish(report, delivered, result, review_key,
                            'Respuesta y límites guardados en answer.json.' if delivered else
                            'El corpus todavía no respalda una respuesta entregable. Revisa QA y fuentes.')

    def publish(self, report, delivered, result, review_key, next_action):
        self.state['choices'] = DELIVERY_CHOICES if delivered else []
        self.state.update(result, review_hash=review_key, phase='done' if delivered else 'audit',
                          execution={'status': 'completed' if delivered else 'waiting_user'}, next_action=next_action)
        self.store.commit(self.state, {'answer.json': report})
        from .deliver import report_markdown
        report_path = self.folder / 'report.md'
        temporary = self.folder / '.report.md.tmp'
        temporary.write_text(report_markdown(report, self.contract, self.state), encoding='utf-8')
        os.replace(temporary, report_path)
        self.checkpoint(report_sha256=sha256(report_path.read_bytes()).hexdigest())
        try:
            from .workspace import publish
            self.checkpoint(workspace=publish(self.folder.parent, self.folder, self.contract, self.state, report))
        except OSError:
            pass  # The project copy is a convenience; the run keeps the canonical report.
        return 0 if delivered and not (self.state.get('require_complete') and result['answer']['status'] != 'complete') else 2

    def skipped_questions(self, answers):
        skipped = []
        answered = {a['entry']['question_id'] for a in answers.values()}
        for question in self.contract['plan']['notebook_questions']:
            if question['id'] in answered:
                continue
            policies = self.blocking_policies(question)
            skipped.append({'question_id': question['id'], 'scope_ids': question['scope_ids'],
                            'reason': 'policy_review_pending' if policies and all(p['policy'] == 'contextual' and not p.get('effective_policy')
                                                                                for p in policies) else 'required_source_missing' if policies else 'not_asked',
                            'source_ids': [p['source_id'] for p in policies]})
        return skipped

    def review_from_direct(self, claim_ids=None, limit=10):
        """A verified-delivery review built from the direct answer, so nobody writes JSON by hand."""
        from .deliver import key_claims
        answer = read_json(self.folder / 'answer.json') if (self.folder / 'answer.json').exists() else {}
        if answer.get('delivery') != 'direct' or answer.get('corpus_hash') != self.state.get('corpus_hash') \
                or answer.get('contract_hash') != self.state.get('contract_hash'):
            raise ContractError('No hay una entrega directa vigente para verificar; usa ez continue primero.')
        by_id = {c['id']: c for c in answer['claims']}
        unknown = [i for i in claim_ids or [] if i not in by_id]
        if unknown:
            raise ContractError('Afirmaciones inexistentes en la entrega directa: ' + ', '.join(unknown))
        chosen = [by_id[i] for i in claim_ids] if claim_ids else key_claims(answer, limit)
        planned = {q['id']: q['scope_ids'] for q in self.contract['plan']['notebook_questions']}
        claims = [{'id': c['id'], 'text': c['text'], 'question_id': c['question_id'], 'citation_numbers': c['citation_numbers'],
                   'scope_ids': [x for x in c['scope_ids'] if x in planned[c['question_id']]] or planned[c['question_id']]}
                  for c in chosen]
        covered = {x for c in claims for x in c['scope_ids']}
        # Keep the direct delivery next to the run: the verified answer replaces answer.json and report.md.
        atomic_json(self.folder / 'direct' / 'answer.json', answer)
        shutil.copyfile(self.folder / 'report.md', self.folder / 'direct' / 'report.md')
        return {'schema_version': '2.0', 'contract_hash': self.state['contract_hash'], 'corpus_hash': self.state['corpus_hash'],
                'reviewer': {'kind': 'host_agent', 'name': 'EZ (selección de la entrega directa)'},
                'coverage': [{'scope_id': s['id'], 'status': 'sufficient' if s['id'] in covered else 'insufficient',
                              'rationale': 'Afirmaciones tomadas de la entrega directa para verificar.',
                              'limitations': [] if s['id'] in covered else ['No se seleccionaron afirmaciones de este alcance.']}
                             for s in self.contract['scope']],
                'claims': claims}

    def finalize_direct(self):
        """Direct delivery: NotebookLM's own cited sentences, with their native passages, no second query."""
        from .audit import DIRECT_PROTOCOL, direct_claims, load_answers, merge_repeated
        answers = load_answers(self.folder, self.state, self.contract, self.sources)
        claims, notes = [], []
        for question in self.contract['plan']['notebook_questions']:
            if question['id'] in answers:
                found, uncited = direct_claims(question, answers[question['id']]['response'], self.sources)
                claims += found
                notes += [{'question_id': question['id'], 'text': text} for text in uncited]
        claims = merge_repeated(claims)
        coverage = {s['id']: 'insufficient' for s in self.contract['scope']}
        delivered, withheld = [], []
        for claim in claims:
            summary = {k: claim[k] for k in ('id', 'text', 'scope_ids', 'question_id', 'citation_numbers')}
            human = self.human_check(claim)
            if human and human['judgement'] == 'unsupported':
                withheld.append(dict(summary, reason='human_rejected', human_check=human))
                continue
            references = self.bibliography([dict(r, role='qa') for r in claim['references']])
            extra = {'human_check': human} if human else {}
            missing = numbers_missing(claim['text'], [r['cited_text'] for r in references])
            if missing:
                extra['warnings'] = [{'code': 'numbers_not_in_passages', 'values': missing}]
            delivered.append(dict(claim, references=references, verification={'mode': 'direct', 'grounding': 'notebooklm_qa_citations'}, **extra))
            for scope in claim['scope_ids']:
                coverage[scope] = 'sufficient'
        result = evaluate(self.contract, self.sources, coverage, 'pass')
        held = {s for s, v in coverage.items() if v == 'sufficient'} - set(result['answer']['scope_ids'])
        withheld += [dict({k: c[k] for k in ('id', 'text', 'scope_ids', 'question_id', 'citation_numbers')}, reason='scope_withheld_by_policy')
                     for c in delivered if set(c['scope_ids']) & held]
        delivered = [c for c in delivered if not set(c['scope_ids']) & held]
        rows = [{'scope_id': s['id'], 'status': coverage[s['id']] if s['id'] in result['answer']['scope_ids'] else 'insufficient',
                 'rationale': 'Entrega directa de las citas de NotebookLM.', 'limitations': []} for s in self.contract['scope']]
        report = {'schema_version': '2.1', 'delivery': 'direct', 'contract_hash': self.state['contract_hash'],
                  'corpus_hash': self.state['corpus_hash'], 'review_hash': None, 'reviewer': {'kind': 'ez', 'name': 'EZ'},
                  **result, 'claims': delivered, 'withheld_claims': withheld,
                  'skipped_questions': self.skipped_questions(answers), 'gaps': self.gaps(result, {'coverage': rows}, withheld),
                  'uncited_statements': notes, 'changes': self.changes(delivered),
                  'corpus_exclusions': self.state.get('corpus_exclusions', []), 'review_adjustments': [], 'coverage': rows,
                  'audit_kind': 'notebooklm_native_citations', 'support_protocol': DIRECT_PROTOCOL, 'release_validation': False}
        return self.publish(report, delivered, result, None,
                            'Respuesta directa guardada en report.md: oraciones de NotebookLM con sus pasajes y páginas. '
                            'Resume lo central y ofrece: 1) verificar afirmaciones para redactar (ez continue --verify); '
                            '2) exportar la bibliografía a Zotero (ez export); 3) redactar con marcas [EZ:<id>] (ez draft); '
                            '4) otra pregunta del mismo proyecto, que reutiliza los PDFs ya cargados.' if delivered else
                            'NotebookLM no respondió con citas verificables. Revisa las preguntas QA o el corpus.')

    def execute(self, review=None, screening=None):
        try:
            if self.state.get('sources_hash') and digest(self.sources) != self.state['sources_hash']:
                raise Pause('NEEDS_TRACEABILITY_REPAIR', 'El manifiesto de fuentes cambió fuera del registro.', 4)
            self.checkpoint(execution={'status': 'running'}, integrity={'status': 'pending'}, legacy_signals=[],
                            blockers=[], choices=[],
                            next_action='La investigación está en curso; el estado muestra el último punto guardado.')
            self.discover()
            self.screen(screening)
            self.expand_citations()
            self.reuse_library()
            self.request_key_pdfs()
            self.acquire()
            self.request_pdfs()
            self.upload()
            return self.qa(review)
        except ReviewError as exc:
            # The host's review is unusable as submitted; the run's evidence is intact.
            self.checkpoint(execution={'status': 'waiting_user'}, legacy_signals=[exc.reason],
                            integrity={'status': 'pending'}, next_action=str(exc), answer={'status': 'unavailable'})
            return 2
        except ContractError as exc:
            self.checkpoint(execution={'status': 'blocked_integrity'}, legacy_signals=['NEEDS_TRACEABILITY_REPAIR'],
                            integrity={'status': 'fail'}, next_action=str(exc), answer={'status': 'unavailable'})
            return 4
        except (OSError, KeyError, ValueError) as exc:
            self.checkpoint(execution={'status': 'failed'}, legacy_signals=['NEEDS_TRACEABILITY_REPAIR'],
                            integrity={'status': 'unknown'}, next_action='No se pudo interpretar o guardar un artefacto: ' + str(exc), answer={'status': 'unavailable'})
            return 4
        except Pause as exc:
            self.checkpoint(choices=exc.choices,
                            execution={'status': 'blocked_integrity' if exc.code == 4 else 'waiting_service' if exc.code == 3 else 'waiting_user'},
                            integrity={'status': 'fail' if exc.code == 4 else 'pending'},
                            legacy_signals=[exc.reason], next_action=exc.message, answer={'status': 'unavailable'})
            return exc.code
        except KeyboardInterrupt:
            self.checkpoint(execution={'status': 'cancelled'}, next_action='La corrida quedó guardada; usa ez continue.')
            return 3
        finally:
            self.checkpoint()
