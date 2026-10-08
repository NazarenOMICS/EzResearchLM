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


class Pause(Exception):
    def __init__(self, reason, message, code=2):
        self.reason, self.message, self.code = reason, message, code


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

    def notebook(self, args, seconds=60):
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
            if not self.state.get('reused_from') or not self.sources:
                raise ContractError('El plan requiere evidencia reutilizada, pero no hay una copia verificada de origen.')
            self.checkpoint(discovery_complete=True)
            return
        self.checkpoint('discover')
        import search_topic
        records = []
        failures = []
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
                argv = [sys.executable, '-m', 'ez.discovery', '--query', str(queries_file), '--output', str(candidate_file)]
                result = self.call(argv, 180)
                if result.returncode or not candidate_file.exists():
                    result = self.call(argv, 180)  # one retry: providers often fail transiently (e.g. HTTP 429)
                if result.returncode or not candidate_file.exists():
                    # One provider down must not stop the research; record it and continue with the others.
                    failures.append({'query_id': query.get('id'), 'provider': query.get('provider'),
                                     'reason': result.reason or 'provider_error'})
                    continue
                atomic_json(receipt_file, {'query_hash': digest(query), 'candidates_hash': digest(read_json(candidate_file)), 'at': now()})
            records.extend(read_json(candidate_file)['candidates'])
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
        request = {'schema_version': '2.0', 'sources_hash': self.state['sources_hash'], 'max_sources': self.max_sources(),
                   'already_included': sum(s.get('screening', 'include') == 'include' for s in self.sources),
                   'candidates': [{k: s.get(k) for k in ('source_id', 'title', 'authors', 'year', 'journal', 'doi', 'pmid',
                                                         'pmcid', 'sources', 'queries') if s.get(k)}
                                  | ({'abstract': s['abstract'][:800]} if s.get('abstract') else {}) for s in pending],
                   'decisions': []}
        atomic_json(self.folder / 'screening-request.json', request)
        raise Pause('NEEDS_SCREENING', f'Hay {len(pending)} candidatos por decidir. El agente anfitrión debe completar una copia de '
                    'screening-request.json con include, exclude o uncertain y una razón por candidato; luego usar '
                    'ez continue --screening.', 2)

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
        self.store.append('decision', {'kind': 'screening', 'actor': 'host_agent', 'screening_hash': digest(screening),
                                       'decisions': len(decided)})
        self.save_sources()

    def acquire(self):
        self.checkpoint('acquire')
        for index, source in enumerate(self.sources):
            if source.get('validation_status') == 'valid' or source.get('acquisition_status') == 'manual_needed' \
                    or source.get('screening', 'include') != 'include':
                continue
            dest = contained(self.folder, 'acquisition/' + source['source_id'])
            dest.mkdir(parents=True, exist_ok=True)
            record_path, result_path = dest / 'record.json', dest / 'result.json'
            atomic_json(record_path, source)
            result = self.call([sys.executable, '-m', 'ez.acquisition', '--record', str(record_path), '--output', str(result_path),
                                '--seconds', str(self.contract['budgets']['source_seconds']), '--attempts', str(self.contract['budgets']['attempts_per_route'])], self.contract['budgets']['source_seconds'])
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
        title = 'EZ ' + self.state['run_id']
        if not self.state.get('notebook_id'):
            if self.state.get('pending_operation') == 'create_notebook':
                notebooks = self.notebook(['list']).get('notebooks', [])
                matches = [n for n in notebooks if n.get('title') == title]
                if len(matches) != 1:
                    raise Pause('remote_reconciliation', 'La creación anterior no tiene resultado inequívoco. Revisa el notebook antes de repetir.')
                self.checkpoint(notebook_id=matches[0]['id'], pending_operation=None)
            else:
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
                self.checkpoint(notebook_id=notebook_id, pending_operation=None)
        notebook_id = self.state['notebook_id']
        remote = self.notebook(['source', 'list', '--notebook', notebook_id]).get('sources', [])
        known_ids = {s.get('notebook_source_id') for s in self.sources if s.get('notebook_source_id')}
        known_titles = {s['source_id'] + '-' + s['content_sha256'][:12] + '.pdf' for s in self.sources if s.get('content_sha256')}
        if any(s.get('id') not in known_ids and s.get('title') not in known_titles for s in remote):
            raise Pause('remote_corpus_drift', 'El notebook contiene fuentes sin reconciliar. Revisa el corpus antes de añadir documentos.', 4)
        for source in verified:
            # Verify local bytes again before sending them outside the machine.
            path = Path(source['pdf_path'])
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != source['content_sha256']:
                raise Pause('NEEDS_TRACEABILITY_REPAIR', 'Un PDF cambió después de validarlo.', 4)
            upload_title = source['source_id'] + '-' + source['content_sha256'][:12] + '.pdf'
            matches = [s for s in remote if s.get('id') == source.get('notebook_source_id') or s.get('title') == upload_title]
            if len(matches) > 1:
                raise Pause('remote_reconciliation', 'NotebookLM tiene fuentes duplicadas; revisa antes de continuar.')
            if matches:
                source['notebook_source_id'] = matches[0]['id']
            elif source.get('upload_pending') or source.get('notebook_source_id'):
                raise Pause('remote_reconciliation', 'Una subida previa no aparece en NotebookLM. Revisa antes de repetirla.')
            else:
                # File uploads can ignore --title. Give the actual upload file
                # its deterministic reconciliation name while preserving the PDF.
                staged = contained(self.folder, 'upload/' + upload_title)
                staged.parent.mkdir(exist_ok=True)
                if not staged.exists():
                    shutil.copyfile(path, staged)
                if sha256(staged.read_bytes()).hexdigest() != source['content_sha256']:
                    raise Pause('NEEDS_TRACEABILITY_REPAIR', 'La copia preparada para subida cambió.', 4)
                source['upload_pending'] = True
                self.save_sources()
                try:
                    data = self.notebook(['source', 'add', '--notebook', notebook_id, '--type', 'file', '--mime-type', 'application/pdf', '--title', upload_title, str(staged)], 180)
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
        self.checkpoint('readiness')
        remote = self.notebook(['source', 'list', '--notebook', notebook_id]).get('sources', [])
        expected = {s['notebook_source_id'] for s in verified}
        if {s.get('id') for s in remote} != expected:
            raise Pause('remote_corpus_drift', 'El corpus remoto incluye fuentes ausentes o no registradas. Revisa su composición.', 4)
        ready = {s['id'] for s in remote if str(s.get('status', '')).lower() in ('ready', 'completed', 'available')}
        for source in verified:
            source['notebook_status'] = 'ready' if source['notebook_source_id'] in ready else 'processing'
        self.save_sources()
        if ready != expected:
            raise Pause('waiting_on_processing', 'NotebookLM todavía procesa fuentes. Ejecuta ez continue más adelante.', 3)
        self.checkpoint(corpus_hash=digest(sorted((s['source_id'], s['content_sha256'], s['notebook_source_id']) for s in verified)),
                        corpus_exclusions=self.exclusions())

    def exclusions(self):
        """Sources that stayed outside the corpus, with the reason the user can act on."""
        result = []
        for source in self.sources:
            screening = source.get('screening', 'include')
            if screening == 'include' and source.get('validation_status') == 'valid' and source.get('identity_status') == 'verified':
                continue
            if screening != 'include':
                reason = {'exclude': 'excluded_by_screening', 'uncertain': 'screening_uncertain'}.get(screening, 'not_screened')
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
                                              ('detail', source.get('screening_reason') if screening != 'include' else None)) if v})
        return result

    def blocking_policies(self, question):
        return [p for p in self.contract['source_policies'] if set(p['scope_ids']) & set(question['scope_ids']) and
                (p.get('effective_policy') or p['policy']) in ('hard_block', 'contextual') and
                not any(s['source_id'] == p['source_id'] and s.get('notebook_status') == 'ready' for s in self.sources)]

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
            result.append(dict(ref, source={k: v for k, v in fields.items() if v not in (None, '', [])}))
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
            args = ['ask', '--notebook', self.state['notebook_id']]
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
            args = ['ask', '--notebook', self.state['notebook_id']]
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
        review = read_json(self.folder / 'reviews' / (self.state['review_hash'] + '.json'))
        return self.finalize(review)

    NO_ACCESS = {'paywall', 'access_denied', 'auth_required', 'captcha_or_challenge'}

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
        claims = review_claims(review, self.state, self.contract, self.sources, answers)
        review_key = digest(review)
        self.store.append('decision', {'kind': 'qa_review_submitted', 'actor': review['reviewer'], 'review_hash': review_key})
        self.store.commit(self.state, {f'reviews/{review_key}.json': review})
        coverage = {r['scope_id']: r['status'] for r in review['coverage']}
        verdicts = {}
        for batch in self.verification_batches(claims):
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
        result = evaluate(self.contract, self.sources, coverage, 'pass')
        allowed = set(result['answer']['scope_ids'])
        delivered = [c for c in verified if set(c['scope_ids']).issubset(allowed)]
        held_by_policy = {s for b in result['blockers'] if b['reason'] == 'policy_review' or b.get('policy') == 'hard_block'
                          for s in b['scope_ids']}
        withheld += [dict({k: c[k] for k in ('id', 'text', 'scope_ids', 'question_id', 'citation_numbers')},
                          reason='scope_withheld_by_policy' if set(c['scope_ids']) & held_by_policy else 'scope_not_sufficient',
                          verification=c['verification']) for c in verified if c not in delivered]
        # Never label a scope answered if all of its claims were withheld jointly
        # with a blocked scope. Claims may be split in a subsequent host review.
        delivered_scope = {s for c in delivered for s in c['scope_ids']}
        for scope in allowed - delivered_scope:
            coverage[scope] = 'insufficient'
        result = evaluate(self.contract, self.sources, coverage, 'pass')
        answered = {a['entry']['question_id'] for a in answers.values()}
        skipped = []
        for question in self.contract['plan']['notebook_questions']:
            if question['id'] in answered:
                continue
            policies = self.blocking_policies(question)
            skipped.append({'question_id': question['id'], 'scope_ids': question['scope_ids'],
                            'reason': 'policy_review_pending' if policies and all(p['policy'] == 'contextual' and not p.get('effective_policy')
                                                                                for p in policies) else 'required_source_missing' if policies else 'not_asked',
                            'source_ids': [p['source_id'] for p in policies]})
        report = {'schema_version': '2.1', 'contract_hash': self.state['contract_hash'], 'corpus_hash': self.state['corpus_hash'],
                  'review_hash': review_key, 'reviewer': review['reviewer'], **result, 'claims': delivered,
                  'withheld_claims': withheld, 'skipped_questions': skipped,
                  'gaps': self.gaps(result, review, withheld),
                  'changes': self.changes(delivered),
                  'corpus_exclusions': self.state.get('corpus_exclusions', []),
                  'coverage': [dict(r, status=coverage[r['scope_id']]) for r in review['coverage']],
                  'audit_kind': 'mechanical_traceability_and_notebooklm_support', 'support_protocol': SUPPORT_PROTOCOL,
                  'release_validation': False}
        self.state.update(result, review_hash=review_key, phase='done' if delivered else 'audit',
                          execution={'status': 'completed' if delivered else 'waiting_user'},
                          next_action='Respuesta y límites guardados en answer.json.' if delivered else 'El corpus todavía no respalda una respuesta entregable. Revisa QA y fuentes.')
        self.store.commit(self.state, {'answer.json': report})
        from .deliver import report_markdown
        report_path = self.folder / 'report.md'
        temporary = self.folder / '.report.md.tmp'
        temporary.write_text(report_markdown(report, self.contract, self.state), encoding='utf-8')
        os.replace(temporary, report_path)
        self.checkpoint(report_sha256=sha256(report_path.read_bytes()).hexdigest())
        return 0 if delivered and not (self.state.get('require_complete') and result['answer']['status'] != 'complete') else 2

    def execute(self, review=None, screening=None):
        try:
            if self.state.get('sources_hash') and digest(self.sources) != self.state['sources_hash']:
                raise Pause('NEEDS_TRACEABILITY_REPAIR', 'El manifiesto de fuentes cambió fuera del registro.', 4)
            self.checkpoint(execution={'status': 'running'}, integrity={'status': 'pending'}, legacy_signals=[],
                            blockers=[],
                            next_action='La investigación está en curso; el estado muestra el último punto guardado.')
            self.discover()
            self.screen(screening)
            self.acquire()
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
            self.checkpoint(execution={'status': 'blocked_integrity' if exc.code == 4 else 'waiting_service' if exc.code == 3 else 'waiting_user'},
                            integrity={'status': 'fail' if exc.code == 4 else 'pending'},
                            legacy_signals=[exc.reason], next_action=exc.message, answer={'status': 'unavailable'})
            return exc.code
        except KeyboardInterrupt:
            self.checkpoint(execution={'status': 'cancelled'}, next_action='La corrida quedó guardada; usa ez continue.')
            return 3
        finally:
            self.checkpoint()
