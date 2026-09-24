# The governed pipeline, step by step

Every command runs with the workspace interpreter. On Windows that is
`.venv\Scripts\python.exe`, elsewhere `.venv/bin/python`; this file writes `PY` for
it, `SCRIPTS` for `${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts` (this plugin's
scripts) and `<pack>` for the pack name. `--packs-dir .` names the workspace, whose layout
is `releases/<pack>/` (what you keep) and `.local/<pack>/` (the run: saved pages, text
records, reports - never committed, never edited by hand). Durable coordination lives
under `.local/<pack>/autopilot/` and is read through `swisstip-autopilot status`.

| Step | Approval | Output |
| ---: | --- | --- |
| 1 Scope and questions | A1 | scope proposal and user questions |
| 2 Catalogue | A2 | approved `sources.json`, `sources.md` |
| 3 Acquire and extract | A3 | saved pages, validated text and exception proposal |
| 4 Curate and classify | A4 | proposed curation, dispositions and risk register |
| 5 Build and review facts | fact-review checkpoint | release candidate and review statuses |
| 6 Suites | A5 | `acceptance.yaml`, `regression.yaml` |
| 7 Replay, index and validate | deterministic checkpoint | reports and semantic index |
| 8 Readiness and documents | A6 | `readiness.json`, coverage and limitations |

## 1. Scope and the questions

Write the user questions before choosing a single source. They decide which pages the
catalogue needs and they become the acceptance suite in step 8.

Each question carries: the question in a user's words, with the noise a real user adds;
the trap, meaning the specific wrong answer a general assistant gives; what a correct
answer must establish, marked `[to verify]` wherever it depends on a number, a fee or a
deadline that no source has been read for yet; and the user facts the answer depends on
(nationality, permit, turnover, legal form), because the server has to ask for them.

Add five questions the release must **decline**, with the reason each one is out of
scope. A pack that answers everything is a pack with no boundary.

The user approves the scope statement, questions, review mode and budgets at A1 before
source discovery.

## 2. Catalogue

`sources.json` holds one entry per publisher branch: start URL, allowed hosts, allowed
path prefixes, authority, jurisdiction, language, crawl profile, planning topics and the
discovery record (how the page was found, from which official page, on which date). It
carries URLs and planning metadata only - never page content. `sources.md` is the human
link list, grouped by topic.

Every explicit HTTP(S) Markdown link in `sources.md` becomes a download target. Link
only A2-approved HTTPS URLs inside a selected source's host/path allowlist. Render
rejected, failed and unapproved URLs as inline code. Changing either catalogue file
after planning requires a fresh run.

Tight allowlists are the point. A prefix of `/` is defensible only for a small site;
anywhere else it invites the crawler into news and unrelated topics.

Bump `version` (`draft-N`) with every change. A run directory is bound to the catalogue
it was planned from, so a changed catalogue needs a fresh run; keep the old one under
another name.

Before crawling, print a table of source, expected pages, and which questions it serves,
and name every question no source covers. That gap is this step's finding, and it is
resolved by more discovery or a narrower scope - not by crawling and hoping.

## 3. Acquire

```shell
PY -m swisstip.builder.cli <pack> --packs-dir . --until gaps --download --workers 4 --no-source-plugins
```

Governed mode disables source plugins until their metadata hosts, document hosts,
requests and bytes can be represented in the A2 plan. A plugin-enabled plan is refused
at network confirmation.

The downloader follows the catalogue and nothing else, saving every target byte for byte
under `.local/<pack>/pages/`. Then read `gap-report.md` and classify every gap:

- **catalogue error** - wrong URL or prefix, page moved: fix `sources.json`, bump the version;
- **publisher reality** - dead link, application shell, login, robots block, or a soft
  error page served with HTTP 200: record it in `sources.md` as a known limit, do not retry;
- **budget** - the profile stopped before the page: raise that source's profile;
- **not needed** - the page serves no question: drop it.

A soft error page with status 200 is real: some portals serve an error body to a
non-browser user agent. Look at the body, not only at the status code.

## 4. Extract

```shell
PY -m swisstip.builder.cli <pack> --packs-dir . --from extract --until validate-text --workers 4
```

No model is involved. The stage writes labelled blocks with code-point offsets and
hashes, and a Markdown reading view per record. The reading views are what the readers
read in step 5, and the block IDs are what they cite.

