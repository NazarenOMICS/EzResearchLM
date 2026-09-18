"""Resolve structural citations only through unique, literal NotebookLM text matches."""
from copy import deepcopy
import re
import unicodedata

from .audit import citation_markers
from .contracts import digest


def normalize(text):
    return ' '.join(unicodedata.normalize('NFKC', text).split())


def quoted_candidates(response):
    missing = {r['citation_number']: r['source_id'] for r in response.get('references', [])
               if not r.get('cited_text') and type(r.get('citation_number')) is int and r.get('source_id')}
    result = {}
    # Require a literal quotation immediately followed by the native citation.
    pattern = r'["“]([^"“”]{40,2000})["”]\*{0,2}\s*(\[[0-9][0-9,\s\-\u2013\u2014]*\])'
    for match in re.finditer(pattern, response['answer']):
        for number in citation_markers(match[2]):
            if number in missing:
                result.setdefault(number, []).append(match[1])
    return result


def resolve_quotes(response, fulltexts):
    result = deepcopy(response)
    candidates = quoted_candidates(response)
    for ref in result['references']:
        number, source_id = ref.get('citation_number'), ref.get('source_id')
        source = fulltexts.get(source_id)
        if number not in candidates or not source or source.get('source_id') != source_id:
            continue
        content = normalize(source['content'])
        matches = {normalize(q) for q in candidates[number] if content.count(normalize(q)) == 1}
        if len(matches) != 1:
            continue
        quote = matches.pop()
        ref.update(cited_text=quote, original_cited_text=ref.get('cited_text'),
                   resolution={'method': 'unique_quote_in_notebooklm_fulltext',
                               'source_snapshot_hash': digest(source), 'normalized_offset': content.index(quote),
                               'normalization': 'NFKC_and_whitespace_only'})
    return result
