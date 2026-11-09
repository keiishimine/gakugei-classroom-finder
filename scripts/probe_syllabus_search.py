#!/usr/bin/env python3
"""Read the public search form ONCE and output a sanitized schema report.

Does not submit searches or collect course lists. Helps identify the actual
form/API rather than guessing undocumented endpoints and dumping lots of pages.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

SEARCH_URL = 'https://tgusyl.u-gakugei.ac.jp/ext_syllabus/syllabusSearchDirect.do?nologin=on'
USER_AGENT = 'GakugeiClassroomFinderResearch/0.2 (single public form metadata inspection)'


class FormStructure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self.inputs: list[dict] = []
        self.selects: list[dict] = []
        self.buttons: list[dict] = []
        self.scripts: list[str] = []
        self.frames: list[str] = []
        self._select: dict | None = None
        self._option: dict | None = None
        self._is_button = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'form':
            self.forms.append({'action': d.get('action'), 'method': d.get('method')})
        elif tag == 'input':
            self.inputs.append({'name': d.get('name'), 'type': d.get('type'),
                                'id': d.get('id'), 'alt': d.get('alt'),
                                'title': d.get('title')})
        elif tag == 'select':
            self._select = {'name': d.get('name'), 'id': d.get('id'), 'options': []}
            self.selects.append(self._select)
        elif tag == 'option' and self._select is not None:
            self._option = {'value': d.get('value'), 'label': ''}
            self._select['options'].append(self._option)
        elif tag == 'button':
            self._is_button = True
            self.buttons.append({'id': d.get('id'), 'name': d.get('name'), 'text': ''})
        elif tag == 'script' and d.get('src'):
            self.scripts.append(d['src'])
        elif tag == 'iframe' and d.get('src'):
            self.frames.append(d['src'])

    def handle_data(self, data):
        if self._option is not None:
            self._option['label'] += data
        if self._is_button and self.buttons:
            self.buttons[-1]['text'] += data

    def handle_endtag(self, tag):
        if tag == 'option':
            self._option = None
        elif tag == 'select':
            self._select = None
        elif tag == 'button':
            self._is_button = False

    def report(self) -> dict:
        # Only the form metadata; hidden input VALUES and cookies are not captured.
        for select in self.selects:
            for option in select['options']:
                option['label'] = ' '.join(option['label'].split())[:120]
            select['options'] = select['options'][:100]
        return {
            'search_url': SEARCH_URL, 'forms': self.forms[:10],
            'inputs': self.inputs[:150], 'selects': self.selects[:30],
            'buttons': self.buttons[:50], 'scripts': self.scripts[:50],
            'frames': self.frames[:30]
        }


def read_search_form() -> str:
    robots = RobotFileParser()
    robots.set_url('https://tgusyl.u-gakugei.ac.jp/robots.txt')
    robots.read()
    if not robots.can_fetch(USER_AGENT, SEARCH_URL):
        raise RuntimeError('robots.txtを確認できないか、ページが取得禁止です。')
    request = Request(SEARCH_URL, headers={
        'User-Agent': USER_AGENT, 'Accept': 'text/html'
    })
    with urlopen(request, timeout=20) as r:
        p = urlparse(r.geturl())
        if p.scheme != 'https' or p.netloc != 'tgusyl.u-gakugei.ac.jp':
            raise RuntimeError('想定外のリダイレクトです')
        if r.headers.get_content_type() != 'text/html':
            raise RuntimeError('HTMLでない応答です')
        raw = r.read(700_001)
        if len(raw) > 700_000:
            raise RuntimeError('取得ページが大きすぎます')
        charset = r.headers.get_content_charset()
    for encoding in ([charset] if charset else []) + ['utf-8', 'cp932', 'shift_jis']:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    raise RuntimeError('文字コードの判定に失敗しました')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--permission-confirmed', action='store_true')
    p.add_argument('--out', type=Path, default=Path('diagnostics/search_form.json'))
    args = p.parse_args(argv)
    if not args.permission_confirmed:
        print('利用条件確認前は実行できません', file=sys.stderr)
        return 2
    try:
        html = read_search_form()
        parser = FormStructure()
        parser.feed(html)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(parser.report(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'フォーム構造を出力しました: {args.out}（検索の送信・科目の一括取得は未実施）')
        return 0
    except (RuntimeError, OSError, TimeoutError) as exc:
        print(f'フォーム確認に失敗: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
