#!/usr/bin/env python3
"""Convert user-saved public Tokyo Gakugei syllabus HTML/text into classroom CSV.

This OFFLINE importer does not send requests to the university or discover pages.
It intentionally skips any course with ambiguous term, day, period or room.

Examples:
  python3 scripts/import_saved_syllabus.py saved_syllabus/*.html
  python3 scripts/import_saved_syllabus.py 241300000789.html --dry-run
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unicodedata

FIELDNAMES = [
    'course_id','course_name','term','weekday','period_start','period_end',
    'room_id','schedule_type','source_url','last_verified','teacher'
]
ROOM_FIELDS = ['room_id','building','floor','room_type']
WEEKDAYS = {'月':'mon', '火':'tue', '水':'wed', '木':'thu', '金':'fri'}
BASE = 'https://tgusyl.u-gakugei.ac.jp/ext_syllabus/referenceDirect.do?formatCD=1&nologin=on&subjectID='

class TextFromHTML(HTMLParser):
    """Read visible HTML text while ignoring scripts and styles."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        elif tag in ('td', 'th', 'tr', 'p', 'div', 'br', 'h1', 'h2'):
            self.chunks.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        elif tag in ('td', 'th', 'tr', 'p', 'div', 'br'):
            self.chunks.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.chunks.append(data)

class SkippedRecord(ValueError):
    pass

def normalize(raw: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', raw)).strip()

def field(t: str, start: str, end: str) -> str:
    # Search the first occurrence between known neighboring official labels.
    m = re.search(re.escape(start) + r'\s*(.*?)\s*' + re.escape(end), t, flags=re.S)
    return m.group(1).strip() if m else ''

def decode_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ('utf-8-sig', 'cp932', 'shift_jis'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise SkippedRecord('文字コードを判定できません（UTF-8/Shift_JIS対応）')

def parse_one(path: Path, *, today: str | None = None) -> dict:
    raw = decode_file(path)
    if '<html' in raw.lower() or '<table' in raw.lower():
        parser = TextFromHTML(); parser.feed(raw)
        content = ' '.join(parser.chunks)
    else:
        content = raw
    t = normalize(content)
    if not re.search(r'2026\s*年度', t):
        raise SkippedRecord('2026年度のシラバスだと確認できません')
    name = field(t, '科目名', '担当教員')
    teacher = field(t, '担当教員', '対象学年')
    room_raw = field(t, '講義室', '開講学期')
    term_raw = field(t, '開講学期', '開講時期')
    time_raw = field(t, '曜日・時限', '単位区分')
    if not name:
        raise SkippedRecord('科目名を読み取れません')
    if ('春学期' in term_raw) == ('秋学期' in term_raw):
        raise SkippedRecord(f'学期が曖昧です: {term_raw[:35]}')
    term = 'spring' if '春学期' in term_raw else 'fall'
    # Explicitly reject any multi-slot/irregular course rather than guessing.
    m = re.fullmatch(r'([月火水木金])\s*([1-6])', time_raw.replace(' ', ''))
    if not m:
        raise SkippedRecord(f'曜日・時限が単純な週1コマではありません: {time_raw[:35]}')
    d, period = m.groups()
    r = re.fullmatch(r'\s*([NCSW])\s*(\d{3})\s*', room_raw, flags=re.I)
    if not r:
        raise SkippedRecord(f'教室が特定できません: {room_raw[:35]}')
    room = (r.group(1) + r.group(2)).upper()
    id_match = re.search(r'subjectID=(\d{6,18})', raw, flags=re.I)
    if not id_match:
        id_match = re.fullmatch(r'(\d{6,18})', path.stem)
    code = id_match.group(1) if id_match else f'local-{sha256((name+teacher+term+d+period+room).encode()).hexdigest()[:16]}'
    source_url = BASE + code if code.isdecimal() else ''
    return {
        'course_id':code, 'course_name':name, 'term':term, 'weekday':WEEKDAYS[d],
        'period_start':period,'period_end':period,'room_id':room,'schedule_type':'weekly',
        'source_url':source_url,'last_verified':today or date.today().isoformat(),'teacher':teacher
    }

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open('r', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, fields: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(rows)

def main(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', type=Path, help='保存済みの2026年度シラバスHTML/TXT')
    ap.add_argument('--out-dir', type=Path, default=Path('data'), help='CSV保存先（既存CSVに追記・重複排除）')
    ap.add_argument('--dry-run', action='store_true', help='保存しないで変換結果のみ確認')
    args=ap.parse_args(argv)
    courses_out = args.out_dir/'verified_2026_classes.csv'
    rooms_out = args.out_dir/'verified_2026_rooms.csv'
    items = {r['course_id']:r for r in read_csv(courses_out)}
    rooms = {r['room_id']:r for r in read_csv(rooms_out)}
    ok=0; skipped=0
    for path in args.files:
        try:
            if not path.is_file():
                raise SkippedRecord('ファイルが存在しません')
            record=parse_one(path)
            # Local IDs may collide when identical class names/times exist. Do not overwrite.
            if record['course_id'].startswith('local-') and record['course_id'] in items:
                if items[record['course_id']]['course_name'] != record['course_name']:
                    raise SkippedRecord('同一キーの衝突を検出しました')
            items[record['course_id']]=record
            room=record['room_id']
            rooms.setdefault(room, {'room_id':room,'building':room[0],'floor':room[1], 'room_type':'公開シラバス掲載'})
            ok+=1
            print(f'OK   {path.name}: {record["term"]} {record["weekday"]}{record["period_start"]} {room} {record["course_name"]}')
        except (SkippedRecord, OSError) as exc:
            skipped+=1
            print(f'SKIP {path.name}: {exc}', file=sys.stderr)
    if not args.dry_run and ok:
        write_csv(courses_out, FIELDNAMES, [items[k] for k in sorted(items)])
        write_csv(rooms_out, ROOM_FIELDS, [rooms[k] for k in sorted(rooms)])
    print(f'取り込み{ok}件、要確認・スキップ{skipped}件。累計{len(items)}件、教室{len(rooms)}室。' + ('（保存なし）' if args.dry_run else ''))
    return 0 if skipped==0 and ok>0 else 1

if __name__=='__main__':
    raise SystemExit(main())
