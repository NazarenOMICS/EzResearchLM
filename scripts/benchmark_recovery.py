"""Opt-in live acquisition pilot; never infer release acceptance from downloads."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time

from ez.contracts import now
from ez.acquisition import normalize_doi
from ez.process import run
from ez.state import atomic_json


def validate_corpus(corpus):
    cases = corpus.get('cases', [])
    if not cases or not isinstance(cases, list):
        raise ValueError('A frozen, nonempty case list is required')
    ids, works = set(), set()
    for case in cases:
        key = case['case_id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', key) or key in ids:
            raise ValueError('Unsafe or duplicate case ID')
        ids.add(key)
        if case['kind'] not in ('eligible', 'negative_control'):
            raise ValueError('Unknown case kind')
        if not case.get('eligibility_url') or not case.get('checked_at') or not case.get('accepted_version'):
            raise ValueError('Eligibility evidence and accepted version are required')
        record = case['record']
        allowed = {'title', 'doi', 'pmcid', 'pmid', 'pdf_url', 'pdf_urls'}
        if not set(record) <= allowed or not record.get('title'):
            raise ValueError('Only bibliographic inputs and public locations are allowed')
        if case['kind'] == 'negative_control' and not record.get('pdf_url'):
            raise ValueError('An isolated negative control requires its exact PDF URL')
        work = normalize_doi(record['doi']) if record.get('doi') else case['eligibility_url'].lower().strip()
        if case['kind'] == 'eligible':
            if work in works:
                raise ValueError('An eligible work may appear only once')
            works.add(work)
    return cases


def summarize(cases, results):
    rows = {r['case_id']: r for r in results}
    eligible = [c for c in cases if c['kind'] == 'eligible']
    controls = [c for c in cases if c['kind'] == 'negative_control']
    valid = lambda c: rows.get(c['case_id'], {}).get('validation_status') == 'valid'
    verified = lambda c: valid(c) and rows[c['case_id']].get('identity_status') == 'verified'
    return {
        'eligible_works': len(eligible),
        'attempted_eligible': sum(c['case_id'] in rows for c in eligible),
        'structurally_valid': sum(valid(c) for c in eligible),
        'automatically_identified': sum(verified(c) for c in eligible),
        'identity_review_pending': sum(valid(c) and not verified(c) for c in eligible),
        'independently_accepted': None,
        'accepted_recovery_rate': None,
        'negative_controls': len(controls),
        'control_false_acceptances': sum(verified(c) for c in controls),
        'control_correct_holds': sum(valid(c) and not verified(c) for c in controls),
        'control_inconclusive': sum(not valid(c) for c in controls),
        'release_ready': False,
    }


def execute(corpus, output, seconds=90, attempts=1):
    cases = validate_corpus(corpus)
    output = Path(output).resolve()
    # Refuse to overwrite any previous evidence, including an interrupted pilot.
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / 'corpus.json', corpus)
    (output / 'runner.py').write_bytes(Path(__file__).read_bytes())
    import ez
    package = Path(ez.__file__).parent
    report = {
        'started_at': now(), 'status': 'running', 'kind': 'acquisition_pilot',
        'corpus_sha256': sha256((output / 'corpus.json').read_bytes()).hexdigest(),
        'runner_sha256': sha256((output / 'runner.py').read_bytes()).hexdigest(),
        'candidate_version': ez.__version__, 'python': sys.version,
        'source_hashes': {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob('*.py'))},
        'per_source_seconds': seconds, 'attempts_per_url': attempts,
        'optional_credentials_present': {key: bool(os.environ.get(key)) for key in
                                         ('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL', 'EZRESEARCH_CORE_API_KEY')},
        'anna_enabled': False, 'authenticated_e2e': False,
        'results': [], 'summary': summarize(cases, []),
    }
    atomic_json(output / 'report.json', report)
    try:
        for case in cases:
            folder = output / case['case_id']
            folder.mkdir()
            record = dict(case['record'], source_id=case['case_id'])
            atomic_json(folder / 'record.json', record)
            started = time.monotonic()
            command = [sys.executable, '-I', '-m', 'ez.acquisition', '--record', str(folder / 'record.json'),
                       '--output', str(folder / 'result.json'), '--seconds', str(seconds),
                       '--attempts', str(attempts)]
            if case['kind'] == 'negative_control':
                # Evaluate the deliberately wrong document only. Falling back to
                # the correct original would make a successful rescue a false alarm.
                worker = ('import json,sys; from pathlib import Path; '
                          'from ez.acquisition import Retriever; from ez.state import atomic_json; '
                          'r=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig")); '
                          'v=Retriever(Path(sys.argv[2]).parent,r["source_id"],int(sys.argv[3]),int(sys.argv[4]))'
                          '.acquire(r,candidates=[(r["pdf_url"],"direct")]); atomic_json(sys.argv[2],v)')
                command = [sys.executable, '-I', '-c', worker, str(folder / 'record.json'), str(folder / 'result.json'), str(seconds), str(attempts)]
            result = run(command, timeout=seconds + 5)
            row = {'case_id': case['case_id'], 'elapsed_seconds': round(time.monotonic() - started, 3),
                   'exit_code': result.returncode, 'failure_code': result.reason or None,
                   'independent_review': 'pending'}
            if result.returncode == 0 and (folder / 'result.json').is_file():
                value = json.loads((folder / 'result.json').read_text(encoding='utf-8-sig'))
                for key in ('acquisition_status', 'validation_status', 'identity_status', 'content_sha256', 'pdf_source', 'failure_code'):
                    row[key] = value.get(key)
            if (folder / 'attempts.json').is_file():
                history = json.loads((folder / 'attempts.json').read_text(encoding='utf-8-sig'))
                row['failure_codes'] = sorted({x['failure_code'] for x in history if x.get('failure_code')})
                row['request_attempts'] = sum(bool(x.get('attempt_id')) for x in history)
            report['results'].append(row)
            report['summary'] = summarize(cases, report['results'])
            atomic_json(output / 'report.json', report)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        report['status'] = 'completed'
    except BaseException:
        report['status'] = 'interrupted'
        raise
    finally:
        report['ended_at'] = now()
        atomic_json(output / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--execute', action='store_true', help='Contact public sources and save private evidence.')
    parser.add_argument('--seconds', type=int, default=90)
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600 or not 1 <= args.attempts <= 3:
        parser.error('Use 1–600 seconds and 1–3 attempts per URL')
    corpus = json.loads(args.corpus.read_text(encoding='utf-8-sig'))
    cases = validate_corpus(corpus)
    if not args.execute:
        print(json.dumps({'status': 'validated_only', 'summary': summarize(cases, [])}))
        return 0
    if not args.output:
        parser.error('--output is required for execution')
    report = execute(corpus, args.output, args.seconds, args.attempts)
    print(json.dumps(report['summary']))
    return 1 if report['summary']['control_false_acceptances'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
