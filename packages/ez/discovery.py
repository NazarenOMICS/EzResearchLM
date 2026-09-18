"""Supervised adapter for legacy searchers that otherwise swallow service errors."""
import argparse
import logging

from .contracts import now
from .state import atomic_json, read_json


class Diagnostics(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.errors = 0
        self.warnings = 0

    def emit(self, record):
        if record.name.startswith('paper_search_mcp.academic_platforms'):
            if record.levelno >= logging.ERROR:
                self.errors += 1
            else:
                self.warnings += 1


def search(query):
    import search_topic
    diagnostic = Diagnostics()
    logger = logging.getLogger('paper_search_mcp.academic_platforms')
    logger.addHandler(diagnostic)
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        candidates = search_topic.search_single(query['provider'], query['text'], query.get('max_results', 5))
    except Exception:
        diagnostic.errors += 1
        candidates = []
    finally:
        logger.removeHandler(diagnostic)
        logger.setLevel(old_level)
    return {'schema_version': '2.0', 'at': now(), 'provider': query['provider'], 'candidates': candidates,
            'status': 'failed' if diagnostic.errors else ('partial' if diagnostic.warnings else 'complete'),
            'failure_code': 'provider_error' if diagnostic.errors else None,
            'errors': diagnostic.errors, 'warnings': diagnostic.warnings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = search(read_json(args.query))
    atomic_json(args.output, result)
    return 3 if result['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
