# 多多중국어 · 네이버 원문 보조 문서

이 저장소는 [다다의 네이버 블로그](https://blog.naver.com/dadablog888) 글을 기간별로 읽고 소개 문서로 정리합니다. **검색 유입의 우선 목적지는 네이버 원문입니다.** GitHub Pages는 보조 문서와 목차로 운영합니다.

## 사이트 바로가기

- [글 목차 보기 (GitHub Pages)](https://dadablog888.github.io/blog/): 연도별·주제별로 글을 찾아볼 수 있습니다.
- [네이버 블로그 원문](https://blog.naver.com/dadablog888): 전체 글과 사진은 네이버에서 확인하세요.

`content/site.json`의 `searchStrategy`는 `naver-first`입니다. 생성하는 모든 GitHub HTML은 `noindex, follow`이고, noindex 페이지를 검색용 사이트맵에 제출하지 않습니다. 크롤러가 noindex를 읽을 수 있도록 HTML 크롤링을 차단하지 않습니다. noindex는 GitHub 검색결과 제외를 요청하는 설정이며 네이버의 순위를 높이거나 1위를 보장하는 기능이 아닙니다.

## 기간을 지정해 갱신

설치된 스킬은 `$naver-blog-update`입니다. 날짜는 KST 기준의 **`YYYY-MM` 또는 `YYYY-MM-DD`**만 사용합니다.

```text
$naver-blog-update 2026-08
$naver-blog-update 2026-10
$naver-blog-update 2026-10-10
```

월은 해당 월 전체, 일은 해당 날짜의 게시물을 확인합니다. 같은 기간을 재실행하면 이미 보관한 글도 원문을 다시 확인하고 변경된 소개만 검토·갱신합니다. 매일 과거 한 달씩 처리할 때도 실행할 월을 명시하세요. 예약 작업을 생성한 것은 아닙니다.

스킬 원본: [skills/naver-blog-update/SKILL.md](skills/naver-blog-update/SKILL.md). 개인 스킬 검색 경로 `~/.codex/skills/naver-blog-update`에 이 폴더를 연결했습니다. 스킬 이름이 현재 대화의 목록에 아직 나타나지 않으면 새 대화에서 실행하거나 위 SKILL.md 경로를 명시해 사용할 수 있습니다.

세부 절차와 재실행 기준은 [기간별 갱신 안내](docs/period-updates.md)에 있습니다. 기본적으로 커밋·push·배포는 실행하지 않습니다.

## 수년치 문서 구조

| 경로 | 역할 |
| --- | --- |
| `content/posts/YYYY/MM/<원문ID>.json` | 검토한 소개의 원본. 글마다 한 파일 |
| `/blog/` | 최신 10개와 전체·주제별 목록 연결 |
| `/blog/archive/` | 전체 연도와 월별 목차를 한 화면에 표시 |
| `/blog/archive/2026/` | 연도별 월 목록 |
| `/blog/archive/2026/08/` | 월별 제목·요약 목록 |
| `/blog/archive/2026/08/page/2/` | 월에 글이 30개를 넘을 때 다음 페이지 |
| `/blog/posts/<고정-slug>/` | 제목·날짜가 바뀌어도 유지하는 개별 소개 URL |
| `/blog/topics/<주제>/` | 모든 연도의 주제별 목록. 30개 단위 페이지 나누기 |

글이 있는 연도·월만 생성합니다. 오래된 소개도 삭제하지 않으며 메인에서 빠진 글은 연도·월·주제·관련 글 링크로 찾을 수 있습니다. 알려진 생성 파일 목록은 `content/generated-pages.json`으로 관리합니다. 원문 게시일이 바뀌어 빈 아카이브가 생기면 이전에 생성한 목록 파일만 정리합니다.

최초 최근 10개를 보관한 뒤 2026년 8월 4개를 추가했으며, 다른 실행에서 추가한 기간별 자료도 함께 유지합니다. 현재 개수는 `content/posts/`와 실행 보고서를 기준으로 확인합니다. 수백 개 전체를 모두 읽은 상태는 아닙니다. 전체 공개 목록의 보고 개수와 기간 경계 확인 결과는 각 실행 보고서에 남깁니다.

## 데이터와 변경 판별

- `content/posts/YYYY/MM/<id>.json`: 제목, 원문 제목·게시일·URL, 소개·요약·키워드·분류·관련 글, 원문 해시.
- `content/site.json`: 네이버 원문 주소, Pages 주소, 분류와 `naver-first` 정책.
- `content/updates/<기간>.json`, `content/sync-state.json`: 완료한 기간, 확인 시각, 새 글·변경·변경 없음 수와 목록 범위.
- `.cache/blog-sync/<기간>/`: 가져온 원문의 본문과 검토 중인 JSON. Git에서 제외하며 공개 HTML에 원문 전문을 복제하지 않음.

원문 ID로 중복을 구분하고 제목·분류·게시 시각·정규화한 본문의 해시로 변경을 판별합니다. 해시는 확인 가능한 텍스트에 대한 것입니다. 사진 파일·영상·이미지 안 글자의 변경까지 감지하는 기능은 아닙니다. 초 단위를 확인할 수 없는 게시 시각은 분 단위로 저장합니다.

기존 slug와 관계없는 기간의 자료를 유지합니다. 접근 실패·비공개·삭제 의심은 이전 문서를 지우는 근거로 삼지 않으며, 수집이 불완전하거나 새 소개를 검토하지 않았다면 기간을 완료로 표시하지 않습니다. 이 수집 경로는 네이버의 공개 페이지에 의존하며 공식적으로 보장된 API는 아닙니다.

## 빌드와 로컬 확인

Python 3.9 이상, 실행에 필요한 외부 패키지는 없습니다.

```sh
python3 scripts/build.py
python3 scripts/serve.py
```

미리보기: `http://127.0.0.1:8000/blog/`. 실제 Pages와 같은 프로젝트 경로를 사용하므로 파일을 직접 열기보다 HTTP 서버로 확인하세요. Pages에서는 생성된 정적 파일을 제공하며 Python을 실행하지 않습니다.

현재 저장소 `dadablog888/dadablog888.github.io` 하나에서 두 주소를 제공합니다. 빌드는 `blog/` 아래에 홈페이지·소개·목차를 생성하고, `assets/style.css`를 `blog/assets/style.css`로 복사합니다. 같은 홈을 루트 `index.html`에도 복사하므로 `/`와 `/blog/`가 강제 이동 없이 동일하게 표시됩니다. 메뉴·CSS·글 주소와 canonical은 `/blog/`를 유지합니다.

Pages의 배포 소스는 `main`의 `/ (root)`입니다. 별도 저장소로 파일을 복사하지 않습니다. 매 갱신 후 `python3 scripts/sync_root_home.py --check`로 루트 홈과 `blog/index.html`의 일치를 확인합니다. 로컬 서버도 파일 경로를 바꾸지 않아 실제 배포 구조를 검사합니다. 공개 주소 반영에는 별도 커밋·push와 Pages 배포가 필요합니다. [배포 안내](docs/seo-and-publishing.md#호스트-루트에도-같은-홈-표시).

```sh
python3 scripts/test_sync_blog.py
python3 scripts/check.py --growth
python3 scripts/check.py --http http://127.0.0.1:8000 --sources
git diff --check
```

오프라인 테스트는 명시 날짜, 기간 범위, 본문 수정 판별, 검토 누락 시 적용 차단과 재실행 시 기존 파일 유지 동작을 확인합니다. `--growth`는 임시 디렉터리에 가상 글 70개를 추가해 연도 전환·월별 및 주제별 페이지 나누기를 점검합니다. 가상 글은 실제 콘텐츠에 저장하지 않습니다.

## 문서

- [게시물별 분석](docs/content-analysis.md)
- [기간별 갱신 흐름과 명령](docs/period-updates.md)
- [네이버 우선 검색 전략](docs/seo-and-publishing.md)
- [이번 기간 갱신 결과](docs/period-update-2026-08.md)

제안 커밋 메시지: `feat: add period-based Naver archive sync skill and Naver-first indexing policy`
