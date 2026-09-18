"""Bounded, provenance-preserving public acquisition. No access-control bypass."""
from hashlib import sha256, md5
import ipaddress
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
import tarfile
import time
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit, quote

import requests
from bs4 import BeautifulSoup

from .contracts import now, digest
from .pdf import validate_pdf
from .state import atomic_json


def safe_url(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc.split('@')[-1], parsed.path, '', ''))


def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('unsupported_url')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('non_public_url')


def failure(response, prefix=b''):
    text = prefix.decode('utf-8', errors='ignore').lower()
    if response.status_code == 429:
        return 'rate_limited'
    if any(x in text for x in ('captcha', 'cf-chl-', 'ddos-guard', 'verify you are human')):
        return 'captcha_or_challenge'
    if response.status_code == 401:
        return 'auth_required'
    if response.status_code == 403:
        return 'access_denied'
    if response.status_code == 404:
        return 'not_found'
    if response.status_code >= 500:
        return 'provider_unavailable'
    if response.status_code >= 400:
        return 'unknown_access_failure'
    if any(x in text for x in ('purchase this article', 'subscribe to access', 'access through your institution')):
        return 'paywall'
    return None


class Retriever:
    def __init__(self, root, source_id, seconds=600, attempts=3, *, session=None, check_url=public_url):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.source_id = source_id
        self.deadline = time.monotonic() + seconds
        self.attempts = min(3, max(1, attempts))
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': 'EZresearchLM/0.2 (academic acquisition; no access bypass)'})
        self.check_url = check_url
        self.history = []
        self.circuit = set()
        self.location_metadata = {}

    def record(self, event):
        self.history.append(event)
        atomic_json(self.root / 'attempts.json', self.history)

    def request(self, url, provider):
        try:
            host = urlsplit(url).hostname
        except ValueError:
            self.record({'provider': provider, 'result': 'failed', 'failure_code': 'invalid_url', 'at': now()})
            return None, None
        if host in self.circuit:
            self.record({'provider': provider, 'url': safe_url(url), 'result': 'skipped', 'failure_code': 'circuit_open', 'at': now()})
            return None, None
        for attempt in range(1, self.attempts + 1):
            if time.monotonic() >= self.deadline:
                return None, None
            event = {'attempt_id': f'{self.source_id}-{len(self.history)+1}', 'source_id': self.source_id,
                     'provider': provider, 'url': safe_url(url), 'started_at': now(), 'attempt': attempt, 'result': 'started'}
            self.record(event)
            response = None
            data = bytearray()
            code = None
            try:
                current = url
                for _ in range(6):
                    if urlsplit(current).hostname in self.circuit:
                        raise ValueError('circuit_open')
                    self.check_url(current)
                    remaining = max(.1, self.deadline - time.monotonic())
                    headers = {}
                    if urlsplit(current).hostname == 'api.core.ac.uk' and os.environ.get('EZRESEARCH_CORE_API_KEY'):
                        headers['Authorization'] = 'Bearer ' + os.environ['EZRESEARCH_CORE_API_KEY']
                    response = self.session.get(current, timeout=(min(10, remaining), min(30, remaining)), stream=True, allow_redirects=False, headers=headers)
                    if response.status_code not in (301, 302, 303, 307, 308):
                        break
                    target = urljoin(current, response.headers.get('Location', ''))
                    if urlsplit(current).scheme == 'https' and urlsplit(target).scheme != 'https':
                        raise ValueError('tls_downgrade')
                    response.close()
                    current = target
                else:
                    raise ValueError('redirect_limit')
                event.update(http_status=response.status_code, final_url=safe_url(current), content_type=response.headers.get('Content-Type', ''))
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if time.monotonic() > self.deadline:
                        raise TimeoutError()
                    if len(data) > 100 * 1024 * 1024:
                        raise ValueError('file_too_large')
                code = failure(response, bytes(data[:32768]))
                if not code:
                    event.update(result='received', bytes=len(data), ended_at=now())
                    atomic_json(self.root / 'attempts.json', self.history)
                    return bytes(data), current
            except requests.exceptions.SSLError:
                code = 'tls_error'
            except (requests.exceptions.Timeout, TimeoutError):
                code = 'network_timeout'
            except requests.exceptions.ConnectionError:
                code = 'connection_error'
            except requests.exceptions.RequestException:
                code = 'network_protocol_error'
            except (ValueError, OSError) as exc:
                code = str(exc) if isinstance(exc, ValueError) else 'dns_error'
            finally:
                if response is not None:
                    response.close()
            event.update(result='failed', failure_code=code, ended_at=now())
            atomic_json(self.root / 'attempts.json', self.history)
            if code in ('captcha_or_challenge', 'access_denied', 'auth_required'):
                self.circuit.add(host)
                self.circuit.add(urlsplit(current).hostname)
            if code not in ('network_timeout', 'connection_error', 'provider_unavailable', 'rate_limited'):
                break
            delay = 2 ** (attempt - 1)
            if response is not None and code == 'rate_limited':
                value = response.headers.get('Retry-After', '')
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    # Unknown/date-shaped limits must not be ignored by immediately retrying.
                    self.circuit.add(host)
                    break
            if time.monotonic() + delay >= self.deadline or attempt == self.attempts:
                if code == 'rate_limited':
                    self.circuit.add(host)
                break
            time.sleep(delay)
        return None, None

    def metadata(self, url, provider):
        data, _ = self.request(url, provider)
        if data:
            try:
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise ValueError('metadata must be an object')
                return value
            except (ValueError, UnicodeDecodeError):
                self.record({'provider': provider, 'result': 'failed', 'failure_code': 'invalid_metadata', 'at': now()})
        return {}

    def locations(self, record):
        """Resolve all applicable OA locations, even if an earlier URL exists."""
        candidates = [(u, 'direct') for u in [record.get('pdf_url'), *self.strings(record.get('pdf_urls') or [], 'input')] if isinstance(u, str) and u]
        doi = normalize_doi(record.get('doi'))
        pmcid = record.get('pmcid')
        if doi:
            candidates.append(('https://doi.org/' + quote(doi, safe='/'), 'doi'))
            data = self.metadata('https://api.openalex.org/works/https://doi.org/' + quote(doi, safe='/'), 'openalex')
            for location in self.rows(data.get('locations', []), 'openalex'):
                if location.get('is_oa'):
                    for key in ('pdf_url', 'landing_page_url'):
                        if isinstance(location.get(key), str) and location[key]:
                            candidates.append((location[key], 'openalex'))
                            self.location_metadata[location[key]] = {'license': location.get('license'), 'version': location.get('version'), 'source': location.get('source')}
            email = os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL')
            if email:
                data = self.metadata('https://api.unpaywall.org/v2/' + quote(doi, safe='/') + '?email=' + quote(email), 'unpaywall')
                for location in self.rows(data.get('oa_locations', []), 'unpaywall'):
                    for key in ('url_for_pdf', 'url'):
                        if isinstance(location.get(key), str) and location[key]:
                            candidates.append((location[key], 'unpaywall'))
                            self.location_metadata[location[key]] = {'license': location.get('license'), 'version': location.get('version'), 'host_type': location.get('host_type')}
            else:
                self.record({'provider': 'unpaywall', 'result': 'skipped', 'failure_code': 'missing_email', 'at': now()})
        query = 'DOI:' + doi if doi else ('EXT_ID:' + str(record['pmid']) if record.get('pmid') else '')
        if query:
            data = self.metadata('https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&query=' + quote(query), 'europepmc')
            result_list = data.get('resultList')
            for row in self.rows(result_list.get('result', []) if isinstance(result_list, dict) else [], 'europepmc'):
                if isinstance(row.get('pmcid'), str):
                    pmcid = pmcid or row['pmcid']
        if isinstance(pmcid, str) and re.fullmatch(r'PMC\d+', pmcid):
            from .pmc import locations as pmc_locations
            candidates.extend(pmc_locations(self, dict(record, pmcid=pmcid)))
            candidates.append(('https://europepmc.org/articles/' + pmcid + '?pdf=render', 'europepmc'))
        if doi:
            data = self.metadata('https://api.core.ac.uk/v3/search/works/?q=' + quote('doi:"' + doi + '"') + '&limit=5', 'core')
            for work in self.rows(data.get('results', []), 'core'):
                if normalize_doi(work.get('doi')) != doi:
                    continue
                rows = [work]
                # Output-level URLs often contain the repository's full text.
                for output_url in self.strings(work.get('outputs') or [], 'core')[:3]:
                    if isinstance(output_url, str) and re.fullmatch(r'https://api\.core\.ac\.uk/v3/outputs/\d+', output_url):
                        rows.append(self.metadata(output_url, 'core'))
                for row in rows:
                    for url in [row.get('downloadUrl'), *self.strings(row.get('sourceFulltextUrls') or [], 'core')]:
                        if isinstance(url, str) and url:
                            candidates.append((url, 'core'))
                            self.location_metadata[url] = {'record_id': row.get('id'), 'license': row.get('license'), 'version': row.get('documentType')}
            data = self.metadata('https://api.openaire.eu/graph/v3/research-products?pid=' + quote(doi) + '&pageSize=5', 'openaire')
            for work in self.rows(data.get('results', []), 'openaire'):
                if not any(p.get('scheme') == 'doi' and normalize_doi(p.get('value')) == doi for p in self.rows(work.get('pids', []), 'openaire')):
                    continue
                for instance in self.rows(work.get('instances', []), 'openaire'):
                    access = instance.get('accessRight')
                    if not isinstance(access, dict) or access.get('code') != 'c_abf2':
                        continue
                    for url in self.strings(instance.get('urls') or [], 'openaire'):
                        if isinstance(url, str) and url:
                            candidates.append((url, 'openaire'))
                            self.location_metadata[url] = {'record_id': work.get('id'), 'license': instance.get('license'), 'version': work.get('version'), 'repository': instance.get('hostedBy')}
        # Fairly interleave providers so a long location list from one API does
        # not consume the bounded route count before PMC or other repositories.
        groups = {}
        for candidate in dict.fromkeys(candidates):
            groups.setdefault(candidate[1], []).append(candidate)
        order = [p for p in ('direct', 'pmc_cloud', 'doi', 'europepmc', 'openalex', 'unpaywall', 'core', 'openaire') if p in groups]
        return [groups[p][index] for index in range(max((len(v) for v in groups.values()), default=0))
                for p in order if index < len(groups[p])]

    def rows(self, value, provider):
        if not isinstance(value, list):
            self.record({'provider': provider, 'result': 'failed', 'failure_code': 'invalid_metadata', 'at': now()})
            return []
        if any(not isinstance(row, dict) for row in value):
            self.record({'provider': provider, 'result': 'failed', 'failure_code': 'invalid_metadata', 'at': now()})
        return [row for row in value if isinstance(row, dict)]

    def strings(self, value, provider):
        if not isinstance(value, list):
            self.record({'provider': provider, 'result': 'failed', 'failure_code': 'invalid_metadata', 'at': now()})
            return []
        return [item for item in value if isinstance(item, str) and item]

    def acquire(self, record, *, candidates=None):
        resolved = candidates is not None
        # Try already-known PDF locations before spending their time budget on
        # discovery APIs. Resolve additional routes only after those fail.
        candidates = ([(u, 'direct') for u in [record.get('pdf_url'), *self.strings(record.get('pdf_urls') or [], 'input')]
                       if isinstance(u, str) and u] if candidates is None else list(candidates))
        seen = set()
        anna_considered = False
        fallback_after = []
        while candidates or not resolved or not anna_considered:
            if not candidates and not resolved:
                resolved = True
                candidates = self.locations(record)
                continue
            if not candidates:
                anna_considered = True
                if record.get('anna_consent'):
                    from .consent import validate_anna
                    receipt = validate_anna(record['anna_consent'], record)
                    fallback_after = list(dict.fromkeys(h['provider'] for h in self.history if h.get('attempt_id') and h['provider'] != 'anna_archive'))
                    candidates.append((receipt['url'], 'anna_archive'))
                else:
                    break
            url, provider = candidates.pop(0)
            if len(seen) >= 40 or time.monotonic() >= self.deadline:
                break
            if url in seen:
                continue
            seen.add(url)
            data, final = self.request(url, provider)
            if not data:
                continue
            location = self.location_metadata.get(url, {})
            expected_md5 = location.get('expected_md5')
            if expected_md5 and md5(data).hexdigest() != expected_md5:
                self.record({'provider': provider, 'result': 'failed', 'failure_code': 'provider_checksum_mismatch', 'at': now()})
                continue
            if provider == 'pmc_oa' and data.startswith(b'\x1f\x8b'):
                try:
                    data = archive_pdf(data, record)
                except ValueError as exc:
                    self.record({'provider': provider, 'url': safe_url(final), 'result': 'failed', 'failure_code': str(exc), 'at': now()})
                    continue
            if not data.lstrip().startswith(b'%PDF-'):
                soup = BeautifulSoup(data[:2 * 1024 * 1024], 'html.parser')
                links = [x.get('content') for x in soup.select('meta[name="citation_pdf_url"]')]
                links += [x.get('href') for x in soup.select('a[href]') if '.pdf' in x.get('href', '').lower()]
                if len(seen) < 20 and len(candidates) < 80:
                    for link in links[:5]:
                        if link:
                            child = urljoin(final, link)
                            candidates.append((child, provider))
                            self.location_metadata[child] = self.location_metadata.get(url, {})
                self.record({'provider': provider, 'url': safe_url(final), 'result': 'failed', 'failure_code': 'html_instead_of_pdf', 'at': now()})
                continue
            candidate = self.root / 'candidate.pdf'
            candidate.write_bytes(data)
            validation = validate_pdf(candidate)
            if validation['status'] != 'valid':
                self.record({'provider': provider, 'result': 'failed', 'failure_code': validation['reason'], 'at': now()})
                continue
            identity = verify_identity(candidate, record)
            if location.get('requires_version_review') or location.get('is_retracted'):
                identity = 'needs_review'
            output = self.root / (validation['sha256'] + '.pdf')
            if not output.exists():
                os.replace(candidate, output)
            result = dict(record, pdf_path=str(output.resolve()), pdf_source=provider, validation_status='valid',
                          content_sha256=validation['sha256'], identity_status=identity, acquisition_status='downloaded', notebook_status='pending')
            result['provenance'] = {'requested_url': safe_url(url), 'final_url': safe_url(final), 'acquired_at': now(),
                                    'validation': validation, 'location': self.location_metadata.get(url, {}),
                                    'acquisition_policy': 'public_route', 'source_version': self.location_metadata.get(url, {}).get('version') or 'unknown'}
            if provider == 'anna_archive':
                result.update(acquisition_policy='non_oa_fallback', fallback_after=fallback_after,
                              consent_id=record['anna_consent']['consent_id'])
                result['provenance'].update(acquisition_policy='non_oa_fallback', fallback_after=fallback_after,
                                             consent_id=record['anna_consent']['consent_id'])
            result['attempts'] = self.history
            return result
        reason = 'source_budget_exhausted' if time.monotonic() >= self.deadline else 'candidate_limit' if len(seen) >= 40 else 'routes_exhausted'
        return dict(record, acquisition_status='manual_needed', validation_status='unknown', failure_code=reason, attempts=self.history)


