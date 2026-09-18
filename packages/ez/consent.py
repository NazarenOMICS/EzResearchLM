"""Source-scoped, expiring acquisition consent; never an access bypass grant."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import re
from uuid import uuid4

from .contracts import ContractError, now


def create_anna(source, url, run_id):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ('annas-archive.org', 'annas-archive.gl', 'annas-archive.gs')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r'/md5/[0-9a-fA-F]{32}', parsed.path)):
        raise ContractError('Indica la página HTTPS /md5/ de la fuente en Anna; no rutas de challenge ni URLs firmadas.')
    identifier = source.get('doi') or source.get('pmid') or source.get('title')
    if not identifier:
        raise ContractError('La fuente necesita un identificador o título verificado.')
    return {'schema_version': '2.0', 'consent_id': uuid4().hex, 'run_id': run_id, 'source_id': source['source_id'],
            'identifier': identifier, 'url': url, 'purpose': 'acquisition_only', 'actor': 'user',
            'granted_at': now(), 'expires_at': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            'access_bypass': False}


def validate_anna(receipt, source):
    if not isinstance(receipt, dict):
        raise ContractError('Falta consentimiento específico para Anna.')
    required = ('schema_version', 'consent_id', 'run_id', 'source_id', 'identifier', 'url', 'purpose', 'actor', 'granted_at', 'expires_at', 'access_bypass')
    if any(k not in receipt for k in required) or receipt['schema_version'] != '2.0' or receipt['purpose'] != 'acquisition_only' or receipt['actor'] != 'user' or receipt['access_bypass'] is not False:
        raise ContractError('El recibo de consentimiento no es válido.')
    if receipt['source_id'] != source['source_id'] or receipt['identifier'] != (source.get('doi') or source.get('pmid') or source.get('title')):
        raise ContractError('El consentimiento corresponde a otra fuente.')
    # Reuse URL validation without treating the generated receipt as authority.
    create_anna(source, receipt['url'], receipt['run_id'])
    expires = datetime.fromisoformat(receipt['expires_at'])
    if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
        raise ContractError('El consentimiento de Anna venció; requiere una nueva decisión.')
    return receipt
