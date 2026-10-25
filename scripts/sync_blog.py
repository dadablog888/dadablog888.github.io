#!/usr/bin/env python3
"""Fetch an explicit month/day, stage changed sources, apply agent-reviewed JSON."""
import argparse
import calendar
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from content_store import load_posts, save_post, write_json

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))


def period_bounds(value):
    if not re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?', value):
        raise ValueError('Use an explicit YYYY-MM or YYYY-MM-DD period')
    if len(value) == 7:
        year, month = map(int, value.split('-'))
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    day = date.fromisoformat(value)
    return day, day


def get(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                return response.read().decode('utf-8')
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def plain(value):
    return ' '.join(unescape(re.sub('<[^>]*>', ' ', value)).replace('\u200b', '').split())


def text_value(value):
    return ' '.join(unescape(value).replace('\u200b', '').split())


class SourceParser(HTMLParser):
    def __init__(self, post_id):
        super().__init__(convert_charrefs=True)
        self.post_id = post_id
        self.depth = 0
        self.scope_depth = None
        self.body_depth = None
        self.parts = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.meta[attrs.get('property', attrs.get('name', ''))] = attrs.get('content', '')
        if tag == 'div':
            self.depth += 1
            classes = set(attrs.get('class', '').split())
            if attrs.get('id') == 'post-view' + self.post_id:
                self.scope_depth = self.depth
                if 'post-view' in classes:  # SmartEditor 2: this node is the body.
                    self.body_depth = self.depth
            if self.scope_depth and ('se-main-container' in classes or
                                     {'se_component_wrap', '__se_component_area'} <= classes):
                self.body_depth = self.depth
        if self.body_depth and tag in ['p', 'br']:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.depth == self.body_depth:
                self.body_depth = None
            if self.depth == self.scope_depth:
                self.scope_depth = None
            self.depth -= 1

    def handle_data(self, value):
        if self.body_depth:
            self.parts.append(value)


def parse_source(html, post_id, blog_id, fallback_published=None):
    parser = SourceParser(post_id)
    parser.feed(html)
    source_url = f'https://blog.naver.com/{blog_id}/{post_id}'
    if parser.meta.get('og:url') != source_url:
        raise ValueError('Unexpected source URL or unavailable/private post')
    lines = [text_value(line) for line in ''.join(parser.parts).splitlines()]
    body = '\n'.join(line for line in lines if line)
    if not body:
        raise ValueError('Readable post text was not found; keep existing introduction')
    stamp_match = re.search(r'class="se_publishDate[^>]*>([^<]+)', html)
    if not stamp_match:
        stamp_match = re.search(r'class="[^"]*\b_postAddDate\b[^"]*"[^>]*>([^<]+)', html)
    if not stamp_match:
        raise ValueError('Exact publication date was not found')
    numbers = list(map(int, re.findall(r'\d+', stamp_match.group(1))))
    if len(numbers) == 5:
        stamp = datetime(*numbers, tzinfo=KST).isoformat(timespec='minutes')
    elif fallback_published:
        stamp = fallback_published
    else:
        raise ValueError('Exact date unavailable in HTML or RSS; keep previous data')
    category = re.search(r'class="blog2_series"[^>]*>\s*<a[^>]*>(.*?)</a>', html, re.S)
    if not category:
        category = re.search(r'<span class="cate pcol2">(?:(?!</span>).)*?<a[^>]*>(.*?)</a>', html, re.S)
    source = {'id': post_id, 'sourceUrl': source_url, 'originalTitle': text_value(parser.meta['og:title']), 'publishedAt': stamp, 'publishedPrecision': 'minute', 'originalCategory': plain(category.group(1)) if category else '', 'bodyText': body}
    payload = {k: v for k, v in source.items() if k != 'publishedPrecision'}
    payload['publishedAt'] = datetime.fromisoformat(stamp).isoformat(timespec='minutes')
    source['sourceHash'] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return source


def list_date(value, now):
    match = re.fullmatch(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.', value.strip())
    if match:
        return date(*map(int, match.groups()))
    if value in ['방금 전', '오늘'] or re.fullmatch(r'\d+(?:초|분|시간) 전', value):
        # A relative date can cross midnight; fetch its exact date before filtering.
        return None
    raise ValueError('Unknown listing date: ' + value)


def discover(blog_id, start, end, known, now, max_pages=200):
    candidates = set()
    seen = set()
    oldest_previous = None
    count = None
    for page in range(1, max_pages + 1):
        url = 'https://blog.naver.com/PostTitleListAsync.naver?' + urlencode({'blogId': blog_id, 'viewdate': '', 'currentPage': page, 'categoryNo': 0, 'parentCategoryNo': 0, 'countPerPage': 30})
        # Naver's pagingHtml uses JavaScript-style \\' escapes in its JSON response.
        result = json.loads(get(url).replace("\\'", "'"), strict=False)
        if result.get('resultCode') != 'S':
            raise ValueError('Public listing request failed')
        rows = result.get('postList', [])
        total = int(result['totalCount'])
        if count is not None and count != total:
            raise ValueError('Listing changed during scan; rerun before claiming completeness')
        count = total
        if not rows:
            if len(seen) < count:
                raise ValueError('Listing ended before reported total; completeness unknown')
            break
        ids = [row['logNo'] for row in rows]
        if set(ids).issubset(seen):
            raise ValueError('Listing repeated a page; completeness unknown')
        dated = []
        for row in rows:
            post_id = row['logNo']
            if not re.fullmatch(r'\d+', post_id):
                raise ValueError('Invalid post ID')
            when = list_date(row['addDate'], now)
            if (when is None and end >= now.date() - timedelta(days=1)) or (when and start <= when <= end):
                candidates.add(post_id)
            if when:
                dated.append(when)
        if dated != sorted(dated, reverse=True) or (oldest_previous and dated and dated[0] > oldest_previous):
            raise ValueError('Listing order changed; do not claim a complete period')
        seen.update(ids)
        if dated:
            oldest_previous = dated[-1]
            if oldest_previous < start:
                break
        if len(seen) >= count:
            break
    else:
        raise ValueError('Listing scan limit reached; completeness unknown')
    # Recheck saved posts too: a moved date or disappearance must not cause silent deletion.
    candidates.update(p['id'] for p in known if start <= datetime.fromisoformat(p['publishedAt']).date() <= end)
    return sorted(candidates), {'pagesScanned': page, 'reportedPublicPosts': count, 'listingRowsSeen': len(seen), 'boundaryReached': True}


def collect(period):
    start, end = period_bounds(period)
    site = json.loads((ROOT / 'content/site.json').read_text())
    blog_id = site['blogUrl'].rstrip('/').rsplit('/', 1)[1]
    now = datetime.now(KST)
    if start > now.date():
        raise ValueError('The requested period has not started yet')
    rss_dates = {}
    if end >= now.date() - timedelta(days=1):
        feed = ET.fromstring(get(site['feedUrl']))
        for item in feed.findall('./channel/item'):
            rss_id = (item.findtext('guid') or '').rstrip('/').rsplit('/', 1)[-1]
            if item.findtext('pubDate'):
                rss_dates[rss_id] = parsedate_to_datetime(item.findtext('pubDate')).astimezone(KST).isoformat()
    known = {p['id']: p for p in load_posts(ROOT)}
    folder = ROOT / '.cache/blog-sync' / period
    report = {'period': period, 'checkedAt': now.isoformat(timespec='seconds'), 'status': 'collected', 'posts': [], 'errors': []}
    try:
        candidates, coverage = discover(blog_id, start, end, list(known.values()), now)
        report['coverage'] = coverage
    except Exception as error:
        report['status'] = 'incomplete'
        report['errors'].append({'stage': 'listing', 'message': str(error)})
        write_json(folder / 'manifest.json', report)
        raise
    for post_id in candidates:
        try:
            url = 'https://blog.naver.com/PostView.naver?' + urlencode({'blogId': blog_id, 'logNo': post_id, 'redirect': 'Dlog', 'widgetTypeCall': 'true', 'directAccess': 'false'})
            source = parse_source(get(url), post_id, blog_id, rss_dates.get(post_id))
            previous = known.get(post_id)
            in_period = start <= datetime.fromisoformat(source['publishedAt']).date() <= end
            previously_in_period = previous and start <= datetime.fromisoformat(previous['publishedAt']).date() <= end
            if not in_period and not previously_in_period:
                continue
            source['checkedAt'] = report['checkedAt']
            write_json(folder / 'sources' / (post_id + '.json'), source)
            state = 'unchanged' if previous and previous.get('sourceHash') == source['sourceHash'] else 'changed' if previous else 'new'
            report['posts'].append({'id': post_id, 'title': source['originalTitle'], 'publishedAt': source['publishedAt'], 'sourceHash': source['sourceHash'], 'status': state, 'inRequestedPeriod': in_period, 'sourceFile': str((folder / 'sources' / (post_id + '.json')).relative_to(ROOT)), 'reviewFile': str((folder / 'reviewed' / (post_id + '.json')).relative_to(ROOT))})
        except Exception as error:
            report['errors'].append({'id': post_id, 'message': str(error)})
    if report['errors']:
        report['status'] = 'incomplete'
    write_json(folder / 'manifest.json', report)
    print(json.dumps({'period': period, 'manifest': str(folder / 'manifest.json'), 'coverage': report['coverage'], 'counts': {state: sum(p['status'] == state for p in report['posts']) for state in ['new', 'changed', 'unchanged']}, 'errors': report['errors']}, ensure_ascii=False, indent=2))
    return report


def apply(period):
    period_bounds(period)
    folder = ROOT / '.cache/blog-sync' / period
    report = json.loads((folder / 'manifest.json').read_text())
    if report['status'] == 'incomplete' or report['errors']:
        raise ValueError('Collection incomplete; keep existing data and resolve errors before apply')
    known = {p['id']: p for p in load_posts(ROOT)}
    pending = []
    for row in report['posts']:
        if row['status'] == 'unchanged':
            if known.get(row['id'], {}).get('sourceHash') != row['sourceHash']:
                raise ValueError('Saved source changed after collect; collect again')
            continue
        source = json.loads((ROOT / row['sourceFile']).read_text())
        reviewed = ROOT / row['reviewFile']
        if not reviewed.is_file():
            raise ValueError('Introduction review required: ' + str(reviewed))
        post = json.loads(reviewed.read_text())
        if post.get('id') != row['id'] or post.get('sourceHash') != row['sourceHash']:
            raise ValueError('Reviewed content does not match the fetched source')
        for key in ['title', 'description', 'summary', 'slug', 'topic', 'publishedAt', 'introUpdatedOn', 'sections', 'takeaways', 'keywords', 'related']:
            if key not in post:
                raise ValueError('Missing introduction field: ' + key)
        date.fromisoformat(post['introUpdatedOn'])
        for key in ['originalTitle', 'originalCategory', 'sourceUrl']:
            if post.get(key) != source[key]:
                raise ValueError('Reviewed source field mismatch: ' + key)
        if not post.get('sections') or not post.get('summary') or not post.get('description'):
            raise ValueError('Reviewed introduction is incomplete')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', post.get('slug', '')):
            raise ValueError('Unsafe public slug')
        if post.get('topic') not in {t['slug'] for t in json.loads((ROOT / 'content/site.json').read_text())['topics']}:
            raise ValueError('Unknown topic')
        published = datetime.fromisoformat(post['publishedAt'])
        exact = datetime.fromisoformat(source['publishedAt'])
        if published.replace(second=0, microsecond=0) != exact.replace(second=0, microsecond=0):
            raise ValueError('Publication date mismatch')
        previous = known.get(row['id'])
        if previous and post['slug'] != previous['slug']:
            raise ValueError('Preserve the permanent URL of an existing post')
        pending.append(post)
    all_ids = set(known) | {p['id'] for p in pending}
    if any(set(p.get('related', [])) - all_ids for p in pending):
        raise ValueError('Unknown related post ID')
    # Validate the whole batch before writing any reviewed introduction.
    for post in pending:
        save_post(ROOT, post)
    ledger_path = ROOT / 'content/sync-state.json'
    ledger = json.loads(ledger_path.read_text()) if ledger_path.is_file() else {'periods': {}}
    ledger['periods'][period] = {'checkedAt': report['checkedAt'], 'coverage': report['coverage'], 'postIds': [p['id'] for p in report['posts'] if p['inRequestedPeriod']], 'new': sum(p['status'] == 'new' for p in report['posts']), 'changed': sum(p['status'] == 'changed' for p in report['posts']), 'unchanged': sum(p['status'] == 'unchanged' for p in report['posts']), 'status': 'complete'}
    write_json(ledger_path, ledger)
    # Full original text stays in ignored local cache; public records retain only provenance.
    public_report = {**ledger['periods'][period], 'period': period, 'posts': [{k: v for k, v in p.items() if k not in ['sourceFile', 'reviewFile']} for p in report['posts']]}
    write_json(ROOT / 'content/updates' / (period + '.json'), public_report)
    print(f'Applied {len(pending)} reviewed introductions for {period}; existing posts retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['collect', 'apply'])
    parser.add_argument('period', help='Explicit YYYY-MM or YYYY-MM-DD, in Asia/Seoul')
    args = parser.parse_args()
    try:
        if args.action == 'collect':
            report = collect(args.period)
            if report['errors']:
                sys.exit(1)
        else:
            apply(args.period)
    except Exception as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