def normalize_doi(value):
    value = str(value or '').lower().strip()
    return re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)


def archive_pdf(data, record):
    """Read bounded archive members in memory, never extract paths or pick alphabetically."""
    pdfs = []
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for index, member in enumerate(archive):
                total += member.size
                if index >= 1000 or total > 200 * 1024 * 1024:
                    raise ValueError('archive_limit')
                if not member.isfile() or not member.name.lower().endswith('.pdf'):
                    continue
                if member.size > 100 * 1024 * 1024:
                    raise ValueError('archive_limit')
                stream = archive.extractfile(member)
                payload = stream.read(member.size + 1)
                if len(payload) != member.size:
                    raise ValueError('corrupt_archive')
                pdfs.append(payload)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError('corrupt_archive') from exc
    if len(pdfs) == 1:
        return pdfs[0]
    doi = normalize_doi(record.get('doi'))
    matched = []
    if doi:
        from PyPDF2 import PdfReader
        for payload in pdfs:
            try:
                reader = PdfReader(io.BytesIO(payload), strict=True)
                if reader_identity(reader, record) == 'verified':
                    matched.append(payload)
            except Exception:
                continue
    if len(matched) != 1:
        raise ValueError('ambiguous_archive' if pdfs else 'archive_without_pdf')
    return matched[0]


