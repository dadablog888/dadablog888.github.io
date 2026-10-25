# 네이버 원문을 우선하는 검색 전략

최우선 목표는 Google 검색 유입이 **https://blog.naver.com/dadablog888** 원문으로 이어지게 하는 것입니다. **https://dadablog888.github.io/** 및 프로젝트 Pages는 보조 기록과 목차입니다. 같은 원칙을 `skills/naver-blog-update/SKILL.md`에도 명시했습니다.

## 구현 정책

- `content/site.json`: `searchStrategy: naver-first`.
- 모든 GitHub HTML: `noindex, follow`.
- noindex인 GitHub 문서를 사이트맵에 넣지 않으며 기존 `sitemap.xml`을 제거합니다.
- GitHub URL을 Search Console에 색인 요청하는 이전 절차는 사용하지 않습니다.
- HTML 크롤링은 허용해 Google이 noindex를 읽을 수 있게 합니다. robots 차단으로 noindex를 가리지 않습니다.
- 각 소개의 눈에 보이는 원문 링크와 `isBasedOn` 출처는 네이버의 해당 게시물입니다.
- 소개는 원문과 별개인 요약 문서이므로 모든 canonical을 네이버 홈 하나로 몰거나, 유사하지 않은 페이지의 canonical이 반드시 인정될 것이라고 가정하지 않습니다. GitHub의 self canonical은 문서 식별용으로 남지만 noindex에 의해 검색 제외를 요청합니다.

`noindex`는 GitHub 페이지가 검색결과에 나타나지 않도록 요청하는 방법입니다. Google이 다시 크롤링해 처리해야 하므로 즉시 반영된다고 보장하지 않습니다. 이 설정이 네이버의 순위나 평가를 이전·상승시키는 것은 아닙니다. 네이버를 우선 노출하도록 강제할 수는 없습니다.

참고: [Google noindex 공식 안내](https://developers.google.com/search/docs/crawling-indexing/block-indexing), [canonical 공식 안내](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

## 네이버에서 관리할 내용

원문에 구체적인 제목, 직접 확인한 경험과 설명, 자연스러운 관련 글 링크를 유지하는 것이 중심입니다. GitHub에 검색어만 바꾼 대량 요약 페이지를 만들어 네이버 검색 평가를 대신할 수 있다고 해석하지 않습니다. 원문 접근이나 검색 허용 상태에 문제가 있으면 네이버 플랫폼의 공개·검색 설정과 실제 검색결과에서 확인해야 합니다.

과거 GitHub 사이트맵을 제출했다면 Search Console에서 이전 제출 상태를 확인하고 필요하면 해당 제출을 삭제할 수 있습니다. 제출을 삭제하는 것만으로 색인이 제거되지는 않으며 HTML의 noindex가 실제 배포되어야 합니다. 이번 작업에서는 Search Console이나 네이버 설정을 변경하지 않았습니다.

## GitHub Pages 배포

통합 저장소는 `dadablog888/dadablog888.github.io`이며 Pages 배포 소스는 `Deploy from a branch` → `main` → `/ (root)`입니다. `.nojekyll`과 생성된 정적 파일을 제공하므로 Pages 빌드에 Python이 필요하지 않습니다. 빌드 결과 전체를 배포해야 하며 홈페이지 하나만 복사해서는 `/blog/`와 CSS를 제공할 수 없습니다.

```text
index.html             # /의 홈페이지
robots.txt             # 실제 호스트 루트 크롤링 규칙
.nojekyll
blog/
  index.html           # /blog/의 같은 홈페이지
  assets/style.css
  posts/
  archive/
  topics/
  robots.txt
```

`assets/style.css`는 편집할 원본이고 `blog/assets/style.css`는 빌드한 배포본입니다. `content/`, `scripts/`, `skills/`, `docs/`는 기존 위치를 유지합니다. `content/generated-pages.json`은 `blog/`를 기준으로 한 상대 경로 목록입니다.

배포 후에는 메인과 대표 과거 소개 페이지의 공개 HTML에서 `noindex, follow`와 정확한 네이버 링크를 확인하세요. 루트 `/robots.txt`가 호스트의 규칙이며 HTML의 noindex를 읽을 수 있도록 크롤링을 허용합니다.

스킬과 수집·적용·생성 스크립트는 커밋·push·설정 저장·배포를 자동으로 실행하지 않습니다.

## 호스트 루트에도 같은 홈 표시

`python3 scripts/build.py`는 `blog/index.html`을 최종 생성한 뒤 같은 저장소의 `index.html`에 복사합니다. 별도 저장소와 `root-site/`는 사용하지 않습니다. 매 갱신마다 `python3 scripts/sync_root_home.py --check`로 두 파일의 바이트 일치와 루트 `.nojekyll`을 확인합니다. 필요한 경우 `python3 scripts/sync_root_home.py`로 같은 저장소 안에서 홈만 다시 동기화할 수 있습니다.

복사본은 강제 이동 없이 같은 화면을 표시합니다. CSS·메뉴·소개 링크는 기존 `/blog/` 경로를 사용하고 canonical도 `/blog/`로 유지합니다. `noindex, follow`는 루트에서도 유지합니다.

`python3 scripts/check.py`는 루트 홈 일치와 `/blog/`의 실제 파일·스타일·내부 링크를 검사합니다. `python3 scripts/check.py --http http://127.0.0.1:8000`으로 실제 HTTP 응답도 검사할 수 있습니다. 로컬 서버는 `/blog/`를 가상의 경로로 바꾸지 않습니다. 실서비스 배포 후에는 두 주소의 HTML 일치와 `/blog/assets/style.css` 로딩을 확인하세요.
