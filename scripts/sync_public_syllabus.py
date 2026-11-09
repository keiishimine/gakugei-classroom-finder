#!/usr/bin/env python3
"""Safely refresh *known* public 2026 syllabus URLs into the static website.

This deliberately does not claim full campus timetable coverage.
- Explicit opt-in; robots.txt check and low-rate requests are done by fetch_approved_syllabus_urls.
- All or nothing: failed fetches or changed/unparseable pages NEVER erase existing CSV.
- Update published metadata and maintain a traceable source URL per course.
- No login credentials, hidden APIs, sequential subject-ID guessing, or pagination scans.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory, NamedTemporaryFile

from fetch_approved_syllabus_urls import main as download_main, validate_url
from import_saved_syllabus import (
    FIELDNAMES, ROOM_FIELDS, SkippedRecord, parse_one, read_csv
)

ROOT = Path(__file__).resolve().parents[1]


def read_manifest(path: Path) -> dict[str, str]:
    lines = [v.strip() for v in path.read_text(encoding='utf-8-sig').splitlines()
             if v.strip() and not v.lstrip().startswith('#')]
    if not 1 <= len(lines) <= 25:
        raise ValueError('既知シラバスURLは1〜25件に限定してください')
    result = {}
    for url in lines:
        valid, course_id = validate_url(url)
        if course_id in result:
            raise ValueError(f'重複しているsubjectID: {course_id}')
        result[course_id] = valid
    return result


def build_updated_rows(
    html_dir: Path, manifest: dict[str, str], existing_courses: list[dict],
    existing_rooms: list[dict], verified_date: str
) -> tuple[list[dict], list[dict]]:
    """Return the new snapshot; if ANY known URL fails parsing, raise and write nothing."""
    courses = {r['course_id']: dict(r) for r in existing_courses}
    rooms = {r['room_id']: dict(r) for r in existing_rooms}
    for course_id, url in manifest.items():
        path = html_dir / f'{course_id}.html'
        if not path.is_file():
            raise ValueError(f'{course_id}: 保存ファイルがありません。更新を中止します')
        try:
            row = parse_one(path, today=verified_date)
        except (SkippedRecord, UnicodeError, OSError) as exc:
            raise ValueError(f'{course_id}: 解析不可のため全体を更新しません: {exc}') from exc
        if row['course_id'] != course_id or row['source_url'] != url:
            # URL query order can differ, but our canonical manifest has fixed order.
            raise ValueError(f'{course_id}: 取得元と記録IDに不一致があります')
        courses[course_id] = row
        room_id = row['room_id']
        rooms.setdefault(room_id, {
            'room_id': room_id, 'building': room_id[0],
            'floor': room_id[1], 'room_type': '公開シラバス掲載'
        })
    return (
        [courses[k] for k in sorted(courses)],
        [rooms[k] for k in sorted(rooms)]
    )


def atomic_csv(path: Path, columns: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    # csv.writer supports quoting course names containing commas/newlines.
    with NamedTemporaryFile('w', newline='', encoding='utf-8-sig', dir=path.parent,
                            suffix='.tmp', delete=False) as out:
        tmp = Path(out.name)
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                            suffix='.tmp', delete=False) as out:
        tmp = Path(out.name)
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')
    os.replace(tmp, path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT/'data/known_syllabus_urls.txt')
    p.add_argument('--data-dir', type=Path, default=ROOT/'data')
    p.add_argument('--permission-confirmed', action='store_true',
                   help='大学側の機械的取得・利用条件を確認したときのみ実行')
    p.add_argument('--delay', type=float, default=3.0,
                   help='アクセス間隔（最低3秒）')
    p.add_argument('--dry-run', action='store_true', help='取得・解析のみ、CSVは保存しない')
    args = p.parse_args(argv)
    if not args.permission_confirmed:
        print('未実行：取得元の利用条件を確認し、明示的な許可フラグが必要です。', file=sys.stderr)
        return 2
    try:
        manifest = read_manifest(args.manifest)
        with TemporaryDirectory(prefix='gakugei_syllabus_') as directory:
            downloads = Path(directory)
            code = download_main([
                '--manifest', str(args.manifest), '--output', str(downloads),
                '--permission-confirmed', '--delay', str(args.delay)
            ])
            if code != 0:
                raise ValueError('取得またはrobots.txt確認に失敗。既存データを保持します')
            now = datetime.now(timezone.utc)
            courses, rooms = build_updated_rows(
                downloads, manifest,
                read_csv(args.data_dir/'verified_2026_classes.csv'),
                read_csv(args.data_dir/'verified_2026_rooms.csv'),
                now.date().isoformat()
            )
            if args.dry_run:
                print(f'DRY RUN OK: {len(manifest)}件を直接照合。変更は保存しません')
                return 0
            atomic_csv(args.data_dir/'verified_2026_classes.csv', FIELDNAMES, courses)
            atomic_csv(args.data_dir/'verified_2026_rooms.csv', ROOM_FIELDS, rooms)
            atomic_json(args.data_dir/'sync_status.json', {
                'status': 'ok',
                'mode': 'known_urls_only',
                'updated_at': now.isoformat(timespec='seconds'),
                'checked_known_urls': len(manifest),
                'published_courses': len(courses),
                'published_rooms': len(rooms),
                'coverage': 'partial',
                'note': '既知の公開URLのみ更新。全教室・全授業の網羅性を示すものではありません。'
            })
            print(f'SYNC OK: {len(manifest)}件を再確認、公開データ{len(courses)}件／教室{len(rooms)}室。空き判定は要確認のままです。')
            return 0
    except (ValueError, OSError) as exc:
        print(f'SYNC FAILED, existing data preserved: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
