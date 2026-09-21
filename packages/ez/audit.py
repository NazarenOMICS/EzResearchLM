"""Mechanical citation checks and host review validation; never a scientific oracle."""
from hashlib import sha256
import json
import re

from .contracts import ContractError, digest, validate
from .paths import contained
from .state import read_json


SUPPORT_PROTOCOL = 'ez-verdict-v3-passages'


def citation_markers(answer):
    """NotebookLM emits single, comma-separated and ranged citation markers."""
    markers = set()
    for group in re.findall(r'\[([0-9][0-9,\s\-\u2013\u2014]*)\]', answer):
        for item in group.split(','):
            match = re.fullmatch(r'\s*(\d+)\s*(?:[-\u2013\u2014]\s*(\d+)\s*)?', item)
            if not match:
                raise ContractError('NotebookLM devolvió un marcador de cita no reconocido.')
            start = int(match[1]); end = int(match[2] or match[1])
            if start < 1 or end < start or end - start > 1000:
                raise ContractError('NotebookLM devolvió un rango de citas inválido.')
            markers.update(range(start, end + 1))
    return markers


def references(response, sources, required_numbers=None):
    """Return only citations with a known, ready, verified source and a passage."""
    available = {s['notebook_source_id']: s for s in sources if s.get('notebook_status') == 'ready'
                 and s.get('validation_status') == 'valid' and s.get('identity_status') == 'verified'}
    answer = response.get('answer')
    if not isinstance(answer, str) or not answer.strip():
        raise ContractError('NotebookLM no devolvió una respuesta auditable.')
    result = {}
    seen = set()
    for ref in response.get('references', []):
        number = ref.get('citation_number')
        if type(number) is not int or number < 1 or number in seen:
            raise ContractError('NotebookLM devolvió números de cita ambiguos.')
        seen.add(number)
        if ref.get('source_id') not in available:
            raise ContractError('Una cita apunta fuera del corpus verificado.')
        if not isinstance(ref.get('cited_text'), str) or not ref['cited_text'].strip():
            # Structural references may be legitimate but require another QA with
            # a passage before this adapter can verify them mechanically.
            continue
        result[number] = ref
    markers = citation_markers(answer)
    required = markers if required_numbers is None else set(required_numbers)
    if not required or not required.issubset(markers) or not required.issubset(result):
        raise ContractError('Faltan marcadores o pasajes verificables para las citas de NotebookLM.')
    return {n: result[n] for n in required}


def load_answers(folder, state, contract, sources):
    manifest = read_json(folder / 'qa/manifest.json')
    if digest(manifest) != state.get('qa_manifest_hash') or manifest.get('corpus_hash') != state.get('corpus_hash'):
        raise ContractError('El manifiesto QA no corresponde al corpus confirmado.')
    planned = {q['id']: q for q in contract['plan']['notebook_questions']}
    answers = {}
    for entry in manifest['answers']:
        qid = entry['question_id']
        if qid not in planned or digest(planned[qid]) != entry['question_hash'] or qid in answers:
            raise ContractError('Una respuesta QA no coincide con la pregunta acordada.')
        path = contained(folder, entry['path'])
        if sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ContractError('Una respuesta de NotebookLM cambió después de registrarse.')
        response = read_json(path)
        answers[qid] = {'entry': entry, 'response': response}
    return answers


def review_claims(review, state, contract, sources, answers):
    validate(review, 'qa-review')
    if review['contract_hash'] != state['contract_hash'] or review['corpus_hash'] != state['corpus_hash']:
        raise ContractError('La revisión pertenece a otra versión del contrato o corpus.')
    scope = {s['id'] for s in contract['scope']}
    rows = review['coverage']
    if {r['scope_id'] for r in rows} != scope or len(rows) != len(scope):
        raise ContractError('La revisión debe cubrir cada subpregunta exactamente una vez.')
    ids = set()
    enriched = []
    for claim in review['claims']:
        if claim['id'] in ids:
            raise ContractError('Identificadores de afirmaciones duplicados.')
        ids.add(claim['id'])
        answer = answers.get(claim['question_id'])
        if not answer or not set(claim['scope_ids']).issubset(answer['entry']['scope_ids']):
            raise ContractError('La afirmación no tiene QA para su alcance.')
        # A draft may contain unsupported material that the host withholds.
        # Every citation actually proposed for delivery still needs its passage.
        refs = references(answer['response'], sources, claim['citation_numbers'])
        if not set(claim['citation_numbers']).issubset(refs):
            raise ContractError('La afirmación contiene una cita ausente en su QA.')
        enriched.append(dict(claim, references=[refs[n] for n in claim['citation_numbers']]))
    for row in rows:
        if row['status'] == 'sufficient' and not any(row['scope_id'] in c['scope_ids'] for c in enriched):
            raise ContractError('No se puede declarar suficiente un alcance sin afirmaciones citadas.')
        if row['status'] != 'sufficient' and not row['limitations']:
            raise ContractError('Declara qué falta en cada alcance insuficiente o desconocido.')
    return enriched


def support_verdict(response, sources, allowed_ids, proposed_references=None):
    """Structured verdict plus native citation passages; malformed answers fail closed."""
    refs = references(response, sources)
    if not {r['source_id'] for r in refs.values()}.issubset(allowed_ids):
        raise ContractError('La verificación usó fuentes fuera de las citas propuestas.')
    if proposed_references is not None:
        # Native citation numbering belongs to each answer independently. Match
        # source and literal passage instead; another paragraph is not evidence
        # for the citation that will actually accompany the delivered claim.
        for ref in refs.values():
            passage = ' '.join(ref['cited_text'].split())
            if not any(ref['source_id'] == proposed['source_id'] and
                       passage in ' '.join(proposed['cited_text'].split())
                       for proposed in proposed_references):
                raise ContractError('La verificación citó un pasaje distinto de los propuestos; requiere nueva revisión QA.')
    text = response['answer'].strip()
    # NotebookLM may omit native citation objects inside JSON/code blocks.
    # This minimal plain-text protocol keeps its actual citation annotations.
    native = re.fullmatch(r'EZ_VERDICT:\s*(supported|partial|unsupported)\s*\nEZ_RATIONALE:\s*(.+)', text, re.DOTALL)
    if native:
        if not citation_markers(native[2]):
            raise ContractError('La justificación del dictamen no contiene citas.')
        return {'verdict': native[1], 'rationale': native[2].strip()}
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise ContractError('La verificación de respaldo no devolvió JSON reconocido; requiere nueva QA.') from exc
    if not isinstance(value, dict) or value.get('verdict') not in ('supported', 'partial', 'unsupported') or not isinstance(value.get('rationale'), str) or not value['rationale'].strip():
        raise ContractError('La verificación no contiene un dictamen de respaldo.')
    if not citation_markers(value['rationale']):
        raise ContractError('La justificación del dictamen no contiene citas.')
    # Ignore unknown envelope fields; they are neither rationale nor authority.
    return {'verdict': value['verdict'], 'rationale': value['rationale'].strip()}
