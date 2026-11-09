import importlib.util
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import sync_public_syllabus as sync
import probe_syllabus_search as probe

SAMPLE = '''<html><body><h1>２０２６年度 教育学部シラバス</h1><table>
<tr><td>科目コード</td><td>70000100</td></tr>
<tr><td>科目名</td><td>日本国憲法</td></tr>
<tr><td>担当教員</td><td>宿谷 晃弘</td></tr>
<tr><td>対象学年</td><td>1年</td></tr>
<tr><td>クラス</td><td>０４</td><td>講義室</td><td>Ｃ４０１</td></tr>
<tr><td>開講学期</td><td>秋学期</td><td>開講時期</td><td>秋学期</td></tr>
<tr><td>曜日・時限</td><td>月２</td><td>単位区分</td><td>必修</td></tr>
</table></body></html>'''
KNOWN_URL = 'https://tgusyl.u-gakugei.ac.jp/ext_syllabus/referenceDirect.do?formatCD=1&nologin=on&subjectID=241300000789'

class TestDirectSync(unittest.TestCase):
    def test_parse_verified_html_and_merge(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            (directory/'241300000789.html').write_text(SAMPLE, encoding='utf-8')
            previous = [{'course_id':'separate-001','course_name':'他科目','room_id':'N101'}]
            courses, rooms = sync.build_updated_rows(directory, {'241300000789':KNOWN_URL}, previous, [], '2026-11-08')
            self.assertEqual(len(courses), 2)
            self.assertEqual(len(rooms), 1)
            self.assertEqual(rooms[0]['room_id'], 'C401')
            self.assertEqual([c for c in courses if c['course_id']=='241300000789'][0]['last_verified'], '2026-11-08')

    def test_all_or_nothing_when_missing_html(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                sync.build_updated_rows(Path(d), {'241300000789':KNOWN_URL}, [], [], '2026-11-08')

    def test_all_or_nothing_when_malformed_html(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'241300000789.html').write_text('NOT A SYLLABUS',encoding='utf-8')
            with self.assertRaises(ValueError):
                sync.build_updated_rows(Path(d), {'241300000789':KNOWN_URL}, [], [], '2026-11-08')

    def test_manifest_validation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'url.txt'
            path.write_text(KNOWN_URL + '\n',encoding='utf-8')
            self.assertEqual(sync.read_manifest(path), {'241300000789':KNOWN_URL})
            path.write_text(KNOWN_URL + '\n'+ KNOWN_URL + '\n',encoding='utf-8')
            with self.assertRaises(ValueError): sync.read_manifest(path)
            path.write_text(KNOWN_URL.replace('tgusyl.u-gakugei.ac.jp','example.com'),encoding='utf-8')
            with self.assertRaises(ValueError): sync.read_manifest(path)

    def test_failed_permission_requires_no_network(self):
        self.assertEqual(sync.main([]),2)

    def test_end_to_end_offline_with_mocked_network(self):
        # Simulate a successful official response without issuing any real requests.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'data'
            data.mkdir()
            manifest = root / 'manifest.txt'
            manifest.write_text(KNOWN_URL + '\n', encoding='utf-8')
            (data/'verified_2026_classes.csv').write_text(','.join(sync.FIELDNAMES) + '\n', encoding='utf-8')
            (data/'verified_2026_rooms.csv').write_text(','.join(sync.ROOM_FIELDS) + '\n', encoding='utf-8')
            def fake_download(args):
                path = Path(args[args.index('--output') + 1])
                (path/'241300000789.html').write_text(SAMPLE, encoding='utf-8')
                return 0
            with patch.object(sync, 'download_main', side_effect=fake_download):
                result = sync.main(['--manifest', str(manifest), '--data-dir', str(data), '--permission-confirmed'])
            self.assertEqual(result,0)
            with (data/'verified_2026_classes.csv').open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['course_name'],'日本国憲法')
            status=json.loads((data/'sync_status.json').read_text(encoding='utf-8'))
            self.assertEqual(status['checked_known_urls'],1)
            self.assertEqual(status['coverage'],'partial')

    def test_failed_download_does_not_erase_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            data=root/'data'
            data.mkdir()
            manifest=root/'manifest.txt'
            manifest.write_text(KNOWN_URL + '\n',encoding='utf-8')
            marker=data/'verified_2026_classes.csv'
            marker.write_text('DO NOT DELETE\n',encoding='utf-8')
            with patch.object(sync, 'download_main', return_value=1):
                result=sync.main(['--manifest',str(manifest),'--data-dir',str(data),'--permission-confirmed'])
            self.assertEqual(result,1)
            self.assertEqual(marker.read_text(encoding='utf-8'),'DO NOT DELETE\n')
            self.assertFalse((data/'sync_status.json').exists())

    def test_parse_form_without_hidden_values(self):
        sample = '''<html><form method="post" action="search.do">
        <input type="hidden" name="secret" value="SENSITIVE-VALUE" />
        <select id="year" name="year"><option value="26">２０２６年度</option></select>
        <input type="image" alt="指定の内容で検索" />
        <button>Search</button></form><script src="public.js"></script></html>'''
        p = probe.FormStructure()
        p.feed(sample)
        report=p.report()
        self.assertEqual(report['forms'][0]['method'], 'post')
        self.assertEqual(report['selects'][0]['options'][0]['label'], '２０２６年度')
        self.assertNotIn('SENSITIVE-VALUE', str(report))

if __name__ == '__main__':
    unittest.main()
