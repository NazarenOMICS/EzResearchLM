"""The project's evidence memory: every delivered claim with its literal passages, searchable without NotebookLM.

Two views of the same records, both rebuilt from the runs' answer.json files (the
source of truth, bound to their corpus by hash):

    projects/<project>/notes/     Obsidian-compatible notes, one per source and one
                                  per research, for the person to browse
    ez recall "<question>"        keyword search over claims and passages

A recalled claim keeps its run: its marker is [EZ:<run_id>/<claim_id>], and
ez draft --check resolves it against that run. Recall never produces new text; it
returns what NotebookLM already said and the passages it cited.

Recall also searches the full text of the project's verified PDFs, page by page, and
returns literal passages marked [EZ:pdf-<sha12>-p<page>]. They answer what the PDFs
say word for word (methods, conditions, reference lists) without a NotebookLM query;
they are not syntheses, so each is used only for what it says literally.
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
    from .presenter import claim_citation
    found = []
    for row in history(Path(runs_root), project, limit=500):
        folder = Path(row['path'])
        answer, state = valid_answer(folder)
        if not answer:
            continue
        for claim in answer.get('claims', []):
            found.append({'key': f'{state["run_id"]}/{claim["id"]}', 'run_id': state['run_id'], 'claim_id': claim['id'],
                          'marker': marker(state['run_id'], claim['id']), 'citation': claim_citation(claim),
                          'text': claim['text'], 'question': row['question'],
                          'delivery': answer.get('delivery', 'verified'), 'date': row['updated_at'][:10], 'path': str(folder),
                          'passages': [{'text': ref.get('cited_text') or '', 'page': ref.get('page'),
                                        'source': ref.get('source') or {'source_id': ref.get('source_id')}}
                                       for ref in claim.get('references', []) if ref.get('cited_text')]})
    return found


def words(text):
    from .acquisition import plain_words
    return [w for w in plain_words(text) if len(w) > 2]


PDF_WINDOW, PDF_STEP = 70, 45  # words per passage and step between passages (they overlap)
REFERENCES_HEADING = re.compile(r'^\s*(references|literature cited|bibliography|referencias|bibliografía)\s*$', re.I | re.M)


def pdf_marker(sha256, page):
    return f'[EZ:pdf-{sha256[:12]}-p{page}]'


def page_cache(runs_root, source):
    """Text of each page of a verified PDF, extracted once and kept next to the runs (keyed by its hash)."""
    import json
    from .pdftext import page_texts
    from .state import atomic_json
    path = Path(runs_root).parent / 'cache' / 'pages' / (source['content_sha256'] + '.json')
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding='utf-8'))['pages']
        except (OSError, ValueError, KeyError):
            pass
    try:
        pages = page_texts(source['pdf_path'])
    except Exception:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, {'sha256': source['content_sha256'], 'pages': pages})
    return pages


def pdf_chunks(runs_root, project, sources=None):
    """Overlapping passages of every verified PDF of the project, with page and whether they sit in the references."""
    from .library import project_sources
    from .presenter import short_citation
    chunks = []
    for source in project_sources(runs_root, project) if sources is None else sources:
        pages = page_cache(runs_root, source)
        in_references = False
        about = {'title': source.get('title'), 'citation': short_citation(source), 'doi': source.get('doi'),
                 'source_id': source['source_id']}
        for number, text in enumerate(pages, 1):
            text = text or ''
            heading = None if in_references else REFERENCES_HEADING.search(text)
            # A page that holds the references heading is split there: the body above, the reference list below.
            parts = [(text[:heading.start()], False), (text[heading.start():], True)] if heading else [(text, in_references)]
            for part, references in parts:
                tokens = part.split()
                for start in range(0, max(1, len(tokens) - PDF_WINDOW // 3), PDF_STEP):
                    piece = ' '.join(tokens[start:start + PDF_WINDOW])
                    if piece:
                        chunks.append({'marker': pdf_marker(source['content_sha256'], number), 'page': number, 'text': piece,
                                       'in_references': references, 'source': about})
            if heading:
                in_references = True
    return chunks


def bm25(query, documents):
    """Okapi BM25 score of each document (a list of words) for the query words."""
    frequency = Counter(w for d in documents for w in set(d))
    average = sum(map(len, documents)) / len(documents) if documents else 0
    scores = []
    for document in documents:
        counts = Counter(document)
        score = 0.0
        for word in query & counts.keys():
            idf = math.log(1 + (len(documents) - frequency[word] + 0.5) / (frequency[word] + 0.5))
            score += idf * counts[word] * 2.2 / (counts[word] + 1.2 * (0.25 + 0.75 * len(document) / (average or 1)))
        scores.append(score)
    return scores


NAMED_WORK = re.compile(r"\b([A-ZÁÉÍÓÚÑÄÖÜ][\w'’-]{2,})(?:\s+(?:et\s+al\.?|y\s+col(?:aboradores|\.)?|and\s+colleagues))?,?"
                        r"\s+\(?((?:19|20)\d{2})\b")
DOI_IN_TEXT = re.compile(r'\b10\.\d{4,9}/[^\s"\'<>,;]*[^\s"\'<>,;.)]')


def named_works(question):
    """Works the question names by author and year («Smith 2019», «García et al., 2021») or by DOI, each with a test
    that tells whether a source is that work."""
    from .acquisition import normalize_doi, plain_words
    from .workspace import STOPWORDS

    def author_words(source):
        authors = source.get('authors') or ''
        return set(plain_words(' '.join(authors) if isinstance(authors, list) else authors))

    works = [(doi, lambda s, d=normalize_doi(doi): bool(s.get('doi')) and normalize_doi(s['doi']) == d)
             for doi in DOI_IN_TEXT.findall(question)]
    for name, year in NAMED_WORK.findall(question):
        surname = plain_words(name)
        if ' '.join(surname) in STOPWORDS:
            continue
        works.append((f'{name} {year}', lambda s, n=set(surname), y=year:
                      str(s.get('year') or '')[:4] == y and n <= author_words(s)))
    return works


def recall(runs_root, project, question, limit=8, pdf_limit=6):
    """BM25 over each claim with its passages and source titles; coverage says how much of the question they touch."""
    from .library import project_sources
    from .workspace import topic_words
    rows = records(runs_root, project)
    documents = [words(' '.join([r['text']] + [p['text'] + ' ' + (p['source'].get('title') or '') for p in r['passages']]))
                 for r in rows]
    query = set(words(question))
    scored = [(score, row) for score, row in zip(bm25(query, documents), rows) if score > 0]
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
    sources = project_sources(runs_root, project)
    # A named work counts as the other words did, so «Smith 2019» looked answered by claims from other works (2026-10-11).
    known = sources + [p['source'] for r in rows for p in r['passages']]
    absent_works = [label for label, is_work in named_works(question) if not any(is_work(s) for s in known)]
    if absent_works and evidence == 'sufficient':
        evidence = 'partial'
    chunks = pdf_chunks(runs_root, project, sources)
    chunk_words = [words(c['text']) for c in chunks]
    ranked = sorted(((s, c) for s, c in zip(bm25(query, chunk_words), chunks) if s > 0), key=lambda item: -item[0])
    passages, pages_seen = [], set()
    for score, chunk in ranked:
        if chunk['marker'] in pages_seen:  # one passage per page: the best one
            continue
        pages_seen.add(chunk['marker'])
        passages.append(dict(chunk, score=round(score, 2)))
        if len(passages) == pdf_limit:
            break
    # A reference list only shows that a work is cited, so it does not count towards answering.
    body = [p for p in passages if not p['in_references']][:COVERAGE_HITS]
    pdf_touched = set().union(*(topic_words(p['text']) for p in body)) if body else set()
    pdf_coverage = round(len(asked & pdf_touched) / len(asked), 2) if asked else 0.0
    # Questions in one language over PDFs in another match little more than the organism's name (9 of 9 follow-ups of a
    # live run, 2026-10-11); a word that is not a proper name and appears in the PDFs is what tells them apart.
    vocabulary = set().union(*map(set, chunk_words)) if chunks else set()
    common = topic_words(' '.join(t for t in re.findall(r"[\w'’-]+", question) if not t[:1].isupper())) & vocabulary
    mismatch = bool(chunks) and len(common) < 3 and len(asked - vocabulary) >= max(1, len(common))
    return {'claims_in_project': len(rows), 'hits': hits, 'coverage': coverage, 'evidence': evidence,
            'missing_words': sorted(asked - touched - pdf_touched), 'pdf_passages': passages, 'pdf_coverage': pdf_coverage,
            'pdfs_searched': len({c['source']['source_id'] for c in chunks}), 'named_works_absent': absent_works,
            'query_language_mismatch': mismatch}


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
