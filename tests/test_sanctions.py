import unittest
from sanctions import parse_annex_html, screen, export_evidence, shipment_coverage

URL = 'https://eur-lex.europa.eu/legal-content/PL/TXT/HTML/?uri=CELEX:02014R0833-20260724'
# Synthetic parser fixture, NOT legislation or a sanctions list.
HTML = b'''<html><title>02014R0833-20260724</title>
<p>ANNEX XXXVII</p><p>Note about the scope.</p><table>
<tr><th>CN code</th><th>Description</th></tr>
<tr><td>8415</td><td>Test parent heading</td></tr>
<tr><td>ex 8415 83</td><td>Test restricted description</td></tr>
<tr><td>8418-8419</td><td>Unsupported range retained</td></tr></table>
<p>ANNEX XXXVIII</p><table><tr><td>9999</td><td>Different annex</td></tr></table></html>'''


class SanctionsTests(unittest.TestCase):
    def doc(self):
        return parse_annex_html(HTML, URL, '833/2014', 'XXXVII')

    def test_annex_boundary_and_unsupported_rows(self):
        d = self.doc()
        self.assertEqual([r['code'] for r in d['rows']], ['8415', '841583'])
        self.assertTrue(d['rows'][1]['ex'])
        self.assertEqual(len(d['unparsed_rows']), 1)
        self.assertIn('Note about the scope.', d['notes'])

    def test_prefix_and_ex_are_retained(self):
        r = screen('8415830090', '2026-10-19', {'833/2014:XXXVII': self.doc()})
        check = r['cases'][2]['annex_checks'][0]
        self.assertEqual(len(check['matches']), 2)
        self.assertTrue(check['matches'][1]['ex'])
        self.assertEqual(r['cases'][0]['annex_checks'][0]['matches'], [])

    def test_missing_documents_never_allow(self):
        r = screen('84158300', '2026-10-19', {})
        self.assertTrue(all('NIE WYDANO ZGODY' in c['status'] for c in r['cases']))
        self.assertTrue(all('BRAK DOKUMENTU' in d['status'] for c in r['cases'] for d in c['annex_checks']))

    def test_negative_match_never_allows(self):
        r = screen('99999999', '2026-10-19', {'833/2014:XXXVII': self.doc()})
        self.assertIn('NIE OZNACZA ZGODY', r['cases'][2]['annex_checks'][0]['status'])

    def test_future_version_not_applied_to_past(self):
        r = screen('84158300', '2026-01-01', {'833/2014:XXXVII': self.doc()})
        self.assertIn('PÓŹNIEJSZY', r['cases'][2]['annex_checks'][0]['status'])
        self.assertFalse(r['cases'][2]['annex_checks'][0]['matches'])

    def test_wrong_regulation_or_identity_rejected(self):
        with self.assertRaises(ValueError):
            parse_annex_html(HTML, URL, '765/2006', 'XIX')
        with self.assertRaises(ValueError):
            parse_annex_html(HTML.replace(b'20260724', b'20200101'), URL, '833/2014', 'XXXVII')

    def test_duplicate_heading_rejected(self):
        with self.assertRaises(ValueError):
            parse_annex_html(HTML + b'<p>ANNEX XXXVII</p>', URL, '833/2014', 'XXXVII')

    def test_import_and_groups_not_export_evidence(self):
        snapshot = {'data': {'nonTariffMeasures': [
            {'country': {'code': 'RU'}, 'description': 'Kontrola przywozu'},
            {'country': {'code': 'RU'}, 'description': 'Kontrola wywozu'},
            {'country': {'code': 'ALLTC'}, 'description': 'Kontrola wywozu'},
            {'country': {'code': 'RU'}, 'description': 'Kontrola przywozu/wywozu'}]}}
        r = export_evidence(snapshot, 'RU')
        self.assertEqual(len(r['records']), 1)
        self.assertEqual(len(r['remaining_records']), 3)

    def test_stale_or_sibling_taric_not_attached(self):
        s = {'code': '8415830090', 'date': '2026-10-19', 'data': {'nonTariffMeasures': []}}
        for code, day in [('84158300', '2026-10-19'), ('8415830010', '2026-10-19'), ('8415830090', '2026-10-18')]:
            r = screen(code, day, {}, s)
            self.assertNotIn('isztar', r['cases'][0])

    def test_export_evidence_does_not_create_transit_finding(self):
        s = {'code': '8415830090', 'date': '2026-10-19', 'fetched_at': 'now', 'source': 'test',
             'data': {'nonTariffMeasures': [{'country': {'code': 'RU'}, 'description': 'Kontrola wywozu'}]}}
        r = screen(s['code'], s['date'], {}, s)
        self.assertEqual(len(r['cases'][0]['isztar']['records']), 1)
        self.assertNotIn('isztar', r['cases'][2])
        self.assertIn('BRAK DOKUMENTU', r['cases'][2]['annex_checks'][0]['status'])

    def test_part_coverage_requires_its_own_code_and_date(self):
        parts = [{'number': i+1, 'code': c, 'date': d} for i, (c, d) in enumerate([
            ('8415830090','2026-10-20'), ('8415830090','2026-10-21'), ('8414590090','2026-10-20'), ('','2026-10-20')])]
        result = shipment_coverage(parts, {'code':'8415830090','date':'2026-10-20'})
        self.assertIn('ZGODNY KOD I DATA', result[0]['status'])
        self.assertTrue(all('BRAK KONTROLI' in p['status'] for p in result[1:]))


if __name__ == '__main__':
    unittest.main()