def verify_identity(path, record):
    if record.get('identifier_conflicts'):
        return 'needs_review'
    from PyPDF2 import PdfReader
    try:
        reader = PdfReader(str(path))
        return reader_identity(reader, record)
    except Exception:
        return 'needs_review'


def reader_identity(reader, record):
    """Conservative identity: a cited original DOI cannot identify an addendum."""
    try:
        text = unicodedata.normalize('NFKC', ' '.join((p.extract_text() or '') for p in list(reader.pages)[:2])).casefold()
        doi = normalize_doi(record.get('doi'))
        title_words = re.findall(r'\w+', unicodedata.normalize('NFKC', record.get('title') or '').casefold())
        # Fonts may extract ligatures as "scienti fic". Compare the full title's
        # characters in the header, without permitting approximate title matches.
        header = ''.join(re.findall(r'\w+', text[:1800]))
        title_matches = len(title_words) >= 3 and ''.join(title_words) in header
        metadata = unicodedata.normalize('NFKC', str(reader.metadata or {})).casefold()
        identity_text = text[:1800] + '\n' + metadata
        # Corrections often repeat both the complete title and DOI of the original.
        # Even when such a notice is the intended source, require explicit review.
        if re.search(r'\b(addendum|corrigendum|erratum|correction|retraction)\b', identity_text):
            return 'needs_review'
        found_dois = {value.rstrip('.,;:)]}') for value in re.findall(r'10\.\d{4,9}/[^\s<>\x27\x22]+', identity_text)}
        if found_dois - {doi}:
            return 'needs_review'
        if doi and title_matches and re.search(re.escape(doi) + r'(?![\w./-])', identity_text):
            return 'verified'
    except Exception:
        pass
    return 'needs_review'


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--attempts', type=int, default=3)
    args = parser.parse_args()
    record = json.loads(Path(args.record).read_text(encoding='utf-8-sig'))
    result = Retriever(Path(args.output).parent, record['source_id'], args.seconds, args.attempts).acquire(record)
    result['acquisition_input_hash'] = digest(record)
    atomic_json(args.output, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