Check before anyone reads: for each question, open the reading view that should answer
it and confirm the answer is present, naming the record and heading path. List records
whose text is far shorter than their saved HTML - a client-rendered table, a component
the extractor does not read, or a PDF that is an image (there is no OCR). List PDFs
without a declared language; they need a `page_languages` rule in step 5.

If a publisher's content sits in a component the extractor cannot read, say so. Do not
work around it in the curation by paraphrasing what you can see in the browser.

## 5. Curate

`curation.yaml` holds topics, concepts, facts and their citations, plus the manifest
every caller reads. Format and field meanings: `curation-schema.md`.

One `kb-reader` subagent per saved page, each proposing at most six concepts from that
page alone, then a `kb-classifier` pass for institutions and basis, then you merge.

Merging rules worth stating: two pages supporting the same concept keep both facts, with
their jurisdictions made explicit; a contradiction between two pages keeps both facts and
goes on the worklist for the reviewer, unresolved by you; an alias that matches three
concepts helps none of them.

The `basis` classification prompt ships inside the installed package at
`swisstip/concepts/prompts/basis_classification_v1.md`; use that file rather than writing
a new prompt, so the classification matches other packs.

## 6. Build and accept

```shell
PY -m swisstip.builder.cli <pack> --packs-dir .
```

Runs build, validate-release, health and accept. The build resolves every citation
against the text dataset, pins it with hashes, verifies every source term against its
excerpt, and refuses an invalid release. Iterate until `build-report.json` drops
nothing; `troubleshooting.md` lists what each failure means.

After the first successful build:

```shell
PY -m swisstip.build.source_terms releases/<pack>/release.json
```

lists candidate source terms found in the excerpts. Adding terms moves the rarity
weights of search, so replay the suites afterwards and say which concepts changed rank.

## 7. Human review

```shell
PY -m swisstip.admin_console.app --packs-dir . --actor "<reviewer name>"
```

The reviewer filters the queue by `review_status`, compares each statement with the
excerpt beside it, and confirms, corrects or rejects. Write them a brief; do not touch
the statuses. When they are done, read the statuses back and report the counts - how
many confirmed, corrected, rejected, and how many in bulk groups. Those numbers go
verbatim into the served limitations, because "confirmed in groups of 100" is a
different claim from "read card by card".

Then rebuild (step 6). The rebuilt release gets a new version and digest.

## 8. Suites

Copy `templates/acceptance.yaml` and `templates/regression.yaml` into the pack and fill
them. `test-suites.md` has the field meanings and the rules that keep the suites honest.
The acceptance suite is the gate; the regression suite is breadth.

## 9. Replay and index

```shell
PY SCRIPTS/replay.py --workspace . --pack <pack> --lexical-only
PY -m swisstip.runtime.search_cli index --release releases/<pack>/release.json \
   --output .local/semantic-index-candidate.json \
   --model qwen3-embedding:0.6b --base-url http://127.0.0.1:11434 --timeout 30
PY SCRIPTS/replay.py --workspace . --pack <pack>
```

`replay.py` is in this plugin, next to `bootstrap.py`. Validate the candidate index, then move it to
`releases/<pack>/semantic-index.json`; the index is bound to the release ID and content
digest, and a stale one silently degrades the server to lexical search.

A failing case is one of three things, and saying which is the work: the release is
wrong (fix the curation), the case is wrong (fix the case and say why the expectation
was wrong), or retrieval is wrong (fix aliases, source terms or the sample question,
then replay everything). Never make a case pass by weakening the phrase it quotes from
the official page.

A case that fails for a genuine retrieval limit is committed with `blocking: false` and
a `quarantine_reason` naming what was measured on which release. A case that fails
because the knowledge is missing is not quarantined; it is a gap.

## 10. Readiness

The workflow screen prints the attestation packet and exposes the only governed
attestation action. It runs G1-G6 with the console actor. Claude never invokes
`--attested-by` directly.

## 11. Documents

Coverage and limitations state, in absolute numbers read from the release and its
reports: what the pack covers, the snapshot date and when it goes stale, the counts, who
reviewed what and when, and what is explicitly not covered. The served `limitations` in
the curation and the written document must say the same thing in the same words - a
caller reads one, a reader reads the other.

## Serving the result

```shell
PY -m swisstip.mcp_server.server --release releases/<pack>/release.json
```

Add `--require-ready` to refuse a release whose readiness record does not match.
