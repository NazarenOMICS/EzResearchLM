"""The project's evidence memory: every delivered claim with its literal passages, searchable without NotebookLM.

Two views of the same records, both rebuilt from the runs' answer.json files (the
source of truth, bound to their corpus by hash):

    projects/<project>/notes/     Obsidian-compatible notes, one per source and one
                                  per research, for the person to browse
    ez recall "<question>"        keyword search over claims and passages

A recalled claim keeps its run: its marker is [EZ:<run_id>/<claim_id>], and
ez draft --check resolves it against that run. Recall never produces new text; it
returns what NotebookLM already said and the passages it cited.
"""
from collections import Counter
import math
from pathlib import Path
import re

from .state import Store, read_json

# Share of the question's topic words that the three best claims and their passages contain.
MIN_COVERAGE = 0.6
COVERAGE_HITS = 3


def marker(run_id, claim_id):
    return f'[EZ:{run_id}/{claim_id}]'


def valid_answer(folder):
    """answer.json of a delivered run, only when it still matches the run's contract and corpus."""
    from .audit import CURRENT_PROTOCOLS
    state = Store(folder).state()
    if not state or state.get('answer', {}).get('status') not in ('complete', 'partial') or not (folder / 'answer.json').exists():
        return None, state
    answer = read_json(folder / 'answer.json')
    if answer.get('contract_hash') != state.get('contract_hash') or answer.get('corpus_hash') != state.get('corpus_hash') \
            or answer.get('support_protocol') not in CURRENT_PROTOCOLS:
        return None, state
    return answer, state


def records(runs_root, project):
    """Every delivered claim of the project, newest research first."""
    from .context import history
    found = []
    for row in history(Path(runs_root), project, limit=500):
        folder = Path(row['path'])
        answer, state = valid_answer(folder)
        if not answer:
            continue
        for claim in answer.get('claims', []):
            found.append({'key': f'{state["run_id"]}/{claim["id"]}', 'run_id': state['run_id'], 'claim_id': claim['id'],
                          'marker': marker(state['run_id'], claim['id']), 'text': claim['text'], 'question': row['question'],
                          'delivery': answer.get('delivery', 'verified'), 'date': row['updated_at'][:10], 'path': str(folder),
                          'passages': [{'text': ref.get('cited_text') or '', 'page': ref.get('page'),
                                        'source': ref.get('source') or {'source_id': ref.get('source_id')}}
                                       for ref in claim.get('references', []) if ref.get('cited_text')]})
    return found


def words(text):
    from .acquisition import plain_words
    return [w for w in plain_words(text) if len(w) > 2]


def recall(runs_root, project, question, limit=8):
    """BM25 over each claim with its passages and source titles; coverage says how much of the question they touch."""
    from .workspace import topic_words
    rows = records(runs_root, project)
    documents = [words(' '.join([r['text']] + [p['text'] + ' ' + (p['source'].get('title') or '') for p in r['passages']]))
                 for r in rows]
    query = set(words(question))
    frequency = Counter(w for d in documents for w in set(d))
    average = sum(map(len, documents)) / len(documents) if documents else 0
    scored = []
    for row, document in zip(rows, documents):
        counts = Counter(document)
        score = 0.0
        for word in query & counts.keys():
            idf = math.log(1 + (len(documents) - frequency[word] + 0.5) / (frequency[word] + 0.5))
            score += idf * counts[word] * 2.2 / (counts[word] + 1.2 * (0.25 + 0.75 * len(document) / (average or 1)))
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: -item[0])
    hits, seen = [], set()
    for score, row in scored:
        if row['text'].casefold() in seen:
            continue
        seen.add(row['text'].casefold())
        hits.append(dict(row, score=round(score, 2)))
        if len(hits) == limit:
            break
    asked = topic_words(question)
    touched = set()
    for hit in hits[:COVERAGE_HITS]:
        touched |= topic_words(' '.join([hit['text']] + [p['text'] for p in hit['passages']]))
    coverage = round(len(asked & touched) / len(asked), 2) if asked else 0.0
    evidence = 'sufficient' if coverage >= MIN_COVERAGE else 'partial' if hits else 'insufficient'
    return {'claims_in_project': len(rows), 'hits': hits, 'coverage': coverage, 'evidence': evidence,
            'missing_words': sorted(asked - touched)}


