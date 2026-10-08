"""Open-access status of candidate works, asked to OpenAlex in batches before screening."""
import argparse
import os
from urllib.parse import quote

from .state import atomic_json, read_json

BATCH = 50


def lookup(dois, session=None):
    """{doi: {'is_oa': bool, 'oa_status': str}} for the DOIs OpenAlex knows; the rest stay unknown."""
    import requests
    from .acquisition import normalize_doi
    session = session or requests.Session()
    email = os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL') or os.environ.get('UNPAYWALL_EMAIL')
    result = {}
    wanted = sorted({normalize_doi(d) for d in dois if normalize_doi(d)})
    for start in range(0, len(wanted), BATCH):
        batch = wanted[start:start + BATCH]
        url = ('https://api.openalex.org/works?per-page=50&select=doi,open_access&filter=doi:'
               + '|'.join(quote(d, safe='/') for d in batch) + (f'&mailto={quote(email)}' if email else ''))
        try:
            response = session.get(url, timeout=(10, 30))
            rows = response.json().get('results', []) if response.status_code == 200 else []
        except Exception:
            continue
        for row in rows if isinstance(rows, list) else []:
            doi = normalize_doi((row or {}).get('doi'))
            access = (row or {}).get('open_access') or {}
            if doi in batch and isinstance(access, dict):
                result[doi] = {'is_oa': bool(access.get('is_oa')), 'oa_status': str(access.get('oa_status') or 'unknown')}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    atomic_json(args.output, {'schema_version': '1.0', 'status': lookup(read_json(args.input))})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
