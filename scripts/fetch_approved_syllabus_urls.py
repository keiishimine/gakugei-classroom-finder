#!/usr/bin/env python3
"""Optionally download a SMALL explicit list of permitted public syllabus pages.

This script is intentionally OFF by default. Before running, obtain university
approval for automated retrieval and publication of course metadata. It will
never discover IDs, login, bypass access controls, or scrape search-result pages.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

USER_AGENT = 'GakugeiClassroomFinderResearch/0.2 (small opt-in academic data import)'
ALLOWED_HOST = 'tgusyl.u-gakugei.ac.jp'
ALLOWED_PATH = '/ext_syllabus/referenceDirect.do'


def validate_url(url: str) -> tuple[str, str]:
    p = urlparse(url.strip())
    if p.scheme != 'https' or p.hostname != ALLOWED_HOST or p.path != ALLOWED_PATH or p.username or p.password or p.fragment:
        raise ValueError(f'認証なしの公式個別シラバスURL以外は使用できません: {url}')
    params = parse_qs(p.query)
    ids = params.get('subjectID', [])
    if len(ids) != 1 or not re.fullmatch(r'\d{6,18}', ids[0]) or params.get('nologin') != ['on'] or params.get('formatCD') != ['1']:
        raise ValueError(f'URLパラメータが想定と異なります: {url}')
    if set(params) != {'subjectID', 'nologin', 'formatCD'}:
        raise ValueError(f'想定外パラメータがあります: {url}')
    return url, ids[0]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=Path('data/known_syllabus_urls.txt'))
    p.add_argument('--output', type=Path, default=Path('saved_syllabus'))
    p.add_argument('--permission-confirmed', action='store_true', help='大学側の自動取得・再利用条件を確認済みの場合のみ実行')
    p.add_argument('--delay', type=float, default=3.0, help='取得間隔（最低3秒）')
    args = p.parse_args(argv)
    if not args.permission_confirmed:
        print('実行中止：大学側の自動取得・情報再利用の条件を確認してから --permission-confirmed を付けてください。', file=sys.stderr)
        return 2
    if args.delay < 3:
        print('取得間隔は最低3秒にしてください。', file=sys.stderr)
        return 2
    lines = [x.strip() for x in args.manifest.read_text(encoding='utf-8-sig').splitlines() if x.strip() and not x.lstrip().startswith('#')]
    if len(lines) > 25 or not lines:
        print('明示したURLは1～25件の小規模なリストに限定してください。', file=sys.stderr)
        return 2
    validated = [validate_url(x) for x in lines]
    if len({identifier for _,identifier in validated}) != len(validated):
        print('重複するsubjectIDが含まれます。', file=sys.stderr)
        return 2
    robots_url = f'https://{ALLOWED_HOST}/robots.txt'
    robots = RobotFileParser()
    try:
        robots.set_url(robots_url)
        robots.read()
        if robots.disallow_all or not robots.allow_all and not robots.can_fetch(USER_AGENT, validated[0][0]):
            raise ValueError('robots.txt上で許可を確認できませんでした')
    except Exception as exc:
        print(f'実行中止：robots.txtを確認できません: {exc}', file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    failures = 0
    for index, (url, identifier) in enumerate(validated):
        if index: time.sleep(args.delay)
        if not robots.can_fetch(USER_AGENT, url):
            print(f'SKIP robots.txt disallows: {identifier}', file=sys.stderr); failures += 1; continue
        try:
            req = Request(url, headers={'User-Agent':USER_AGENT, 'Accept':'text/html'})
            with urlopen(req, timeout=20) as response:
                if urlparse(response.geturl()).hostname != ALLOWED_HOST:
                    raise ValueError('公式ドメイン以外へのリダイレクトを検出しました')
                typ = response.headers.get_content_type()
                if typ != 'text/html':
                    raise ValueError(f'想定外Content-Type: {typ}')
                content = response.read(1_000_001)
                if len(content) > 1_000_000:
                    raise ValueError('ページが1MBを超えています')
                (args.output/f'{identifier}.html').write_bytes(content)
                print(f'OK   {identifier}: {len(content)} bytes')
        except Exception as exc:
            failures += 1
            print(f'SKIP {identifier}: {exc}', file=sys.stderr)
    return int(failures > 0)

if __name__ == '__main__':
    raise SystemExit(main())
