#!/usr/bin/env python3
"""Offline regression tests for period scope, source changes and safe application."""
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import sync_blog as sync
from content_store import load_posts, save_post, write_json


def source_html(post_id='123', title='번역 &lt;책&gt;', body='확인한 본문', stamp='2026. 8. 19. 14:12'):
    return f'''<meta property="og:url" content="https://blog.naver.com/dadablog888/{post_id}"><meta property="og:title" content="{title}">
    <div id="unrelated"><div class="se-main-container">다른 글</div></div>
    <div id="post-view{post_id}"><div class="blog2_series"><a>통번역 이야기</a></div><span class="se_publishDate pcol2">{stamp}</span><div class="se-main-container"><div><p>{body}</p></div></div></div>'''


def row(post_id, when):
    return {'logNo': post_id, 'addDate': when}


def introduction(source, slug='123'):
    return {**{k: source[k] for k in ['id', 'sourceUrl', 'originalTitle', 'publishedAt', 'originalCategory', 'sourceHash']}, 'slug': slug, 'title': '검토한 소개', 'topic': 'translation', 'description': '독립적인 설명', 'summary': '확인한 요약', 'sections': [{'heading': '확인 내용', 'text': '원문을 읽고 쓴 소개'}], 'takeaways': [], 'keywords': ['번역'], 'related': [], 'introUpdatedOn': '2026-10-21'}


class SyncTests(unittest.TestCase):
    def test_explicit_period_and_leap_day(self):
        first, last = sync.period_bounds('2024-02')
        self.assertEqual(str(last), '2024-02-29')
        self.assertEqual(sync.period_bounds('2026-10-10')[0], sync.period_bounds('2026-10-10')[1])
        for invalid in ['오늘', '2026/08', '2026-8', '2026-13', '2026-02-30', '../2026-08']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                sync.period_bounds(invalid)

    def test_source_scope_angle_brackets_and_change_hash(self):
        source = sync.parse_source(source_html(), '123', 'dadablog888')
        self.assertEqual(source['originalTitle'], '번역 <책>')
        self.assertEqual(source['bodyText'], '확인한 본문')
        same = sync.parse_source(source_html(body='  확인한   본문  '), '123', 'dadablog888')
        self.assertEqual(source['sourceHash'], same['sourceHash'])
        edited = sync.parse_source(source_html(body='수정한 본문'), '123', 'dadablog888')
        self.assertNotEqual(source['sourceHash'], edited['sourceHash'])
        with self.assertRaises(ValueError):
            sync.parse_source(source_html(), '456', 'dadablog888')

    def test_relative_date_uses_verified_rss_timestamp(self):
        with self.assertRaises(ValueError):
            sync.parse_source(source_html(stamp='2시간 전'), '123', 'dadablog888')
        source = sync.parse_source(source_html(stamp='2시간 전'), '123', 'dadablog888', '2026-08-19T14:12:33+09:00')
        absolute = sync.parse_source(source_html(), '123', 'dadablog888')
        self.assertEqual(source['sourceHash'], absolute['sourceHash'])

    def test_legacy_editors_keep_only_target_body_and_exact_metadata(self):
        for body in [
            '<div id="post-view123" class="post-view pcol2"><div class="view"><p>첫 문장<br>두 번째 문장</p></div></div>',
            '<div id="post-view123"><div class="se_component_wrap se_documentTitle">제목 도구</div><div class="se_component_wrap sect_dsc __se_component_area"><div><p>첫 문장<br>두 번째 문장</p></div></div><div>출처 도구</div></div>',
        ]:
            html = '''<meta property="og:url" content="https://blog.naver.com/dadablog888/123"><meta property="og:title" content="옛 글">
            <span class="date pcol2">2023. 11. 17.</span>
            <span class="cate pcol2"><img><a>생각</a></span>
            <p class="date fil5 pcol2 _postAddDate">2015. 2. 12. 15:16</p>
            <div id="post-view999" class="post-view"><p>다른 글</p></div>'''+body+'<div>댓글 메뉴</div>'
            with self.subTest(body=body):
                result = sync.parse_source(html, '123', 'dadablog888')
                self.assertEqual(result['bodyText'], '첫 문장\n두 번째 문장')
                self.assertEqual(result['publishedAt'], '2015-02-12T15:16+09:00')
                self.assertEqual(result['originalCategory'], '생각')

    def test_period_boundary_ignores_unrelated_relative_posts(self):
        listing = {'resultCode': 'S', 'totalCount': '3', 'postList': [row('900', '2시간 전'), row('123', '2026. 8. 19.'), row('100', '2026. 7. 31.')]}
        with patch.object(sync, 'get', return_value=json.dumps(listing)):
            ids, coverage = sync.discover('dadablog888', *sync.period_bounds('2026-08'), [], datetime(2026, 10, 21, tzinfo=sync.KST))
        self.assertEqual(ids, ['123'])
        self.assertTrue(coverage['boundaryReached'])

    def test_incomplete_listing_is_not_empty_success(self):
        with patch.object(sync, 'get', return_value=json.dumps({'resultCode': 'S', 'totalCount': '811', 'postList': []})):
            with self.assertRaises(ValueError):
                sync.discover('dadablog888', *sync.period_bounds('2026-08'), [], datetime(2026, 10, 21, tzinfo=sync.KST))

    def test_changed_then_unchanged_does_not_rewrite_intro(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json(root / 'content/site.json', {'blogUrl': 'https://blog.naver.com/dadablog888', 'feedUrl': 'https://rss.blog.naver.com/dadablog888.xml', 'topics': [{'slug': 'translation'}]})
            source = sync.parse_source(source_html(body='지난 본문'), '123', 'dadablog888')
            old = introduction(source, slug='keep-permanent-url')
            save_post(root, old)
            listing = {'resultCode': 'S', 'totalCount': '2', 'postList': [row('123', '2026. 8. 19.'), row('100', '2026. 7. 31.')]}
            def fetch(url):
                return json.dumps(listing) if 'PostTitleListAsync' in url else source_html(body='새로 수정된 본문')
            with patch.object(sync, 'ROOT', root), patch.object(sync, 'get', side_effect=fetch):
                report = sync.collect('2026-08')
                self.assertEqual(report['posts'][0]['status'], 'changed')
                with self.assertRaises(ValueError):
                    sync.apply('2026-08')
                self.assertEqual(load_posts(root)[0], old)
                fresh = json.loads((root / report['posts'][0]['sourceFile']).read_text())
                reviewed = introduction(fresh, slug='keep-permanent-url')
                write_json(root / report['posts'][0]['reviewFile'], reviewed)
                sync.apply('2026-08')
                target = next((root / 'content/posts').rglob('123.json'))
                before, modified = target.read_bytes(), target.stat().st_mtime_ns
                report = sync.collect('2026-08')
                self.assertEqual(report['posts'][0]['status'], 'unchanged')
                sync.apply('2026-08')
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(target.stat().st_mtime_ns, modified)
                self.assertEqual(load_posts(root)[0]['slug'], 'keep-permanent-url')


if __name__ == '__main__':
    unittest.main()
