"""Deliverables derived deterministically from answer.json: the evidence report and draft checks."""
import re

from .presenter import GAP_LABELS, REASON_LABELS

STATUS = {'complete': 'Respuesta completa para el alcance acordado.',
          'partial': 'Respuesta parcial: algunas subpreguntas quedaron sin respaldo verificado.',
          'unavailable': 'Sin respuesta verificada todavía.'}
ROLE = {'qa': 'Pasaje citado por NotebookLM', 'verification': 'Pasaje citado en la verificación',
        'verification_quote': 'Cita textual de la verificación, encontrada en la fuente'}
METHOD = {'verified': '**Cómo se verificó:** cada afirmación proviene de una respuesta de NotebookLM sobre los PDFs del corpus y '
                      'pasó una segunda consulta de respaldo a NotebookLM. Es una verificación automática: no reemplaza la lectura '
                      'del pasaje en el PDF original.',
          'direct': '**Cómo se obtuvo:** cada afirmación es una oración de NotebookLM respondiendo sobre los PDFs del corpus, '
                    'con los pasajes que NotebookLM citó para ella. No pasó una segunda verificación por afirmación: lee el '
                    'pasaje antes de usarla en tu texto.'}
PER_SCOPE = 10
MARKER = re.compile(r'\[EZ:\s*([A-Za-z0-9_,\s-]+)\]')


def bibliography(answer):
    """Sources in order of first citation; the key is the local source when known, else the remote ID."""
    order = {}
    for claim in answer.get('claims', []):
        for ref in claim.get('references', []):
            source = ref.get('source') or {}
            key = source.get('source_id') or ref['source_id']
            if key not in order:
                order[key] = (len(order) + 1, source, ref['source_id'])
    return order


def key_claims(answer, limit=8):
    """The claims backed by the most distinct sources, in delivery order on ties."""
    def sources(claim):
        return len({(r.get('source') or {}).get('source_id') or r['source_id'] for r in claim['references']})
    claims = answer.get('claims', [])
    ranked = sorted(range(len(claims)), key=lambda i: (-sources(claims[i]), i))[:limit]
    return [claims[i] for i in sorted(ranked)]


def entry(source, remote_id):
    if not source:
        return f'Fuente de NotebookLM {remote_id} (sin metadatos locales).'
    parts = [source.get('title') or source['source_id']]
    if source.get('authors'):
        authors = source['authors'] if isinstance(source['authors'], str) else ', '.join(source['authors'])
        parts.insert(0, authors)
    if source.get('year'):
        parts.append(f'({source["year"]})')
    if source.get('journal'):
        parts.append(source['journal'])
    ids = [f'{label} {source[key]}' for key, label in (('doi', 'DOI'), ('pmid', 'PMID'), ('pmcid', 'PMCID')) if source.get(key)]
    text = '. '.join(p.rstrip('.') for p in parts) + '.'
    if ids:
        text += ' ' + ' · '.join(ids) + '.'
    if source.get('pdf_path'):
        text += f' Archivo: `{source["pdf_path"]}` (SHA-256 `{source.get("content_sha256", "")}`).'
    if source.get('pdf_source'):
        text += f' Origen: {source["pdf_source"]}.'
    return text


