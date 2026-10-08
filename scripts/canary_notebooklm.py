"""Maintainer canary: does the installed NotebookLM CLI still answer in the shapes EZ relies on?

Run before each release with a notebook that already holds at least one processed source:

    python scripts/canary_notebooklm.py --notebook <notebook-id> [--report canary.json]

It only reads the notebook and asks two short questions (two chat queries of the
account's quota). It prints counts and pass/fail per check, never source text.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'packages'), str(ROOT / 'packages' / 'paper_search')]

from ez.audit import batch_verdicts, verification_prompt  # noqa: E402
from ez.notebook_format import valid_response  # noqa: E402
from ez.paths import executable  # noqa: E402
from ez.process import run  # noqa: E402


def call(command, args, seconds=120):
    result = run([command, *args, '--json'], timeout=seconds)
    if result.returncode:
        return None, (result.reason or 'exit_' + str(result.returncode))
    try:
        value = json.loads(result.stdout)
    except ValueError:
        return None, 'not_json'
    return (value, None) if valid_response(value, args) else (None, 'unexpected_shape')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--notebook', required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    command = executable('notebooklm')
    checks = []

    def check(name, ok, detail, critical=True):
        checks.append({'check': name, 'ok': bool(ok), 'critical': critical, 'detail': detail})

    if not command:
        check('cli_installed', False, 'notebooklm no está instalado')
    else:
        listing, error = call(command, ['list'])
        check('list_notebooks', listing is not None, error or f'{len(listing["notebooks"])} notebooks')
        sources, error = call(command, ['source', 'list', '--notebook', args.notebook])
        ready = [s for s in (sources or {}).get('sources', []) if str(s.get('status', '')).lower() in ('ready', 'completed', 'available')]
        check('list_sources', sources is not None and ready, error or f'{len(ready)} fuentes listas')
        if ready:
            source_id = ready[0]['id']
            text, error = call(command, ['source', 'fulltext', source_id, '--notebook', args.notebook], 60)
            check('source_fulltext', text is not None, error or f'{len(text["content"])} caracteres')
            answer, error = call(command, ['ask', '--notebook', args.notebook, '--new', '--source', source_id,
                                           '¿Cuál es el objetivo principal de esta fuente? Cita la fuente.'], 180)
            refs = [r for r in (answer or {}).get('references', []) if r.get('cited_text')]
            check('qa_native_citations', answer is not None and refs, error or f'{len(refs)} citas con pasaje')
            claim = [{'id': 'c1', 'text': 'Esta fuente describe un trabajo de investigación.',
                      'references': [{'source_id': source_id, 'citation_number': 1, 'cited_text': ''}]}]
            verdict, error = call(command, ['ask', '--notebook', args.notebook, '--new', '--source', source_id,
                                            verification_prompt(claim)], 180)
            # EZ asks every question in a fresh conversation; a follow-up here means --new did not apply.
            check('fresh_conversation', verdict is not None and verdict.get('is_follow_up') is False,
                  error or f'is_follow_up={verdict.get("is_follow_up")!r}')
            parsed = batch_verdicts(verdict, [{'notebook_source_id': source_id, 'notebook_status': 'ready',
                                               'validation_status': 'valid', 'identity_status': 'verified'}], claim)['c1'] if verdict else {}
            check('verdict_format', verdict is not None and parsed.get('stated_verdict'), error or f'dictamen {parsed.get("stated_verdict")}')
            # Not critical: EZ falls back to a literal quote check, but the trend matters.
            check('verdict_native_citations', parsed.get('grounding') == 'native_citations',
                  parsed.get('reason') or 'citas nativas presentes', critical=False)
    failed = [c for c in checks if c['critical'] and not c['ok']]
    report = {'at': datetime.now(timezone.utc).isoformat(), 'kind': 'notebooklm_canary', 'passed': not failed, 'checks': checks}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
