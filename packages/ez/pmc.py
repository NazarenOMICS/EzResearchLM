"""Current PMC public Cloud Service; no retired OA service or website scraping."""
import re
from urllib.parse import parse_qs, quote, urlsplit
from xml.etree import ElementTree

from .contracts import digest, now

BASE = 'https://pmc-oa-opendata.s3.amazonaws.com'


def locations(retriever, record):
    pmcid = str(record.get('pmcid') or '').upper()
    if not re.fullmatch(r'PMC\d+', pmcid):
        return []

    def fail(reason):
        retriever.record({'provider': 'pmc_cloud', 'result': 'failed', 'failure_code': reason, 'at': now()})

    data, _ = retriever.request(BASE + '/?list-type=2&prefix=' + pmcid + '.&delimiter=/&max-keys=100', 'pmc_cloud')
    if not data:
        return []
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        fail('invalid_metadata'); return []
    if root.findtext('{*}IsTruncated') == 'true':
        fail('pmc_version_list_truncated'); return []
    prefixes = sorted({p.text for p in root.findall('{*}CommonPrefixes/{*}Prefix')
                       if p.text and re.fullmatch(re.escape(pmcid) + r'\.[1-9]\d*/', p.text)},
                      key=lambda p: int(p.split('.')[1][:-1]))
    if len(prefixes) > 8:
        fail('pmc_version_limit'); return []
    requested = record.get('pmc_version')
    selected = [p for p in prefixes if p == f'{pmcid}.{requested}/'] if requested is not None else prefixes
    if not selected:
        fail('pmc_version_unavailable' if requested is not None else 'pmc_not_in_public_dataset'); return []
    candidates = []
    for prefix in selected:
        metadata_url = BASE + '/' + prefix + prefix[:-1] + '.json'
        value = retriever.metadata(metadata_url, 'pmc_cloud')
        if value.get('pmcid') != pmcid or str(value.get('version')) != prefix.split('.')[1][:-1]:
            fail('pmc_identity_mismatch'); continue
        doi = str(record.get('doi') or '').strip().lower()
        doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi)
        if doi and str(value.get('doi') or '').strip().lower() != doi:
            fail('pmc_identity_mismatch'); continue
        raw = value.get('pdf_url')
        if not isinstance(raw, str) or not raw:
            fail('pmc_pdf_unavailable'); continue
        try:
            url = urlsplit(raw)
        except ValueError:
            fail('invalid_metadata'); continue
        checksum = parse_qs(url.query).get('md5', [''])[0].lower()
        permitted_host = ((url.scheme == 's3' and url.netloc == 'pmc-oa-opendata') or
                          (url.scheme == 'https' and url.netloc == 'pmc-oa-opendata.s3.amazonaws.com'))
        if (not permitted_host or not url.path.startswith('/' + prefix) or '..' in url.path.split('/')
                or not url.path.lower().endswith('.pdf') or not re.fullmatch(r'[a-f0-9]{32}', checksum)):
            fail('invalid_metadata'); continue
        pdf_url = BASE + '/' + quote(url.path.lstrip('/'), safe='/')
        retriever.location_metadata[pdf_url] = {
            'repository': 'NIH NLM NCBI PubMed Central Article Datasets', 'metadata_url': metadata_url,
            'metadata_hash': digest(value), 'license': value.get('license_code') or 'unknown',
            'version': prefix[:-1], 'is_manuscript': value.get('is_manuscript'),
            'is_retracted': value.get('is_retracted'), 'expected_md5': checksum,
            'versions_available': [p[:-1] for p in prefixes],
            'requires_version_review': len(prefixes) > 1 and requested is None,
        }
        candidates.append((pdf_url, 'pmc_cloud'))
    return candidates
