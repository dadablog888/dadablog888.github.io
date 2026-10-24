#!/usr/bin/env python3
"""Build a text-first static journal. Every saved post keeps a permanent URL."""
import json
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET
from content_store import load_posts, write_json

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / 'content/site.json').read_text())
POSTS = load_posts(ROOT)
TOPICS = {topic['slug']: topic for topic in SITE['topics']}
BASE = SITE['url']
PREFIX = urlsplit(BASE).path
PAGE_SIZE = 30
INDEXED = {}
GENERATED = set()
assert BASE.startswith('https://') and BASE.endswith('/')


def esc(value):
    return escape(str(value), quote=True)


def local(path=''):
    return PREFIX + path


def absolute(path=''):
    return urljoin(BASE, path)


def post_path(post):
    return 'posts/' + post['slug'] + '/'


def topic_path(slug):
    return 'topics/' + slug + '/'


def date(post):
    return datetime.fromisoformat(post['publishedAt']).strftime('%Y년 %m월 %d일')


def month_key(post):
    return datetime.fromisoformat(post['publishedAt']).strftime('%Y/%m')


def lastmod(posts):
    return max((p['introUpdatedOn'] for p in posts), default=SITE['contentUpdatedOn'])


def item_list(posts):
    return {'@type': 'ItemList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i, 'url': absolute(post_path(p)), 'name': p['title']}
        for i, p in enumerate(posts, 1)]}


def breadcrumbs(items):
    html = '<nav class="breadcrumbs" aria-label="현재 위치"><ol>'
    schema = {'@type': 'BreadcrumbList', 'itemListElement': []}
    for i, (name, path) in enumerate(items, 1):
        html += f'<li><a href="{local(path)}">{esc(name)}</a></li>' if path is not None else f'<li aria-current="page">{esc(name)}</li>'
        schema['itemListElement'].append({'@type': 'ListItem', 'position': i, 'name': name, **({'item': absolute(path)} if path is not None else {})})
    return html + '</ol></nav>', schema


def page_head(title, description, path, schema, noindex=False):
    noindex = noindex or SITE.get('searchStrategy') == 'naver-first'
    verification = f'<meta name="google-site-verification" content="{esc(SITE["googleSiteVerification"])}">' if SITE.get('googleSiteVerification') else ''
    data = json.dumps(schema, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return f'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="{'noindex, follow' if noindex else 'index, follow'}">
  <link rel="canonical" href="{esc(absolute(path))}">
  <meta property="og:locale" content="ko_KR">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{esc(SITE['name'])}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(absolute(path))}">
  <meta name="twitter:card" content="summary">
{verification}
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="{local('assets/style.css')}">
  <script type="application/ld+json">{data}</script>
