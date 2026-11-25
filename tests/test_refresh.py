import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh

class SourceTests(unittest.TestCase):
    def test_complete_pagination_and_duplicate_rejection(self):
        config={'api_base':'https://source.invalid/api','page_size':2,'max_pages':4}
        def source(url):
            page=int(parse_qs(urlsplit(url).query)['pagination[page]'][0])
            return {'data':[{'id':i} for i in ([1,2] if page==1 else [3])],'meta':{'pagination':{'page':page,'pageSize':2,'pageCount':2,'total':3}}}
        self.assertEqual([p['id'] for p in refresh.fetch_all('parks',{},config,source)],[1,2,3])
        def duplicate(url):
            doc=source(url)
            if doc['meta']['pagination']['page']==2:doc['data']=[{'id':1}]
            return doc
        with self.assertRaisesRegex(ValueError,'Duplicate'):refresh.fetch_all('parks',{},config,duplicate)
        def changing(url):
            doc=source(url)
            if doc['meta']['pagination']['page']==2:doc['meta']['pagination']['total']=4
            return doc
        with self.assertRaisesRegex(ValueError,'changed'):refresh.fetch_all('parks',{},config,changing)

    def test_zero_notices_requires_complete_pagination(self):
        config={'api_base':'https://source.invalid/api','page_size':2,'max_pages':2}
        doc={'data':[],'meta':{'pagination':{'page':1,'pageSize':2,'pageCount':0,'total':0}}}
        self.assertEqual(refresh.fetch_all('notices',{},config,lambda _:doc),[])
        doc['meta']['pagination']['total']=2
        with self.assertRaisesRegex(ValueError,'count'):refresh.fetch_all('notices',{},config,lambda _:doc)

    def test_normalization_removes_markup_internal_notes_and_inactive_rows(self):
        park={'id':1,'orcs':44,'protectedAreaName':'Test <b>Park</b>','isDisplayed':True,'legalStatus':'Active','url':'https://bcparks.ca/test/','latitude':50,'longitude':-125,'adminNote':'INTERNAL',
              'parkFacilities':[{'name':'44:Water','isActive':True,'description':'<p>Seasonal</p><script>bad()</script>'}],
              'parkDates':[{'isActive':True,'operatingYear':2025,'startDate':'2025-05-01','endDate':'2025-09-30','isDateAnnual':True,'parkDateType':{'id':1,'dateType':'Gate'}}]}
        notice={'advisoryNumber':1,'title':'Closure','advisoryStatus':{'code':'PUB'},'protectedAreas':[{'orcs':44}],'links':[{'url':'javascript:bad()'},{'url':'https://bcparks.ca/','title':'Official'}]}
        parks,notices=refresh.normalize([park,{**park,'orcs':45,'isDisplayed':False}],[notice,{**notice,'advisoryStatus':{'code':'DRAFT'}}])
        self.assertEqual(len(parks),1);self.assertEqual(parks[0]['name'],'Test Park');self.assertEqual(parks[0]['facilities'][0]['detail'],'Seasonal')
        self.assertTrue(parks[0]['dates'][0]['annual']);self.assertEqual(notices[0]['parks'],[44]);self.assertEqual(len(notices[0]['links']),1)
        self.assertNotIn('INTERNAL',json.dumps(parks))
        park['parkDates'][0]['startDate']='2025-02-30'
        with self.assertRaises(ValueError):refresh.normalize([park],[])

    def test_source_dates_reject_invalid_calendar_and_naive_instants(self):
        self.assertEqual(refresh.source_date('2026-11-24'),'2026-11-24')
        self.assertEqual(refresh.source_date('2026-11-24T02:00:00Z'),'2026-11-24T02:00:00Z')
        for value in ['2026-02-30','2026-11-24T02:00:00']:
            with self.assertRaises(ValueError):refresh.source_date(value)

    def test_failed_refresh_preserves_every_last_good_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'config').mkdir();(root/'data').mkdir()
            (root/'config/source.json').write_text(json.dumps({'api_base':'https://bcparks.api.gov.bc.ca/api','page_size':2,'max_pages':2}))
            for name in ['index.json','status.json']:(root/'data'/name).write_text('last-good')
            def fail(_):raise OSError('source unavailable')
            with self.assertRaises(OSError):refresh.refresh(root,fail)
            for name in ['index.json','status.json']:self.assertEqual((root/'data'/name).read_text(),'last-good')

if __name__=='__main__':unittest.main()
