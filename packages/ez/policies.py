"""Evidence gates are deterministic and scoped, never inferred from retrieval score."""
POLICIES = {'hard_block', 'soft_block', 'contextual', 'historical', 'optional'}


def legacy_gate(explicit=None, *, continuing=False, persisted=None):
    if explicit is not None:
        return bool(explicit)
    if continuing:
        return True if persisted is None else bool(persisted)
    return False


def evaluate(contract, sources, coverage=None, integrity='unknown'):
    coverage = coverage or {}
    available = {x['source_id'] for x in sources if x.get('notebook_status') == 'ready' and x.get('validation_status') == 'valid' and x.get('identity_status') == 'verified'}
    blockers = []
    withheld = set()
    signals = set()
    for item in contract['source_policies']:
        policy = item['policy']
        if policy not in POLICIES:
            raise ValueError('Unknown evidence policy')
        if policy == 'contextual':
            policy = item.get('effective_policy')
            if policy not in POLICIES - {'contextual'}:
                withheld.update(item['scope_ids'])
                blockers.append({'reason': 'policy_review', 'scope_ids': item['scope_ids'], 'source_id': item['source_id']})
                signals.add('NEEDS_SOURCE_REVIEW')
                continue
        if item['source_id'] not in available:
            if policy in ('hard_block', 'soft_block'):
                signals.add('NEEDS_SOURCE_RESCUE')
                blockers.append({'reason': 'missing_source', 'policy': policy, 'scope_ids': item['scope_ids'], 'source_id': item['source_id']})
            if policy == 'hard_block':
                withheld.update(item['scope_ids'])
    scopes = {x['id'] for x in contract['scope']}
    supported = {s for s in scopes if coverage.get(s) == 'sufficient'} - withheld
    if integrity not in ('pass', 'warn'):
        supported.clear()
        signals.add('NEEDS_TRACEABILITY_REPAIR')
    if not available:
        supported.clear()
        signals.add('NEEDS_CORPUS')
    elif supported != scopes:
        signals.add('NEEDS_MORE_QA')
    status = 'complete' if supported == scopes else ('partial' if supported else 'unavailable')
    return {'answer': {'status': status, 'scope_ids': sorted(supported)}, 'integrity': {'status': integrity},
            'blockers': blockers, 'legacy_signals': sorted(signals)}
