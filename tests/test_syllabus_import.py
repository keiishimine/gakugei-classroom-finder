import importlib.util
from pathlib import Path
import tempfile
import unittest

p=Path(__file__).resolve().parents[1]/'scripts'/'import_saved_syllabus.py'
spec=importlib.util.spec_from_file_location('syllabus_import',p)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TestSyllabusImporter(unittest.TestCase):
    def test_simple_verified_record(self):
        sample='''<html><body><h1>２０２６年度 教育学部シラバス</h1>
        <table><tr><td>科目コード</td><td>70000100</td></tr>
        <tr><td>科目名</td><td>日本国憲法</td></tr>
        <tr><td>担当教員</td><td>宿谷 晃弘</td></tr>
        <tr><td>対象学年</td><td>1年</td></tr>
        <tr><td>クラス</td><td>０４</td><td>講義室</td><td>Ｃ４０１</td></tr>
        <tr><td>開講学期</td><td>秋学期</td><td>開講時期</td><td>秋学期</td></tr>
        <tr><td>曜日・時限</td><td>月２</td><td>単位区分</td><td>必修</td></tr></table>
        </body></html>'''
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'241300000789.html';path.write_text(sample,encoding='utf-8')
            r=module.parse_one(path,today='2026-11-08')
            self.assertEqual((r['room_id'],r['weekday'],r['period_start'],r['term']),('C401','mon','2','fall'))
            self.assertTrue(r['source_url'].endswith('241300000789'))
    def test_irregular_course_is_skipped(self):
        sample='2026年度 科目名 イベント 担当教員 A 対象学年 1 クラス 1 講義室 Ｃ４０１ 開講学期 春学期 開講時期 春学期 曜日・時限 集中 単位区分 選択'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'123456.html';path.write_text(sample,encoding='utf-8')
            with self.assertRaises(module.SkippedRecord): module.parse_one(path)
    def test_missing_room_is_skipped(self):
        sample='2026年度 科目名 イベント 担当教員 A 対象学年 1 クラス 1 講義室 別途指示 開講学期 秋学期 開講時期 秋学期 曜日・時限 火4 単位区分 選択'
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'123456.html';path.write_text(sample,encoding='utf-8')
            with self.assertRaises(module.SkippedRecord): module.parse_one(path)

if __name__=='__main__': unittest.main()
