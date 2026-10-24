---
name: naver-blog-update
description: Refresh dadablog888 Naver blog introductions in the dainblog repository for an explicit YYYY-MM month or YYYY-MM-DD day, rechecking changed originals and retaining all saved years. Use for period backfills and repeat daily or monthly updates.
---

# Naver blog period update

## Highest-priority search strategy

The user's primary search destination is **https://blog.naver.com/dadablog888**, not **https://dadablog888.github.io/** or its project pages. GitHub Pages is a supporting archive and document catalog. Preserve `searchStrategy: naver-first` and **`noindex, follow` on every generated GitHub HTML page**. Do not re-enable GitHub indexing, submit GitHub URLs for indexing, or generate an indexable GitHub sitemap as part of a refresh. Keep visible original links and accurate Naver provenance. Do not claim that noindex transfers ranking, that a summary canonical forces Naver selection, or that Naver will rank first.

This priority applies to every month/day, including historical backfills and scheduled invocations. A future explicit user change can revise the strategy; ordinary updates must not.

## Target and date

Use the current dainblog checkout. If invoked elsewhere, the installed skill's resolved directory belongs to `<repo>/skills/naver-blog-update`; use that repository and verify `content/site.json` has the intended Naver blog URL. Read repository instructions before editing.

Require a literal **`YYYY-MM` or `YYYY-MM-DD`** in Asia/Seoul. Validate with `period_bounds` in `scripts/sync_blog.py`. Do not substitute today/yesterday/next month or silently update another period. If the period is missing or ambiguous, request the literal value. One invocation handles one period.

Examples:

- `$naver-blog-update 2026-08` — all posts published in August 2026, including rechecking saved posts.
- `$naver-blog-update 2026-10-10` — only the specified KST publication date.
- `Use $naver-blog-update to refresh 2026-07; preserve existing posts and do not commit or push.`

These invocations do not create a recurring schedule. In an authorized scheduled task, the prompt must still supply a literal period. Keep commit/push/publication outside this skill unless separately authorized by the user; existing no-commit/no-push instructions remain applicable.

## Collect, review, apply

1. Inspect `git status`, `content/site.json`, and the target records in `content/posts/YYYY/MM/<id>.json`. Do not read all years' bodies into context. Run:

   `python3 scripts/sync_blog.py collect 2026-08`

   Replace the sample period with the literal requested value. The helper scans the paginated public title list through the period boundary; RSS alone cannot enumerate historical posts. It rereads saved target IDs too. It stores full normalized source text only under ignored `.cache/blog-sync/<period>/sources/` and writes a manifest. This is an observed public Naver endpoint, not an official supported API; if it changes, report incomplete coverage instead of assuming an empty period.

2. Read the manifest. Only load **new/changed** sources and their existing introduction JSON into model context. Unchanged source hashes do not need another editorial pass. Source hashes cover title, category, KST publication time at minute precision and body text. Missing/blocked/deleted or moved posts must not silently delete previous documents. If collection is incomplete, preserve the existing site and report the unresolved IDs.

3. Read each new/changed source in full. Write independently worded introductions into the manifest's `reviewFile` paths. Preserve existing slugs; new slugs should use the immutable numeric Naver ID. Keep exact source title/category/URL, a verified publication timestamp, and the manifest's source hash. Set `introUpdatedOn` to the actual editorial review date. Preserve unrelated records and manual fields. Use the schema in the existing per-post JSON files; check `scripts/build.py` when adding fields.

   - Summarize only observed text; describe the author's interpretation as interpretation.
   - Do not republish full original bodies, lyrics, images or AI-generated guesses.
   - Do not turn historical prices, policies, health claims or statistics into current verified advice.
   - Short, empty-title or image-only sources may need a restrained note and `noindex`; do not invent a topic.
   - Add a topic only when actual content needs it. Do not force travel/economics into unrelated categories.
   - Related IDs must exist. Preserve prior public URLs even if a title or publication date changes.

4. Run `python3 scripts/sync_blog.py apply <period>`. The helper validates the entire reviewed batch, writes per-post JSON, and records a completed-period report in `content/updates/<period>.json` and `content/sync-state.json`. Full original text remains in the ignored local cache. Apply does not author summaries, build, commit or push.

5. Run `python3 scripts/build.py` and `python3 scripts/check.py`. The site must retain all years, show only the latest ten on home, expose all saved introductions through year → month → post and topic navigation, and paginate long lists with real HTML links. Confirm every generated page stays `noindex, follow`, no images or forced redirects reappear, and no GitHub sitemap advertises noindex pages. Run `python3 scripts/test_sync_blog.py` after collector/storage changes, and `python3 scripts/check.py --growth` after archive/builder changes. Perform a representative local preview after visible changes.

6. **Every refresh must copy the final homepage into the host-root Pages checkout.** After the final build, run `python3 scripts/sync_root_home.py` followed by `python3 scripts/sync_root_home.py --check`. The default destination is the sibling checkout `/Users/won/workspace/dadablog888.github.io` for this installation; use `--destination <checkout>` only when the user has relocated it. Read that repository's instructions and inspect its status before writing. The helper copies `root-site/index.html` and `root-site/.nojekyll` into its publishing root and verifies byte equality against the final project homepage. Never skip this for historical or unchanged periods. If the checkout is missing or mismatched, retain the staged `root-site/` files and report the root synchronization as incomplete; do not claim the whole refresh workflow is complete. `build.py` always regenerates `root-site/`, and `check.py` rejects a missing or stale staged copy. The `blog` repository serves `/blog/`; only `dadablog888/dadablog888.github.io` serves the host root. Preserve `/blog/` asset/navigation URLs, the `/blog/` canonical and `noindex, follow`; display the copied page directly without a forced redirect. This local copy requirement does not authorize commit, push, repository creation or Pages settings changes by itself; the user's separate instructions govern publication.

7. Report the literal period, coverage, new/changed/unchanged/error counts, source/body limitations, and the local file changes, including the root homepage copy and its deployment status. Re-run collection after first applying to verify unchanged hashes when testing a new integration; unchanged runs must not rewrite introductions or advance their modification dates. Do not call an incomplete or unreviewed batch complete.

## Token-aware operation

Read the manifest before bodies; process one explicit period at a time. Use the helper for pagination, parsing, hashing and file writes. Review only changed sources. If a month is large, process bounded groups within that same month and keep a clear pending list; do not replace source review with generated boilerplate to save tokens. The all-or-nothing apply check prevents partial, unreviewed periods being marked complete.
