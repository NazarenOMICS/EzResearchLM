import io
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter

from ez.acquisition import Retriever, archive_pdf, failure, normalize_doi
from ez.acquisition import verify_identity
from ez.consent import create_anna, validate_anna
from ez.contracts import ContractError


class Response:
    def __init__(self, status=200, data=b'', headers=None):
        self.status_code, self.data, self.headers = status, data, headers or {}
        self.closed = False

    def iter_content(self, size):
        yield self.data

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.headers = {}
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class AcquisitionTests(unittest.TestCase):
    def test_addendum_citing_original_doi_is_not_the_original_paper(self):
        from types import SimpleNamespace
        source = {'title': 'The FAIR Guiding Principles for scientific data management and stewardship', 'doi': '10.1038/sdata.2016.18'}
        header = 'https://doi.org/10.1038/s41597-019-0009-6\nAddendum: ' + source['title'] + '\nAddendum to: https://doi.org/' + source['doi']
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: header)], metadata={})
        with patch('PyPDF2.PdfReader', return_value=reader):
            self.assertEqual(verify_identity('synthetic.pdf', source), 'needs_review')
            # Conflicting document identifiers remain ambiguous without a notice label.
            header = header.replace('Addendum', 'Related paper')
            self.assertEqual(verify_identity('synthetic.pdf', source), 'needs_review')

    def test_identity_accepts_font_ligatures_but_not_an_unrelated_title(self):
        from types import SimpleNamespace
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: 'A scienti ﬁc data example\nAuthors and text')],
                                 metadata={'/Subject': 'doi:10.1234/example'})
        with patch('PyPDF2.PdfReader', return_value=reader):
            self.assertEqual(verify_identity('synthetic.pdf', {'title': 'A scientific data example', 'doi': '10.1234/example'}), 'verified')
            self.assertEqual(verify_identity('synthetic.pdf', {'title': 'An unrelated paper title', 'doi': '10.1234/example'}), 'needs_review')
            self.assertEqual(verify_identity('synthetic.pdf', {'title': 'A scientific data example', 'doi': '10.1234/other'}), 'needs_review')
    def test_anna_requires_matching_unexpired_consent(self):
        source = {'source_id': 's1', 'doi': '10.1234/example'}
        receipt = create_anna(source, 'https://annas-archive.org/md5/' + 'a' * 32, 'run1')
        validate_anna(receipt, source)
        with self.assertRaises(ContractError):
            validate_anna(receipt, dict(source, source_id='different'))
        receipt['expires_at'] = '2000-01-01T00:00:00+00:00'
        with self.assertRaises(ContractError):
            validate_anna(receipt, source)
        with self.assertRaises(ContractError):
            create_anna(source, 'https://annas-archive.org/slow_download/x', 'run1')

    def test_anna_is_never_contacted_without_consent_and_runs_after_public_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = {'source_id': 's1', 'doi': '10.1234/example'}
            retriever = Retriever(folder, 's1', session=Session([]), check_url=lambda u: None)
            self.assertEqual(retriever.acquire(source, candidates=[])['acquisition_status'], 'manual_needed')
            source['anna_consent'] = create_anna(source, 'https://annas-archive.org/md5/' + 'b' * 32, 'run1')
            session = Session([Response(404), Response(data=b'<html>captcha</html>')])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            result = retriever.acquire(source, candidates=[('https://repository.example/paper.pdf', 'direct')])
            self.assertEqual(result['acquisition_status'], 'manual_needed')
            self.assertEqual([url for url, _ in session.calls], ['https://repository.example/paper.pdf', source['anna_consent']['url']])
            self.assertEqual(result['attempts'][-1]['failure_code'], 'captcha_or_challenge')
    def test_challenge_stops_same_host_and_records_diagnosis(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(data=b'<html>verify you are human</html>')])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            self.assertEqual(retriever.request('https://example.org/a', 'direct'), (None, None))
            retriever.request('https://example.org/b', 'direct')
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(retriever.history[0]['failure_code'], 'captcha_or_challenge')
            self.assertEqual(retriever.history[1]['failure_code'], 'circuit_open')

    def test_redirect_revalidated_and_tls_never_downgraded(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(302, headers={'Location': 'http://example.org/x'})])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            retriever.request('https://example.org/x', 'direct')
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(retriever.history[0]['failure_code'], 'tls_downgrade')

    def test_rate_limit_longer_than_budget_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(429, headers={'Retry-After': '3600'})])
            retriever = Retriever(folder, 's1', seconds=1, session=session, check_url=lambda u: None)
            start = time.monotonic()
            retriever.request('https://example.org/x', 'direct')
            self.assertLess(time.monotonic() - start, 1)
            self.assertEqual(len(session.calls), 1)
            self.assertIn('example.org', retriever.circuit)

    def test_redirect_cannot_revisit_a_host_that_already_denied_access(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(403), Response(302, headers={'Location': 'https://denied.example/paper'})])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            retriever.request('https://denied.example/first', 'direct')
            retriever.request('https://resolver.example/doi', 'doi')
            self.assertEqual(len(session.calls), 2)
            self.assertEqual(retriever.history[-1]['failure_code'], 'circuit_open')

    def test_malformed_provider_rows_do_not_discard_a_direct_location(self):
        def broken(url, provider):
            return {'locations': [None], 'results': None, 'resultList': None}
        with tempfile.TemporaryDirectory() as folder:
            retriever = Retriever(folder, 's1')
            with patch.object(retriever, 'metadata', side_effect=broken):
                locations = retriever.locations({'doi': '10.1234/example', 'pdf_url': 'https://repo.example/paper.pdf'})
            self.assertIn(('https://repo.example/paper.pdf', 'direct'), locations)
            self.assertIn('invalid_metadata', [r.get('failure_code') for r in retriever.history])

    def test_provider_identity_filters_and_repository_locations(self):
        doi = '10.1234/example'
        def metadata(url, provider):
            if provider == 'core':
                return {'results': [{'id': 1, 'doi': doi, 'downloadUrl': 'https://repo.example/a.pdf'},
                                    {'id': 2, 'doi': '10.1234/other', 'downloadUrl': 'https://wrong.example/b.pdf'}]}
            if provider == 'openaire':
                return {'results': [{'id': 'work1', 'pids': [{'scheme': 'doi', 'value': doi}], 'instances': [
                    {'accessRight': {'code': 'c_abf2'}, 'urls': ['https://repository.example/fulltext'], 'license': 'CC-BY'},
                    {'accessRight': {'code': 'c_14cb'}, 'urls': ['https://closed.example/fulltext']}]}]}
            return {}
        with tempfile.TemporaryDirectory() as folder:
            retriever = Retriever(folder, 's1')
            with patch.object(retriever, 'metadata', side_effect=metadata):
                locations = retriever.locations({'doi': doi, 'pdf_url': 'https://direct.example/a.pdf'})
            self.assertIn(('https://repo.example/a.pdf', 'core'), locations)
            self.assertIn(('https://repository.example/fulltext', 'openaire'), locations)
            self.assertFalse(any('wrong.example' in u or 'closed.example' in u for u, _ in locations))
            self.assertEqual(retriever.location_metadata['https://repository.example/fulltext']['license'], 'CC-BY')

    def test_archive_ambiguity_cannot_silently_select_supplement(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name in ('../supplement.pdf', 'main.pdf'):
                payload = b'%PDF-invalid-but-multiple'
                member = tarfile.TarInfo(name); member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        with self.assertRaisesRegex(ValueError, 'ambiguous_archive'):
            archive_pdf(buffer.getvalue(), {})

    def test_fake_pdf_and_corrupt_pdf_are_distinct_from_download_success(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(data=b'<html>not a paper</html>'), Response(data=b'%PDF-1.4 invalid')])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            with patch.object(retriever, 'locations', return_value=[('https://one.example/a', 'direct'), ('https://two.example/b', 'core')]):
                result = retriever.acquire({'source_id': 's1'})
            self.assertEqual(result['acquisition_status'], 'manual_needed')
            codes = [h.get('failure_code') for h in result['attempts']]
            self.assertIn('html_instead_of_pdf', codes)
            self.assertIn('corrupt_pdf', codes)

    def test_valid_pdf_is_preserved_but_identity_needs_review(self):
        buffer = io.BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(buffer)
        with tempfile.TemporaryDirectory() as folder:
            session = Session([Response(data=buffer.getvalue())])
            retriever = Retriever(folder, 's1', session=session, check_url=lambda u: None)
            with patch.object(retriever, 'locations', return_value=[('https://repo.example/paper.pdf?secret=never-log', 'direct')]):
                result = retriever.acquire({'source_id': 's1'})
            self.assertEqual(result['validation_status'], 'valid')
            self.assertEqual(result['identity_status'], 'needs_review')
            self.assertNotIn('secret', str(result['provenance']))
            self.assertNotIn('secret', str(result['attempts']))
            self.assertTrue(Path(result['pdf_path']).is_file())

    def test_known_pdf_is_tried_before_metadata_can_consume_the_budget(self):
        buffer = io.BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(buffer)
        with tempfile.TemporaryDirectory() as folder:
            retriever = Retriever(folder, 's1', session=Session([Response(data=buffer.getvalue())]), check_url=lambda u: None)
            with patch.object(retriever, 'locations', side_effect=AssertionError('Metadata lookup must be unnecessary')):
                result = retriever.acquire({'source_id': 's1', 'doi': '10.1234/example', 'pdf_url': 'https://repo.example/known.pdf'})
            self.assertEqual(result['validation_status'], 'valid')
            self.assertEqual(len(result['attempts']), 1)

    def test_many_openalex_locations_do_not_starve_other_providers(self):
        doi = '10.1234/example'
        def metadata(url, provider):
            if provider == 'openalex':
                return {'locations': [{'is_oa': True, 'pdf_url': f'https://repo.example/{n}.pdf'} for n in range(60)]}
            if provider == 'core':
                return {'results': [{'doi': doi, 'downloadUrl': 'https://core-repo.example/paper.pdf'}]}
            return {}
        with tempfile.TemporaryDirectory() as folder:
            retriever = Retriever(folder, 's1')
            with patch.object(retriever, 'metadata', side_effect=metadata):
                candidates = retriever.locations({'doi': doi})
            self.assertLess(next(i for i, (_, p) in enumerate(candidates) if p == 'core'), 5)
