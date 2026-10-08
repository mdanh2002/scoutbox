from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from portal.services.focus import _sanitize_focus_label
from portal.services.pagefetch import fetch_target
from portal.templatetags.portal_extras import remote_sort_value, post_age_provenance_tooltip

class Release010102Tests(SimpleTestCase):
    def test_focus_label_is_ai_vocab_but_slash_free(self):
        self.assertEqual(_sanitize_focus_label('Embedded / Firmware'),'Embedded and Firmware')
        self.assertEqual(_sanitize_focus_label('Infrastructure / Platform'),'Infrastructure and Platform')

    def test_remote_sort_order(self):
        def row(status): return SimpleNamespace(extracted_facts={'remote_classification':{'status':status}})
        self.assertLess(remote_sort_value(row('fully_remote')),remote_sort_value(row('remote')))
        self.assertEqual(remote_sort_value(row('remote')),remote_sort_value(row('hybrid')))
        self.assertLess(remote_sort_value(row('hybrid')),remote_sort_value(row('onsite')))
        self.assertLess(remote_sort_value(row('onsite')),remote_sort_value(row('unknown')))

    def test_post_age_hides_obvious_schema_evidence(self):
        row=SimpleNamespace(
            freshness_label='< 1 week',freshness_confidence=95,declared_posted_at=None,estimated_first_seen=None,
            extracted_facts={'post_age':{'post_age_method':'explicit','post_age_reason':'Best available evidence: JobPosting schema · datePosted.','exact_source':'Page content'}}
        )
        tip=post_age_provenance_tooltip(row)
        self.assertIn('Post age:',tip); self.assertIn('Source: Page content',tip)
        self.assertNotIn('Evidence:',tip); self.assertNotIn('Reason:',tip)

    @patch('portal.services.pagefetch.requests.get')
    def test_pdf_is_not_downloaded(self,get):
        response=Mock(status_code=200,url='https://example.test/report.pdf')
        response.headers={'Content-Type':'application/pdf','Content-Length':'9000000'}
        response.raise_for_status=Mock(); response.iter_content=Mock(side_effect=AssertionError('binary body should not be consumed'))
        get.return_value=response
        result=fetch_target(response.url)
        self.assertTrue(result['ok']); self.assertTrue(result['is_pdf']); self.assertTrue(result['skipped_binary'])
        self.assertEqual(result['bytes'],0); response.iter_content.assert_not_called(); response.close.assert_called_once()
