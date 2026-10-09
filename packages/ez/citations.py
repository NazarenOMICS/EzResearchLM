"""Citation expansion: works that the included sources cite, and works that cite them.

A keyword search misses relevant papers that use other words; the reference lists and
citing works of the papers already judged relevant recover many of them. Europe PMC
answers for PubMed-indexed seeds (references and citations by PMID); OpenAlex answers
for seeds with a DOI. Every returned record names the seeds it is linked to, so the
engine can rank candidates by how many relevant papers point to them.
"""
import argparse
import os
from urllib.parse import quote

from .state import atomic_json, read_json

EUROPEPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/MED/{pmid}/{kind}?format=json&pageSize=100'
OPENALEX = 'https://api.openalex.org/'
FIELDS = 'id,doi,title,publication_year,ids,authorships,primary_location,abstract_inverted_index'
BATCH = 50


def text_of(inverted):
    """OpenAlex abstracts come as {word: [positions]}."""
    if not isinstance(inverted, dict):
        return ''
    words = sorted((position, word) for word, positions in inverted.items() for position in positions or [])
    return ' '.join(word for _, word in words)


def from_europepmc(row, relation, seed):
    if not isinstance(row, dict) or not row.get('title'):
        return None
    pmid = str(row.get('id') or '') if row.get('source') == 'MED' else ''
    return {'title': str(row['title']).strip().rstrip('.'), 'authors': row.get('authorString') or '', 'year': str(row.get('pubYear') or ''),
            'journal': row.get('journalAbbreviation') or '', 'doi': row.get('doi') or '', 'pmid': pmid, 'pmcid': '',
            'abstract': '', 'source': 'europepmc_citations', 'sources': ['europepmc_citations'], 'queries': [],
            'links': [{'seed': seed, 'relation': relation}]}


def from_openalex(row, relation, seed):
    if not isinstance(row, dict) or not row.get('title'):
        return None
    ids = row.get('ids') or {}
    pmid = str(ids.get('pmid') or '').rstrip('/').rsplit('/', 1)[-1]
    pmcid = str(ids.get('pmcid') or '').rstrip('/').rsplit('/', 1)[-1]
    doi = str(row.get('doi') or '').replace('https://doi.org/', '')
    authors = '; '.join(((a or {}).get('author') or {}).get('display_name') or '' for a in row.get('authorships') or [])
    venue = (((row.get('primary_location') or {}).get('source')) or {}).get('display_name') or ''
    return {'title': str(row['title']).strip(), 'authors': authors, 'year': str(row.get('publication_year') or ''),
            'journal': venue, 'doi': doi, 'pmid': pmid, 'pmcid': pmcid, 'abstract': text_of(row.get('abstract_inverted_index')),
            'source': 'openalex_citations', 'sources': ['openalex_citations'], 'queries': [],
            'links': [{'seed': seed, 'relation': relation}]}


def get_json(session, url):
    try:
        response = session.get(url, timeout=(10, 30))
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None


def expand(seeds, session=None):
    """Records linked to the seeds and the number of requests that failed."""
    import requests
    session = session or requests.Session()
    email = os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL') or os.environ.get('UNPAYWALL_EMAIL')
    mailto = f'&mailto={quote(email)}' if email else ''
    records, failures = [], 0
    for seed in seeds:
        if seed.get('pmid'):
            for kind, relation, key in (('references', 'cited_by_seed', ('referenceList', 'reference')),
                                        ('citations', 'cites_seed', ('citationList', 'citation'))):
                value = get_json(session, EUROPEPMC.format(pmid=quote(str(seed['pmid'])), kind=kind))
                if value is None:
                    failures += 1
                    continue
                rows = (value.get(key[0]) or {}).get(key[1]) or []
                records += [r for r in (from_europepmc(row, relation, seed['source_id']) for row in rows) if r]
        if seed.get('doi'):
            work = get_json(session, OPENALEX + 'works/doi:' + quote(seed['doi'], safe='/') + '?select=id,referenced_works' + mailto)
            if work is None:
                failures += 1
                continue
            referenced = [w.rsplit('/', 1)[-1] for w in work.get('referenced_works') or []]
            for start in range(0, len(referenced), BATCH):
                value = get_json(session, OPENALEX + 'works?per-page=50&select=' + FIELDS + '&filter=openalex_id:'
                                 + '|'.join(referenced[start:start + BATCH]) + mailto)
                if value is None:
                    failures += 1
                    continue
                records += [r for r in (from_openalex(row, 'cited_by_seed', seed['source_id']) for row in value.get('results') or []) if r]
            work_id = str(work.get('id') or '').rsplit('/', 1)[-1]
            if work_id:
                value = get_json(session, OPENALEX + 'works?per-page=100&sort=cited_by_count:desc&select=' + FIELDS
                                 + '&filter=cites:' + work_id + mailto)
                if value is None:
                    failures += 1
                else:
                    records += [r for r in (from_openalex(row, 'cites_seed', seed['source_id']) for row in value.get('results') or []) if r]
    return records, failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    records, failures = expand(read_json(args.input))
    atomic_json(args.output, {'schema_version': '1.0', 'records': records, 'failures': failures})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
