"""Recognize the pinned NotebookLM CLI envelopes before acting on their data."""


def valid_listing(value, key):
    if not isinstance(value, dict) or value.get('error') or not isinstance(value.get(key), list):
        return False
    rows = value[key]
    if any(not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip()
           or ('title' in row and not isinstance(row['title'], str)) for row in rows):
        return False
    return len({row['id'] for row in rows}) == len(rows)


def valid_response(value, args):
    if not isinstance(value, dict) or value.get('error'):
        return False
    if args[0] == 'list':
        return valid_listing(value, 'notebooks')
    if args[:2] == ['source', 'list']:
        return valid_listing(value, 'sources') and all(isinstance(row.get('status'), str) for row in value['sources'])
    if args[:2] == ['source', 'fulltext']:
        return (value.get('source_id') == args[2] and isinstance(value.get('content'), str)
                and bool(value['content'].strip()))
    if args[0] == 'create' or args[:2] == ['source', 'add']:
        entity = value.get('notebook' if args[0] == 'create' else 'source', value)
        return isinstance(entity, dict) and isinstance(entity.get('id'), str) and bool(entity['id'].strip())
    if args[0] == 'ask':
        return (isinstance(value.get('answer'), str) and bool(value['answer'].strip())
                and isinstance(value.get('references'), list)
                and all(isinstance(ref, dict) for ref in value['references']))
    return False
