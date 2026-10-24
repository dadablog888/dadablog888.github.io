#!/usr/bin/env python3
"""Check the content/SEO contract and optionally crawl local HTTP responses."""
import argparse
import copy
import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import urlopen, Request
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from content_store import load_posts

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / 'content/site.json').read_text())
POSTS = load_posts(ROOT)
BASE = SITE['url']
PREFIX = urlsplit(BASE).path
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.links = []
        self.ids = set()
        self.h1_count = 0
        self.canonicals = []
        self.title = ''
        self.schemas = []
        self.in_title = False
        self.in_json = False
        self.json_text = ''
        self.html_lang = None
        self.images = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.html_lang = a.get('lang')
        if 'id' in a:
            require(a['id'] not in self.ids, 'Duplicate id: ' + a['id'])
            self.ids.add(a['id'])
        if tag == 'meta':
            self.meta[a.get('name', a.get('property', ''))] = a.get('content')
            require(a.get('http-equiv', '').lower() != 'refresh', 'Found automatic refresh')
        if tag == 'link' and a.get('rel') == 'canonical':
            self.canonicals.append(a.get('href'))
        if tag == 'a' or (tag == 'link' and a.get('rel') in ['stylesheet', 'icon']):
            self.links.append(a.get('href', ''))
        if tag == 'img':
            self.links.append(a.get('src', ''))
            self.images.append(a)
        if tag == 'h1':
            self.h1_count += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'script':
            require(a.get('type') == 'application/ld+json', 'Unexpected executable client-side script')
            self.in_json = a.get('type') == 'application/ld+json'
            self.json_text = ''

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'script' and self.in_json:
            try:
                self.schemas.append(json.loads(self.json_text))
            except ValueError as error:
                errors.append('Invalid JSON-LD: ' + str(error))
            self.in_json = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_json:
            self.json_text += data