def note_name(source):
    from .workspace import slug
    from .deliver import citation_key
    key = citation_key(source, set()) if source.get('authors') or source.get('year') else ''
    return (key + ' ' if key else '') + slug(source.get('title') or source.get('source_id') or 'fuente', 50)


def write(runs_root, project):
    """Rebuild the project's notes/ from its delivered researches; existing notes are regenerated, never merged."""
    from .workspace import project_dir, report_name
    folder = project_dir(runs_root, project) / 'notes'
    rows = records(runs_root, project)
    sources, researches = {}, {}
    for row in rows:
        researches.setdefault(row['run_id'], []).append(row)
        for passage in row['passages']:
            source = passage['source']
            entry = sources.setdefault(source.get('content_sha256') or source.get('source_id'), {'source': source, 'passages': {}})
            entry['passages'].setdefault(passage['text'], {'page': passage['page'], 'claims': []})['claims'].append(row)
    (folder / 'sources').mkdir(parents=True, exist_ok=True)
    (folder / 'researches').mkdir(parents=True, exist_ok=True)
    names, used = {}, set()
    for key, entry in sources.items():
        name, suffix = note_name(entry['source']), 1
        while name.casefold() in used:
            suffix += 1
            name = f'{note_name(entry["source"])} {suffix}'
        used.add(name.casefold())
        names[key] = name
    research_names = {}
    for run_id, claims in researches.items():
        contract = read_json(Path(claims[0]['path']) / 'research-contract.json')
        research_names[run_id] = report_name(contract, Store(Path(claims[0]['path'])).state())
    written = set()
    for key, entry in sources.items():
        source = entry['source']
        lines = ['---', 'title: "' + str(source.get('title') or '').replace('"', "'") + '"']
        lines += [f'{field}: {source[field]}' for field in ('year', 'doi', 'pmid', 'pmcid', 'content_sha256') if source.get(field)]
        lines += ['---', '', f'# {source.get("title") or source.get("source_id")}', '']
        if source.get('doi'):
            lines += [f'DOI: [{source["doi"]}](https://doi.org/{source["doi"]})', '']
        lines += ['## Pasajes citados por NotebookLM', '']
        for text, passage in entry['passages'].items():
            page = f' (p. {passage["page"]})' if passage['page'] else ''
            lines += ['> ' + re.sub(r'\s+', ' ', text).strip() + page, '']
            for row in passage['claims']:
                lines.append(f'- {row["text"]} {row["marker"]} en [[{research_names[row["run_id"]]}]]')
            lines.append('')
        target = folder / 'sources' / (names[key] + '.md')
        target.write_text('\n'.join(lines), encoding='utf-8')
        written.add(target)
    for run_id, claims in researches.items():
        lines = [f'# {claims[0]["question"]}', '', f'Fecha: {claims[0]["date"]} · Corrida: `{run_id}` · '
                 + ('entrega verificada' if claims[0]['delivery'] == 'verified' else 'entrega directa'), '']
        for row in claims:
            linked = sorted({names[p['source'].get('content_sha256') or p['source'].get('source_id')] for p in row['passages']})
            lines.append(f'- {row["text"]} {row["marker"]} ' + ' '.join(f'[[{n}]]' for n in linked))
        target = folder / 'researches' / (research_names[run_id] + '.md')
        target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        written.add(target)
    for stale in list((folder / 'sources').glob('*.md')) + list((folder / 'researches').glob('*.md')):
        if stale not in written:
            stale.unlink()
    (folder / 'README.md').write_text(
        '# Notas del proyecto\n\nEZ reescribe esta carpeta en cada entrega a partir de las investigaciones verificables '
        '(`runs/ez-…`). Cada nota de `sources/` reúne los pasajes que NotebookLM citó de esa fuente; cada nota de '
        '`researches/` lista las afirmaciones de una investigación. Se puede abrir como vault de Obsidian. No la edites: '
        'los cambios se pierden en la próxima entrega.\n', encoding='utf-8')
    return {'notes': str(folder), 'sources': len(sources), 'researches': len(researches)}
