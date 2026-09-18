"""Versioned contracts for plans supplied by the host agent."""
from datetime import datetime, timezone
from hashlib import sha256
from importlib.resources import files
import json
from uuid import uuid4

from jsonschema import Draft202012Validator


class ContractError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate(value, kind='research-contract'):
    schema = json.loads(files('ez').joinpath('schemas', kind + '.json').read_text(encoding='utf-8'))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ContractError('; '.join(f'{list(e.path)}: {e.message}' for e in errors))
    if kind == 'source-manifest':
        ids = [s['source_id'] for s in value]
        if len(ids) != len(set(ids)):
            raise ContractError('Duplicate source identifiers')
    if kind == 'research-contract':
        scope = [x['id'] for x in value['scope']]
        if len(set(scope)) != len(scope):
            raise ContractError('Duplicate scope identifiers')
        for field in ('queries', 'notebook_questions'):
            rows = value['plan'][field]
            ids = [x['id'] for x in rows]
            if len(ids) != len(set(ids)):
                raise ContractError(f'Duplicate {field} identifiers')
            for row in rows:
                if not set(row['scope_ids']).issubset(scope):
                    raise ContractError(f'Unknown scope in {field}')
        policy_ids = [p['source_id'] for p in value['source_policies']]
        if len(policy_ids) != len(set(policy_ids)):
            raise ContractError('Duplicate source policy identifiers')
        for policy in value['source_policies']:
            if not set(policy['scope_ids']).issubset(scope):
                raise ContractError('Unknown scope in source policy')
        if value['acquisition']['anna_enabled'] and not value['acquisition'].get('consent_id'):
            raise ContractError('Anna requires an explicit consent receipt')
    return value


def draft(question, context):
    return {
        'schema_version': '2.0', 'contract_id': str(uuid4()), 'revision': 1,
        'created_at': now(), 'question': {'original': question, 'language': context.get('language', 'es')},
        'context': context, 'scope': [{'id': 'sq1', 'question': question, 'central': True}],
        'plan': {'status': 'needs_host_plan', 'queries': [], 'notebook_questions': [], 'stop_rule': ''},
        'source_policies': [], 'acquisition': {'anna_enabled': False, 'consent_id': None},
        'budgets': {'run_seconds': 3600, 'source_seconds': 600, 'attempts_per_route': 3},
        'operator': {'name': 'EZ', 'backend': 'host_agent', 'model': 'unknown'},
    }


def require_ready(contract):
    validate(contract)
    plan = contract['plan']
    needs_queries = plan.get('discovery_mode', 'search') != 'reuse_only'
    if plan['status'] != 'ready' or (needs_queries and not plan['queries']) or not plan['notebook_questions'] or not plan['stop_rule'].strip():
        raise ContractError('El agente anfitrión debe completar queries, preguntas NotebookLM y criterio de parada.')
    scopes = {s['id'] for s in contract['scope']}
    if {s for q in plan['notebook_questions'] for s in q['scope_ids']} != scopes:
        raise ContractError('Todas las subpreguntas deben tener QA planificada.')