</head>
<body>
<a class="skip-link" href="#main">본문으로 건너뛰기</a>
<header class="site-header wrap"><a class="brand" href="{local()}">{SITE['name']}</a><nav aria-label="주요 메뉴"><a href="{local()}">최근 글</a><a href="{local('archive/')}">연도·월별 기록</a><a href="{local('#topics')}">주제별 글</a><a href="{SITE['blogUrl']}">네이버 블로그 ↗</a></nav></header>'''


def footer():
    return f'''<footer class="site-footer wrap"><p><a href="{local()}">{SITE['name']}</a> · <a href="{local('archive/')}">전체 기록</a> · <a href="{SITE['blogUrl']}">네이버 원문 블로그</a></p><p>네이버 블로그가 원문이며 이곳은 보조 문서·목차입니다. 전체 글과 사진은 각 네이버 원문에서 확인할 수 있습니다.</p></footer></body></html>'''


def write(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding='utf-8')


def save_page(path, title, description, body, schema, posts, noindex=False):
    noindex = noindex or SITE.get('searchStrategy') == 'naver-first'
    graph = {'@context': 'https://schema.org', '@graph': schema}
    write(path + 'index.html', page_head(title, description, path, graph, noindex) + body + footer())
    GENERATED.add(path + 'index.html')
    if not noindex:
        INDEXED[path] = lastmod(posts)


def collection_schema(path, title, description, posts):
    return {'@type': 'CollectionPage', 'url': absolute(path), 'name': title, 'description': description, 'inLanguage': 'ko', 'mainEntity': item_list(posts)}


def entry(post, level=2):
    return f'''<li class="entry"><p class="entry-meta"><time datetime="{post['publishedAt']}">{date(post)}</time> · <a href="{local(topic_path(post['topic']))}">{esc(TOPICS[post['topic']]['name'])}</a></p><h{level}><a href="{local(post_path(post))}">{esc(post['title'])}</a></h{level}><p>{esc(post['summary'])}</p><p class="entry-links"><a href="{local(post_path(post))}">소개 읽기</a></p></li>'''


def entries(posts, level=2):
    return '<ol class="entry-list">' + ''.join(entry(p, level) for p in posts) + '</ol>'


def topic_links(active=None):
    links = []
    for t in SITE['topics']:
        count = sum(p['topic'] == t['slug'] for p in POSTS)
        if count:
            current = ' aria-current="page"' if t['slug'] == active else ''
            links.append(f'<a href="{local(topic_path(t["slug"]))}"{current}>{esc(t["name"])} ({count})</a>')
    return '<nav class="topic-links" aria-label="주제별 목록">' + ''.join(links) + '</nav>'


def paged_path(base, number):
    return base if number == 1 else base + f'page/{number}/'


def pagination(base, number, total):
    if total <= 1:
        return ''
    links = []
    if number > 1:
        links.append(f'<a rel="prev" href="{local(paged_path(base, number - 1))}">← 이전 페이지</a>')
    # Bounded navigation stays small even with many years of daily posts.
    wanted = {1, total, *range(max(1, number - 2), min(total, number + 2) + 1)}
    previous = 0
    for page in sorted(wanted):
        if previous and page > previous + 1:
            links.append('<span aria-hidden="true">…</span>')
        if page == number:
            links.append(f'<span aria-current="page">{page}</span>')
        else:
            links.append(f'<a href="{local(paged_path(base, page))}">{page}</a>')
        previous = page
    if number < total:
        links.append(f'<a rel="next" href="{local(paged_path(base, number + 1))}">다음 페이지 →</a>')
    return '<nav class="pagination" aria-label="목록 페이지">' + ''.join(links) + '</nav>'


def build_home():
    recent = POSTS[:10]
    body = f'''<main id="main" class="wrap"><header class="page-intro"><p class="eyebrow">다다의 중국 이야기</p><h1>중국 문화와 중국어, 일상에서 발견한 이야기</h1><p>{esc(SITE['description'])}</p><p>중국어 통번역사 다다가 네이버에 기록한 글을 주제와 날짜별로 소개합니다. 관심 있는 내용을 살펴보고 원문으로 이어 읽으세요.</p></header><section id="topics" aria-labelledby="topics-title"><h2 id="topics-title">주제별로 읽기</h2>{topic_links()}</section><section aria-labelledby="recent-title"><div class="section-heading"><h2 id="recent-title">최근 글 {len(recent)}개</h2><a href="{local('archive/')}">전체 {len(POSTS)}개 기록 보기 →</a></div>{entries(recent, 3)}<p class="note">최근 글 목록이 바뀌어도 기존 소개 페이지는 유지됩니다. 확인일: {SITE['verifiedOn']}</p></section><section class="archive-callout"><h2>날짜로 찾아보기</h2><p>지난 글은 연도별·월별 목록에서 찾을 수 있습니다.</p><a href="{local('archive/')}">전체 기록으로 이동 →</a></section></main>'''
    title = '다다중국어 | 중국 문화·밀크티·취미·중국어 이야기'
    schema = [{'@type': 'WebSite', '@id': absolute('#website'), 'url': BASE, 'name': SITE['name'], 'inLanguage': 'ko', 'description': SITE['description']}, collection_schema('', title, SITE['description'], recent)]
    save_page('', title, SITE['description'], body, schema, POSTS)


def build_topics():
    for topic in SITE['topics']:
        posts = [p for p in POSTS if p['topic'] == topic['slug']]
        if not posts:
            continue
        total = (len(posts) + PAGE_SIZE - 1) // PAGE_SIZE
        for number in range(1, total + 1):
            base = topic_path(topic['slug'])
            path = paged_path(base, number)
            subset = posts[(number - 1) * PAGE_SIZE:number * PAGE_SIZE]
            suffix = f' · {number}페이지' if number > 1 else ''
            title = topic['name'] + suffix + ' | 다다중국어'
            description = topic['description'] + (f' 총 {len(posts)}개 글 중 {number}페이지입니다.' if total > 1 else '')
            crumb, crumb_schema = breadcrumbs([('홈', ''), (topic['name'] + suffix, None)])
            body = f'<main id="main" class="wrap">{crumb}<header class="page-intro"><h1>{esc(topic["name"] + suffix)}</h1><p>{esc(description)}</p><p class="note">원문 게시일순 · 총 {len(posts)}개 · 페이지당 최대 {PAGE_SIZE}개</p></header>{topic_links(topic["slug"])}{entries(subset)}{pagination(base, number, total)}</main>'
            save_page(path, title, description, body, [collection_schema(path, title, description, subset), crumb_schema], posts, all(p.get('noindex', False) for p in posts))


def group_index(path, title, description, groups, crumbs, posts):
    crumb, crumb_schema = breadcrumbs(crumbs)
    links = ''.join(f'<li><a href="{local(p)}">{esc(name)}</a><span>{len(group)}개 글</span></li>' for name, p, group in groups)
    body = f'<main id="main" class="wrap">{crumb}<header class="page-intro"><h1>{esc(title)}</h1><p>{esc(description)}</p><p class="note">전체 {len(posts)}개 기록 · 원문 게시일 기준</p></header><ul class="archive-groups">{links}</ul></main>'
    items = {'@type': 'ItemList', 'itemListElement': [{'@type': 'ListItem', 'position': i, 'name': name, 'url': absolute(p)} for i, (name, p, _) in enumerate(groups, 1)]}
    schema = collection_schema(path, title, description, [])
    schema['mainEntity'] = items
    save_page(path, title + ' | 다다중국어', description, body, [schema, crumb_schema], posts, all(p.get('noindex', False) for p in posts))


def build_archives():
    years, months = defaultdict(list), defaultdict(list)
    for post in POSTS:
        key = month_key(post)
        years[key[:4]].append(post)
        months[key].append(post)
    group_index('archive/', '연도·월별 전체 기록', '네이버 원문 게시일을 기준으로 다다의 중국 문화·중국어 이야기를 연도와 월별로 찾아보세요. 새 글을 추가해도 지난 글의 소개 URL은 유지됩니다.', [(y + '년', f'archive/{y}/', years[y]) for y in sorted(years, reverse=True)], [('홈', ''), ('전체 기록', None)], POSTS)
    # The overview exposes every year/month directly, without one giant post list.
    overview = ROOT / 'archive/index.html'
    month_links = ''.join('<section><h2>' + year + '년 월별 목록</h2><ul>' + ''.join(f'<li><a href="{local("archive/" + key + "/")}">{int(key[-2:])}월 ({len(months[key])}개 글)</a></li>' for key in sorted(months, reverse=True) if key.startswith(year + '/')) + '</ul></section>' for year in sorted(years, reverse=True))
    overview.write_text(overview.read_text().replace('</main>', month_links + '</main>'))
    for year in sorted(years, reverse=True):
        group_index(f'archive/{year}/', year + '년의 기록', f'{year}년에 게시된 글을 월별로 모았습니다. 월을 선택하면 해당 기간의 글 제목과 요약을 확인할 수 있습니다.', [(str(int(m[-2:])) + '월', f'archive/{m}/', months[m]) for m in sorted(months, reverse=True) if m.startswith(year + '/')], [('홈', ''), ('전체 기록', 'archive/'), (year + '년', None)], years[year])
    for key, posts in sorted(months.items(), reverse=True):
        year, month = key.split('/')
        label = f'{year}년 {int(month)}월'
        base = f'archive/{key}/'
        total = (len(posts) + PAGE_SIZE - 1) // PAGE_SIZE
        for number in range(1, total + 1):
            subset = posts[(number - 1) * PAGE_SIZE:number * PAGE_SIZE]
            suffix = f' · {number}페이지' if number > 1 else ''
            title = label + ' 글 목록' + suffix
            description = f'{label}에 게시된 다다의 네이버 블로그 글 {len(posts)}개를 소개합니다. ' + (f'{number}페이지에서 ' if total > 1 else '') + '각 글의 제목, 요약과 원문 연결을 확인하세요.'
            crumb, crumb_schema = breadcrumbs([('홈', ''), ('전체 기록', 'archive/'), (year + '년', f'archive/{year}/'), (str(int(month)) + '월' + suffix, None)])
            path = paged_path(base, number)
            body = f'<main id="main" class="wrap">{crumb}<header class="page-intro"><h1>{esc(title)}</h1><p>{esc(description)}</p><p class="note">원문 게시일순 · {number}/{total}페이지 · 페이지당 최대 {PAGE_SIZE}개</p></header>{entries(subset)}{pagination(base, number, total)}</main>'
            save_page(path, title + ' | 다다중국어', description, body, [collection_schema(path, title, description, subset), crumb_schema], posts, all(p.get('noindex', False) for p in posts))


def build_post(post):
    path = post_path(post)
    topic = TOPICS[post['topic']]
    key = month_key(post)
    year, month = key.split('/')
    crumb, crumb_schema = breadcrumbs([('홈', ''), (topic['name'], topic_path(post['topic'])), ('글 소개', None)])
    source = {'@type': 'BlogPosting', 'headline': post['originalTitle'] or '제목 없는 일상 기록', 'url': post['sourceUrl'], 'datePublished': post['publishedAt'], 'author': {'@type': 'Person', 'name': SITE['author'], 'url': SITE['blogUrl']}, 'inLanguage': 'ko'}
    schema = {'@type': 'WebPage', 'url': absolute(path), 'name': post['title'], 'description': post['description'], 'inLanguage': 'ko', 'isBasedOn': source, 'dateModified': post['introUpdatedOn']}
    body = f'''<main class="wrap" id="main">{crumb}<article><header class="page-intro article-header"><p class="eyebrow"><a href="{local(topic_path(post['topic']))}">{esc(topic['name'])}</a></p><h1>{esc(post['title'])}</h1><p>{esc(post['summary'])}</p><dl class="source-meta"><div><dt>원문 작성자</dt><dd>다다 · 多多중국어</dd></div><div><dt>원문 게시일</dt><dd><time datetime="{post['publishedAt']}">{date(post)}</time></dd></div><div><dt>소개 확인·수정일</dt><dd><time datetime="{post['introUpdatedOn']}">{post['introUpdatedOn']}</time></dd></div></dl><a class="original-link" href="{post['sourceUrl']}">네이버 블로그에서 전체 글 읽기 ↗</a></header>'''
    if post.get('sourceNote'):
        body += '<p class="note">' + esc(post['sourceNote']) + '</p>'
    body += ''.join(f'<section class="article-section"><h2>{esc(s["heading"])}</h2><p>{esc(s["text"])}</p></section>' for s in post['sections'])
    if post['takeaways']:
        body += '<section><h2>핵심 내용</h2><ul class="takeaways">' + ''.join('<li>' + esc(t) + '</li>' for t in post['takeaways']) + '</ul></section>'
    if post['keywords']:
        body += '<section><h2>관련 검색 주제</h2><ul class="keywords">' + ''.join('<li>' + esc(k) + '</li>' for k in post['keywords']) + '</ul></section>'
    body += f'''<section class="original-callout"><h2>네이버 원문에서 이어 읽기</h2><p>원문 제목: {esc(post['originalTitle'] or '공백 제목')}</p><a class="original-link" href="{post['sourceUrl']}">네이버 블로그에서 전체 글 읽기 ↗</a><p class="source-url">{post['sourceUrl']}</p></section><p class="note">이 페이지는 실제 확인한 원문을 바탕으로 새로 작성한 소개와 요약입니다. 원문 게시일과 소개 페이지의 확인·수정일은 구분해 표시합니다.</p></article>'''
    related = [next(p for p in POSTS if p['id'] == id_) for id_ in post['related']]
    if related:
        body += '<section class="related"><h2>함께 읽기</h2><ul>' + ''.join(f'<li><a href="{local(post_path(p))}">{esc(p["title"])}</a></li>' for p in related) + '</ul></section>'
    body += f'<nav class="article-navigation" aria-label="글 탐색"><a href="{local(topic_path(post["topic"]))}">{topic["name"]} 글 목록</a><a href="{local("archive/" + key + "/")}">{year}년 {int(month)}월 글 목록</a><a href="{local("archive/")}">전체 기록</a></nav></main>'
    save_page(path, post['title'] + ' | 다다중국어', post['description'], body, [schema, crumb_schema], [post], post.get('noindex', False))


def build_sitemap():
    if SITE.get('searchStrategy') == 'naver-first':
        (ROOT / 'sitemap.xml').unlink(missing_ok=True)
        write('robots.txt', '# Rules apply only at hostname root; HTML noindex remains effective.\n# Naver is the primary source; do not block crawling of HTML noindex tags.\nUser-agent: *\nAllow: /\n')
        return
    root = ET.Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for path, modified in sorted(INDEXED.items()):
        entry_ = ET.SubElement(root, 'url')
        ET.SubElement(entry_, 'loc').text = absolute(path)
        ET.SubElement(entry_, 'lastmod').text = modified
    ET.indent(root, space='  ')
    write('sitemap.xml', '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n')
    write('robots.txt', '# Effective only at the hostname root /robots.txt.\n# Submit /blog/sitemap.xml in Search Console for this project site.\nUser-agent: *\nAllow: /\n\nSitemap: ' + absolute('sitemap.xml') + '\n')


def build_analysis():
    lines = ['# 공개 글 분석', '', f'초기 최근 10개는 {SITE["verifiedOn"]}에 RSS 및 실제 원문으로 확인했습니다. 이후 기간별 공개 목록·실제 본문을 확인한 글을 누적합니다. 실행별 확인일·기간·변경 여부는 content/updates/에 기록합니다.', '', '게시일은 KST이며 확인할 수 있는 정밀도만 사용합니다. 원문 전문은 공개 문서에 복제하지 않습니다. 사이트는 네이버 원문 우선 전략으로 모든 HTML을 noindex, follow로 제공합니다.', '']
    for i, p in enumerate(POSTS, 1):
        lines += [f'## {i}. {p["originalTitle"] or "(원문 제목 공백)"}', '', f'- 원문: {p["sourceUrl"]}', f'- 원문 게시: {p["publishedAt"]}', f'- 원문 분류: {p["originalCategory"]} / 사이트 분류: {TOPICS[p["topic"]]["name"]}', f'- 핵심 내용: {p["summary"]}', '- 제안 검색 키워드: ' + (', '.join(p['keywords']) or '제안하지 않음 — 제목과 본문 정보 부족'), f'- 소개 페이지: {absolute(post_path(p))}', '- 확인 상태: 실제 원문 본문 확인. 이미지 속 텍스트 전체 판독이나 원문이 인용한 외부 자료의 사실 검증까지 수행한 것은 아닙니다.', '']
        if p.get('sourceNote'):
            lines += [p['sourceNote'], '']
    lines += ['## 작성 기준', '', '- 원문 전재 대신 읽을 지점과 구성을 독립적인 문장으로 설명했습니다.', '- 사진, 타사 상품 이미지, 인물관계도와 가사 전문은 게시하지 않습니다. 사진은 네이버 원문에서 볼 수 있습니다.', '- 가격·재고·배송기간·매장 영업 상태를 현재 사실로 단정하지 않았습니다.', '- AI 참고 레시피와 AI 번역 인물관계도는 공식 자료로 표시하지 않았습니다.', '- 빈 제목 글과 그 글만 있는 일상 분류는 noindex이며 sitemap에서 제외했습니다.', '']
    write('docs/content-analysis.md', '\n'.join(lines))


def build():
    INDEXED.clear()
    GENERATED.clear()
    registry = ROOT / 'content/generated-pages.json'
    previous = json.loads(registry.read_text()) if registry.is_file() else []
    build_home()
    # The user Pages repository publishes these files at the host root.
    # Keep /blog/ asset/navigation URLs and its canonical; do not redirect.
    write('root-site/index.html', (ROOT / 'index.html').read_text(encoding='utf-8'))
    write('root-site/.nojekyll', '')
    build_topics()
    build_archives()
    for post in POSTS:
        build_post(post)
    build_sitemap()
    build_analysis()
    write('.nojekyll', '')
    # Delete only known generated files; date edits must not leave stale archive pages.
    for old in set(previous) - GENERATED:
        target = ROOT / old
        if old.endswith('/index.html') and old.split('/')[0] in {'archive', 'topics', 'posts'} and target.resolve().is_relative_to(ROOT.resolve()):
            target.unlink(missing_ok=True)
    write_json(registry, sorted(GENERATED))
    print(f'Built {len(POSTS)} permanent post introductions, topic/date archives; {len(INDEXED)} indexable URLs.')


if __name__ == '__main__':
    build()