def report_markdown(answer, contract, state):
    sources = bibliography(answer)
    number = {key: n for key, (n, _, _) in sources.items()}
    lines = ['# Informe de evidencia', '',
             f'**Pregunta:** {contract["question"]["original"]}', '',
             f'**Estado:** {STATUS.get(answer["answer"]["status"], answer["answer"]["status"])}', '',
             METHOD.get(answer.get('delivery'), METHOD['verified']), '']
    if len(answer.get('claims', [])) > 8:
        lines += ['## Lo central', '', f'{len(answer["claims"])} afirmaciones en total; estas son las respaldadas por más fuentes.', '']
        for claim in key_claims(answer):
            cited = sorted({number[(r.get('source') or {}).get('source_id') or r['source_id']] for r in claim['references']})
            lines.append(f'- {claim["text"]} [{", ".join(map(str, cited))}] `[EZ:{claim["id"]}]`')
        lines.append('')
    lines += ['## Respuesta por subpregunta', '']
    gaps = {g['scope_id']: g for g in answer.get('gaps', [])}
    annex = []
    for scope in contract['scope']:
        lines += [f'### {scope["question"]}', '']
        claims = [c for c in answer.get('claims', []) if scope['id'] in c['scope_ids']]
        if len(claims) > PER_SCOPE:
            # Long answers show the best-supported claims here and keep the rest, complete, in an annex.
            shown = {c['id'] for c in key_claims({'claims': claims}, PER_SCOPE)}
            annex += [(scope, c) for c in claims if c['id'] not in shown]
            claims = [c for c in claims if c['id'] in shown]
        for claim in claims:
            cited = sorted({number[(r.get('source') or {}).get('source_id') or r['source_id']] for r in claim['references']})
            lines.append(f'- {claim["text"]} [{", ".join(map(str, cited))}] `[EZ:{claim["id"]}]`')
            for ref in claim['references']:
                key = (ref.get('source') or {}).get('source_id') or ref['source_id']
                warning = ' (no se encontró literal en el texto indexado; revísalo en el PDF)' if ref.get('found_in_fulltext') is False else ''
                lines.append(f'  - {ROLE.get(ref.get("role", "qa"), "Pasaje")} [{number[key]}]{warning}: «{ref["cited_text"]}»')
            for item in claim.get('warnings', []):
                if item['code'] == 'numbers_not_in_passages':
                    lines.append(f'  - Aviso: los números {", ".join(item["values"])} no aparecen en los pasajes citados; verifícalos en el PDF.')
            if claim.get('human_check'):
                judgement = {'supported': 'respaldada', 'partial': 'respaldo parcial'}.get(claim['human_check']['judgement'],
                                                                                           claim['human_check']['judgement'])
                lines.append(f'  - Revisión humana: {judgement}.')
        hidden = sum(1 for item in annex if item[0] is scope)
        if hidden:
            lines.append(f'- Otras {hidden} afirmaciones de esta subpregunta están en el anexo.')
        if not claims:
            lines.append('- Sin afirmaciones verificadas.')
        if scope['id'] in gaps:
            for cause in gaps[scope['id']]['causes']:
                detail = f' ({cause["title"]})' if cause.get('title') else ''
                lines.append(f'- Pendiente: {GAP_LABELS.get(cause["cause"], cause["cause"])}{detail}.')
        lines.append('')
    if answer.get('changes'):
        changes = answer['changes']
        lines += ['## Cambios respecto de la versión anterior', '',
                  f'Versión anterior: `{changes.get("previous_run")}`. Afirmaciones nuevas: {len(changes["new"])}; '
                  f'se mantienen: {len(changes["kept"])}; ya no se sostienen: {len(changes["dropped"])}.', '']
        lines += [f'- Ya no se sostiene: {c["text"]}' for c in changes['dropped']]
        lines += [f'- Fuente nueva: {title}' for title in changes.get('new_sources', [])]
        lines.append('')
    if answer.get('withheld_claims'):
        lines += ['## Qué no se pudo afirmar', '']
        lines += [f'- {c["text"]} — {REASON_LABELS.get(c["reason"], c["reason"])}.' for c in answer['withheld_claims']]
        lines.append('')
    if answer.get('uncited_statements'):
        lines += ['## Lo que NotebookLM dijo sin citar', '',
                  'No es evidencia: NotebookLM no citó pasajes para estas oraciones. Suelen señalar límites del corpus.', '']
        lines += [f'- {n["question_id"]}: {n["text"]}' for n in answer['uncited_statements']]
        lines.append('')
    if answer.get('review_adjustments'):
        lines += ['## Correcciones automáticas de la revisión', '']
        for item in answer['review_adjustments']:
            target = item.get('claim_id') or item.get('scope_id')
            lines.append(f'- {target}: `{item["field"]}` pasó de {item["from"]} a {item["to"]}.')
        lines.append('')
    if answer.get('skipped_questions'):
        lines += ['## Preguntas que no se consultaron', '']
        lines += [f'- {q["question_id"]}: {REASON_LABELS.get(q["reason"], q["reason"])}.' for q in answer['skipped_questions']]
        lines.append('')
    lines += ['## Fuentes citadas', '']
    lines += [f'{n}. {entry(source, remote)}' for _, (n, source, remote) in sorted(sources.items(), key=lambda item: item[1][0])]
    if not sources:
        lines.append('Ninguna.')
    lines.append('')
    if answer.get('corpus_exclusions') or state.get('discovery_failures'):
        lines += ['## Fuentes que no entraron al corpus', '']
        for source in answer.get('corpus_exclusions', []):
            detail = f' ({source["detail"]})' if source.get('detail') else ''
            routes = ', '.join(f'{r["provider"]} ({r["failure_code"]})' for r in source.get('routes', []))
            routes = f' Rutas probadas: {routes}.' if routes else ''
            lines.append(f'- {source.get("title") or source["source_id"]}: {REASON_LABELS.get(source["reason"], source["reason"])}{detail}.{routes}')
        for failure in state.get('discovery_failures', []):
            lines.append(f'- Búsqueda {failure.get("query_id")} en {failure.get("provider")}: no se completó ({failure.get("reason")}).')
        lines.append('')
    if annex:
        lines += ['## Anexo: resto de las afirmaciones', '']
        for scope, claim in annex:
            cited = sorted({number[(r.get('source') or {}).get('source_id') or r['source_id']] for r in claim['references']})
            lines.append(f'- ({scope["id"]}) {claim["text"]} [{", ".join(map(str, cited))}] `[EZ:{claim["id"]}]`')
            for ref in claim['references']:
                key = (ref.get('source') or {}).get('source_id') or ref['source_id']
                lines.append(f'  - {ROLE.get(ref.get("role", "qa"), "Pasaje")} [{number[key]}]: «{ref["cited_text"]}»')
        lines.append('')
    lines += ['## Trazabilidad', '',
              f'- Corrida: `{state["run_id"]}`',
              f'- Contrato: `{answer["contract_hash"]}`',
              f'- Corpus: `{answer["corpus_hash"]}`',
              f'- Revisión: `{answer.get("review_hash") or "sin revisión (entrega directa)"}`',
              f'- Protocolo de verificación: `{answer.get("support_protocol")}`',
              '- Para redactar con estas afirmaciones, cita cada una con su marcador `[EZ:<id>]` y comprueba el borrador con '
              '`ez draft <corrida> --check <archivo>`.', '']
    return '\n'.join(lines)


