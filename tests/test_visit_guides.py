from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from visit_guides import gates, hours, relevant, write_guides

ROOT = Path(__file__).resolve().parents[1]


class ParkGuides(unittest.TestCase):
    def test_date_window_uses_source_local_day_and_both_end_fields(self):
        row = {'effective':'2026-03-02T03:00:00Z','end':None,'expires':'2026-03-03'}
        self.assertTrue(relevant(row, date(2026, 3, 1)))
        self.assertFalse(relevant(row, date(2026, 3, 4)))
        row['end'] = '2026-03-01'
        self.assertFalse(relevant(row, date(2026, 3, 2)))

    def test_prior_and_incomplete_dates_do_not_imply_a_season(self):
        park = {'dates': [
            {'kind':'Gate','year':2025,'start':'2025-01-01','end':'2025-12-31','annual':True},
            {'kind':'Gate','year':2026,'start':'2026-01-01','end':None},
            {'kind':'Winter fee','year':2026,'start':'2026-01-01','end':'2026-03-30'}],
            'gate':{'present':False,'all_day':True}}
        self.assertEqual(gates(park, 2026), [])
        self.assertEqual(hours(park), '')

    def test_offline_publication_source_join_and_expansion(self):
        data = json.loads((ROOT/'data/index.json').read_text())
        tool = json.loads((ROOT/'tool.json').read_text())
        # An additional source ID with a new name and a markup-like facility note.
        sample = dict(data['parks'][0], id=987654, name='Extra <park>',
                      facilities=[{'name':'Drinking water','detail':'<script>bottles</script>'}])
        data['parks'] = [sample]
        data['advisories'] = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'config').mkdir()
            (root/'config/guides.json').write_text(json.dumps([{'slug':'new-area','name':'Additional parks','intro':'Compare parks.',
                                            'parks':{'extra':987654,'absent':12345}}]))
            page = write_guides(root, root, data, tool, '{{GUIDE_PATHS}}', True)
            self.assertEqual(json.loads(page), {'987654':'extra'})
            urls = [node.text for node in ET.parse(root/'sitemap.xml').findall('.//{*}loc')]
            self.assertEqual(len(set(urls)), 3)
            self.assertFalse((root/'records/absent').exists())
            for url in urls:
                relative = url.removeprefix('https://coolcode.ca/parkready/')
                html = (root / relative / 'index.html').read_text()
                self.assertIn(f'rel="canonical" href="{url}"', html)
                self.assertEqual(html.count('<h1>'), 1)
            article = (root/'records/extra/index.html').read_text()
            self.assertIn('&lt;script&gt;bottles&lt;/script&gt;', article)
            region = (root/'records/new-area/index.html').read_text()
            self.assertIn('href="../extra/#facility-drinking-water"', region)
            self.assertIn('id="facility-drinking-water"', article)
            self.assertIn('No park-specific notice', article)
            self.assertIn('park=987654#details', article)
