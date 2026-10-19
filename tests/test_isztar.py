import unittest
from unittest.mock import patch
from isztar import flatten, search_catalog, get_measures, group_measures, load_catalog, SourceError

class ClientTests(unittest.TestCase):
    def test_full_parent_context_and_leaf_only(self):
        tree={'description':'Maszyny','subgroup':[{'code':'841583','description':'Klimatyzatory bez agregatu','subgroup':[{'code':'8415830090','description':'Pozostałe'}]}]}
        rows=flatten(tree)
        self.assertEqual(len(rows),1)
        self.assertIn('bez agregatu',rows[0]['description'])
        self.assertEqual(search_catalog(rows,'klimatyzator agregatu')[1],1)
        self.assertEqual(search_catalog(rows,'8415 83')[1],1)
        self.assertEqual(search_catalog(rows,'pompa')[1],0)
    def test_incomplete_catalog_fails(self):
        first={'description':'one','subgroup':[], 'links':{'last':'https://ext-isztar4.mf.gov.pl/tariff/rest/goods-nomenclature/codes?page=2'}}
        with patch('isztar.request_json',side_effect=[(first,'source'),SourceError('unavailable')]):
            with self.assertRaises(SourceError):load_catalog('2026-10-16','all')
    def test_mismatched_code_fails(self):
        with patch('isztar.request_json',return_value=({'nomenclature':{'code':'1111111111'},'nonTariffMeasures':[]},'source')):
            with self.assertRaises(SourceError):get_measures('8415830090','2026-10-16')
    def test_groups_and_imports_never_dropped(self):
        items=[{'country':{'code':x},'description':'Kontrola przywozu'} for x in ['RU','BY','ALLTC','XX']]
        grouped=group_measures({'nonTariffMeasures':items})
        self.assertEqual(sum(map(len,grouped.values())),4)
        self.assertEqual(len(grouped['other']),2)
    def test_http_error_not_empty_success(self):
        from isztar import request_json
        with patch('isztar.requests.get') as mock:
            mock.return_value.status_code=503
            mock.return_value.json.return_value={}
            with self.assertRaises(SourceError):request_json('codes',{})

if __name__=='__main__':unittest.main()