def check_draft(answer, text):
    """Every marker must name a delivered claim; sentences without a marker are listed for review."""
    delivered = {c['id'] for c in answer.get('claims', [])}
    withheld = {c['id'] for c in answer.get('withheld_claims', [])}
    used, unknown, refused = set(), set(), set()
    for group in MARKER.findall(text):
        for claim_id in (x.strip() for x in group.split(',') if x.strip()):
            used.add(claim_id)
            if claim_id in withheld:
                refused.add(claim_id)
            elif claim_id not in delivered:
                unknown.add(claim_id)
    unmarked = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(('#', '>', '|', '```')):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+', line.strip()):
            plain = MARKER.sub('', sentence).strip()
            if len(plain) >= 40 and not MARKER.search(sentence):
                unmarked.append(plain)
    return {'kind': 'draft_check', 'valid': not unknown and not refused, 'claims_used': sorted(used & delivered),
            'unknown_markers': sorted(unknown), 'withheld_markers': sorted(refused),
            'unmarked_sentences': unmarked[:50], 'unmarked_count': len(unmarked),
            'next_action': ('El borrador solo cita afirmaciones verificadas. Revisa las oraciones sin marcador: si afirman '
                            'hechos de la literatura, deben apoyarse en una afirmación verificada o eliminarse.')
            if not unknown and not refused else
            'El borrador cita afirmaciones inexistentes o retenidas. Corrígelo antes de entregarlo.'}
