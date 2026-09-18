from hashlib import md5
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter

from ez.acquisition import Retriever
from ez.pmc import BASE, locations


class PmcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.retriever = Retriever(self.temp.name, 's1', attempts=1)
        self.record = {'source_id': 's1', 'pmcid': 'PMC123', 'doi': '10.1234/example'}
        stream = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=72, height=72); writer.write(stream)
        self.pdf = stream.getvalue()

    def metadata(self, url, _):
        version = int(url.split('/')[-1].split('.')[1])
        return {'pmcid': 'PMC123', 'version': version, 'doi': '10.1234/example', 'license_code': 'CC BY',
                'is_manuscript': version == 2, 'is_retracted': False,
                'pdf_url': f's3://pmc-oa-opendata/PMC123.{version}/PMC123.{version}.pdf?md5=' + md5(self.pdf).hexdigest()}

    def resolve(self, versions=(1,), record=None, metadata=None, truncated=False):
        xml = ('<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
               '<IsTruncated>' + str(truncated).lower() + '</IsTruncated>'
               + ''.join(f'<CommonPrefixes><Prefix>PMC123.{v}/</Prefix></CommonPrefixes>' for v in versions)
               + '</ListBucketResult>').encode()
        with patch.object(self.retriever, 'request', return_value=(xml, BASE)), patch.object(self.retriever, 'metadata', side_effect=metadata or self.metadata):
            return locations(self.retriever, record or self.record)

    def test_cloud_metadata_retains_license_version_and_checksum(self):
        found = self.resolve()
        self.assertEqual(found, [(BASE + '/PMC123.1/PMC123.1.pdf', 'pmc_cloud')])
        metadata = self.retriever.location_metadata[found[0][0]]
        self.assertEqual(metadata['license'], 'CC BY')
        self.assertEqual(metadata['version'], 'PMC123.1')
        self.assertEqual(metadata['expected_md5'], md5(self.pdf).hexdigest())

    def test_multiple_versions_need_review_and_explicit_version_is_respected(self):
        found = self.resolve((1, 2))
        self.assertEqual(len(found), 2)
        self.assertTrue(all(self.retriever.location_metadata[u]['requires_version_review'] for u, _ in found))
        with patch.object(self.retriever, 'request', return_value=(self.pdf, found[0][0])), patch('ez.acquisition.verify_identity', return_value='verified'):
            acquired = self.retriever.acquire(self.record, candidates=found)
        self.assertEqual(acquired['identity_status'], 'needs_review')
        selected = self.resolve((1, 2), dict(self.record, pmc_version=2))
        self.assertEqual(len(selected), 1)
        self.assertIn('PMC123.2/', selected[0][0])
        self.assertFalse(self.retriever.location_metadata[selected[0][0]]['requires_version_review'])

    def test_wrong_identity_foreign_bucket_and_truncated_listing_are_rejected(self):
        self.assertEqual(self.resolve(record=dict(self.record, doi='10.1234/wrong')), [])
        def foreign(url, provider):
            value = self.metadata(url, provider); value['pdf_url'] = value['pdf_url'].replace('pmc-oa-opendata', 'other-bucket'); return value
        self.assertEqual(self.resolve(metadata=foreign), [])
        self.assertEqual(self.resolve(truncated=True), [])

    def test_provider_checksum_mismatch_never_becomes_a_valid_pdf(self):
        found = self.resolve()
        with patch.object(self.retriever, 'request', return_value=(self.pdf + b'changed', found[0][0])):
            acquired = self.retriever.acquire(self.record, candidates=found)
        self.assertEqual(acquired['acquisition_status'], 'manual_needed')
        self.assertEqual(acquired['attempts'][-1]['failure_code'], 'provider_checksum_mismatch')
        self.assertFalse(list(Path(self.temp.name).glob('*.pdf')))