def disk_path(url):
    path = unquote(urlsplit(url).path)
    if not path.startswith(PREFIX):
        return None
    target = ROOT / path[len(PREFIX):]
    return target / 'index.html' if path.endswith('/') else target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--http', help='Local origin, e.g. http://127.0.0.1:8000')
    parser.add_argument('--sources', action='store_true', help='Verify live original Naver post bodies')
    parser.add_argument('--growth', action='store_true', help='Test accumulation and pagination in an isolated temporary directory')
    args = parser.parse_args()
    root_home = ROOT / 'root-site/index.html'
    require(root_home.is_file(), 'Root Pages homepage copy is missing; run build.py')
    if root_home.is_file():
        require(root_home.read_bytes() == (ROOT / 'index.html').read_bytes(), 'Root Pages homepage copy is stale')
    require((ROOT / 'root-site/.nojekyll').is_file(), 'Root Pages .nojekyll is missing')
    files = [ROOT / 'index.html'] + sorted((ROOT / 'posts').rglob('index.html')) + sorted((ROOT / 'topics').rglob('index.html')) + sorted((ROOT / 'archive').rglob('index.html'))
    require(len(POSTS) >= 10, 'Expected at least the initial 10 source posts')
    require(len({p['id'] for p in POSTS}) == len(POSTS), 'Duplicate source id')
    require(len({p['slug'] for p in POSTS}) == len(POSTS), 'Duplicate post slug')
    require(len(list((ROOT / 'posts').glob('*/index.html'))) == len(POSTS), 'Every retained post needs a permanent introduction')
    documents = {}
    all_local_urls = set()
    titles = set()
    descriptions = set()
    indexed_urls = set()
    for file in files:
        rel = file.relative_to(ROOT).as_posix().removesuffix('index.html')
        url = urljoin(BASE, rel)
        doc = Document(file.read_text())
        documents[file] = doc
        require(doc.html_lang == 'ko', f'{rel}: language missing')
        require(doc.h1_count == 1, f'{rel}: expected one h1')
        require(doc.canonicals == [url], f'{rel}: canonical mismatch')
        require(bool(doc.title) and doc.title not in titles, f'{rel}: missing/duplicate title')
        require(bool(doc.meta.get('description')) and doc.meta.get('description') not in descriptions, f'{rel}: missing/duplicate description')
        titles.add(doc.title)
        descriptions.add(doc.meta.get('description'))
        require(doc.meta.get('og:url') == url, f'{rel}: OG URL mismatch')
        require(doc.meta.get('og:title') == doc.title, f'{rel}: OG title mismatch')
        require(doc.meta.get('og:description') == doc.meta.get('description'), f'{rel}: OG description mismatch')
        require(len(doc.schemas) == 1, f'{rel}: JSON-LD missing')
        if SITE.get('searchStrategy') == 'naver-first':
            require(doc.meta.get('robots') == 'noindex, follow', f'{rel}: Naver-first policy requires noindex, follow')
        require(not doc.images and 'og:image' not in doc.meta, f'{rel}: unexpected image in text-only site')
        for im in doc.images:
            require(all(k in im for k in ['width', 'height', 'alt']), f'{rel}: image dimensions/alt missing')
        if 'noindex' not in doc.meta.get('robots', ''):
            indexed_urls.add(url)
        all_local_urls.add(url)
        for link in doc.links + [doc.meta.get('og:image', '')]:
            resolved = urljoin(url, link)
            parts = urlsplit(resolved)
            if parts.netloc == urlsplit(BASE).netloc:
                target = disk_path(resolved)
                require(target is not None and target.is_file(), f'{rel}: broken local URL {resolved}')
                all_local_urls.add(parts._replace(fragment='', query='').geturl())
                if parts.fragment and target and target.suffix == '.html' and target.is_file():
                    other = documents.get(target) or Document(target.read_text())
                    require(parts.fragment in other.ids, f'{rel}: broken anchor {resolved}')
        if rel.startswith('posts/'):
            post = next(p for p in POSTS if rel == 'posts/' + p['slug'] + '/')
            require(post['sourceUrl'] in doc.links, f'{rel}: original link missing')
            require(post['publishedAt'] in file.read_text(), f'{rel}: source date missing')
            graph = doc.schemas[0]['@graph']
            require(graph[0]['isBasedOn']['url'] == post['sourceUrl'], f'{rel}: structured source mismatch')
            require(graph[0]['isBasedOn']['datePublished'] == post['publishedAt'], f'{rel}: source date schema mismatch')
            require(graph[0]['dateModified'] == post['introUpdatedOn'], f'{rel}: introduction date schema mismatch')
    home_items = documents[ROOT / 'index.html'].schemas[0]['@graph'][1]['mainEntity']['itemListElement']
    latest = sorted(POSTS, key=lambda p: p['publishedAt'], reverse=True)[:10]
    require([item['url'] for item in home_items] == [urljoin(BASE, 'posts/' + p['slug'] + '/') for p in latest], 'Home must list the latest 10 while retaining older posts')
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = []
    if (ROOT / 'sitemap.xml').is_file():
        sitemap = ET.parse(ROOT / 'sitemap.xml')
        sitemap_urls = [x.text for x in sitemap.findall('.//s:loc', ns)]
    require(len(sitemap_urls) == len(set(sitemap_urls)), 'Sitemap duplicates')
    require(set(sitemap_urls) == indexed_urls, 'Sitemap must exactly match indexable canonical pages')
    if SITE.get('searchStrategy') == 'naver-first':
        require(not (ROOT / 'sitemap.xml').exists(), 'Do not advertise noindex GitHub pages in a sitemap')
    else:
        require(urljoin(BASE, 'sitemap.xml') in (ROOT / 'robots.txt').read_text(), 'Robots sitemap mismatch')
        all_local_urls.add(urljoin(BASE, 'sitemap.xml'))
    all_local_urls.add(urljoin(BASE, 'robots.txt'))
    print(f'Static checks: {len(files)} pages, {len(sitemap_urls)} indexable URLs, {len(all_local_urls)} local resources.')
    if args.http:
        try:
            with urlopen(args.http.rstrip('/') + '/', timeout=10) as response:
                require(response.status == 200 and response.geturl() == args.http.rstrip('/') + '/', 'Root homepage must return 200 without redirect')
                require(response.read() == root_home.read_bytes(), 'HTTP root homepage differs from /blog/')
        except Exception as error:
            errors.append('Root homepage: ' + str(error))
        for url in sorted(all_local_urls):
            local_url = args.http.rstrip('/') + urlsplit(url).path
            try:
                with urlopen(local_url, timeout=10) as response:
                    require(response.status == 200, local_url + ': non-200')
                    if response.headers.get_content_type() == 'text/html':
                        require('<h1' in response.read().decode(), local_url + ': empty HTML')
            except Exception as error:
                errors.append(local_url + ': ' + str(error))
        print(f'HTTP checks: {len(all_local_urls)} local URLs requested under {PREFIX}.')
    if args.sources:
        def source_check(post):
            url = 'https://blog.naver.com/PostView.naver?blogId=dadablog888&logNo=' + post['id'] + '&redirect=Dlog&widgetTypeCall=true&directAccess=false'
            try:
                with urlopen(Request(post['sourceUrl'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                    outer = response.read().decode()
                    require(response.status == 200 and post['id'] in outer, post['id'] + ': public URL mismatch')
                with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=25) as response:
                    html = response.read().decode()
                    require(response.status == 200 and 'se-main-container' in html, post['id'] + ': original body missing')
                    require(post['sourceUrl'] in html, post['id'] + ': source metadata mismatch')
                    if post['originalTitle']:
                        require(escape_title(post['originalTitle']) in html or post['originalTitle'] in html, post['id'] + ': title mismatch')
                return post['id'] + ': OK (public URL + original body)'
            except Exception as error:
                errors.append(post['id'] + ': ' + str(error))
                return post['id'] + ': FAILED'
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(source_check, POSTS):
                print(result)
    if args.growth:
        check_growth()
    if errors:
        print('\n'.join('FAIL: ' + e for e in errors))
        sys.exit(1)
    print('PASS: metadata, canonicals, structure, internal links, source attribution and sitemap agree.')


def escape_title(title):
    from html import escape
    return escape(title)


def check_growth():
    spec = importlib.util.spec_from_file_location('journal_builder', ROOT / 'scripts/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    original_posts = copy.deepcopy(builder.POSTS)
    with tempfile.TemporaryDirectory(prefix='dainblog-growth-') as directory:
        builder.ROOT = Path(directory)
        builder.POSTS = copy.deepcopy(original_posts)
        builder.build()
        original_generated = set(builder.GENERATED)
        old_files = {p['slug']: (builder.ROOT / builder.post_path(p) / 'index.html').read_text() for p in original_posts}
        # Synthetic records remain entirely inside the temporary directory.
        for i in range(70):
            post = copy.deepcopy(original_posts[0])
            post['id'] = f'growth-test-{i}'
            post['slug'] = f'growth-test-{i}'
            post['title'] = f'테스트용 기록 {i}'
            post['topic'] = 'food-and-tea'
            stamp = datetime(2026, 12, 1, tzinfo=timezone(timedelta(hours=9))) + timedelta(days=i)
            post['publishedAt'] = stamp.isoformat()
            post['introUpdatedOn'] = stamp.date().isoformat()
            post['related'] = [original_posts[0]['id']]
            builder.POSTS.append(post)
        builder.POSTS.sort(key=lambda p: p['publishedAt'], reverse=True)
        builder.build()
        pages = list(builder.ROOT.rglob('index.html'))
        for post in original_posts:
            target = builder.ROOT / builder.post_path(post) / 'index.html'
            require(target.read_text() == old_files[post['slug']], 'Adding posts changed an existing introduction: ' + post['slug'])
        require(len(list((builder.ROOT / 'posts').glob('*/index.html'))) == len(original_posts) + 70, 'Growth lost a saved post')
        home = Document((builder.ROOT / 'index.html').read_text())
        items = home.schemas[0]['@graph'][1]['mainEntity']['itemListElement']
        require(len(items) == 10 and items[0]['name'] == '테스트용 기록 69', 'Growth home is not limited to latest 10')
        for path in ['archive/2026/', 'archive/2027/', 'archive/2026/12/page/2/', 'archive/2027/01/page/2/', 'topics/food-and-tea/page/3/']:
            require((builder.ROOT / path / 'index.html').is_file(), 'Missing year/month/pagination page: ' + path)
        for page in pages:
            relative = page.relative_to(builder.ROOT).as_posix().removesuffix('index.html')
            if relative == 'root-site/':
                require(page.read_bytes() == (builder.ROOT / 'index.html').read_bytes(), 'Growth left a stale root homepage copy')
                continue
            doc = Document(page.read_text())
            require(doc.canonicals == [urljoin(BASE, relative)], 'Growth pagination canonical mismatch')
            for link in doc.links:
                url = urljoin(urljoin(BASE, relative), link)
                parts = urlsplit(url)
                if parts.netloc == urlsplit(BASE).netloc:
                    path = unquote(parts.path)
                    target = builder.ROOT / path[len(PREFIX):]
                    if path.endswith('/'):
                        target /= 'index.html'
                    # The isolated fixture checks generated documents; CSS is shared unchanged.
                    if path.endswith('/') or path.endswith('.html'):
                        require(target.is_file(), 'Growth has an unreachable document: ' + path)
        temporary_generated = set(builder.GENERATED)
        builder.POSTS = original_posts
        builder.build()
        require(set(builder.GENERATED) == original_generated, 'Generated catalog did not return to the retained documents')
        for obsolete in temporary_generated - original_generated:
            require(not (builder.ROOT / obsolete).exists(), 'Stale generated document remains: ' + obsolete)
        print(f'Growth checks: initial {len(original_posts)} + 70 temporary records, year/month pagination, unchanged old URLs, all document links and safe stale-page cleanup.')


if __name__ == '__main__':
    main()
